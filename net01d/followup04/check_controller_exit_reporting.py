"""Actual reporting AST + short Python children only; no ROS/model imports."""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]


def function(name, parameters, body, namespace, source):
    # Same AST-isolation approach as check_contract.py; no copied predicate.
    node = ast.FunctionDef(name=name, args=ast.arguments(posonlyargs=[],
        args=[ast.arg(arg=p) for p in parameters], kwonlyargs=[],
        kw_defaults=[], defaults=[], vararg=None, kwarg=None), body=body, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(source), "exec"), namespace)
    return namespace[name]


def actual_blocks():
    source = REPO / "net01/run_network_case.py"
    tree = ast.parse(source.read_text())
    observer = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "NetworkObserver")
    persist = next(n for n in observer.body if isinstance(n, ast.FunctionDef)
                   and n.name == "persist_observer_records")
    writes = [n for n in persist.body if isinstance(n, ast.Expr)
              and any(isinstance(x, ast.Constant) and x.value == "network-controller-exit.json"
                      for x in ast.walk(n))]
    assert len(writes) == 1, "actual controller persistence statement changed"
    namespace = dict(json=json, os=os, time=time, controller_process=None)
    capture = function("capture", ["self"], writes, namespace, source)

    host = REPO / "net01/host_run.py"
    main = next(n for n in ast.parse(host.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    final = next(n.finalbody for n in main.body if isinstance(n, ast.Try)
                 and any(isinstance(x, ast.Assign) and isinstance(x.targets[0], ast.Name)
                         and x.targets[0].id == "controller_path" for x in n.finalbody))
    begin = next(i for i, n in enumerate(final) if isinstance(n, ast.Assign)
                 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "controller_path")
    load_begin = begin
    # Actual controller path/load and existing host outcome write, all three statements.
    load = function("load", ["case", "result", "outcome"], final[begin:],
                    dict(json=json), host)
    begin = next(i for i, n in enumerate(main.body) if isinstance(n, ast.Assign)
                 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "saved")
    integrity = function("integrity", ["case", "result", "controlled", "direct_reference"],
                         main.body[begin:], dict(json=json), host)
    return capture, namespace, load, integrity, dict(
        persist_source=str(source.relative_to(REPO)), persist_lines=[writes[0].lineno, writes[0].end_lineno],
        host_source=str(host.relative_to(REPO)), load_lines=[final[load_begin].lineno, final[-1].end_lineno],
        integrity_source="Actual main body from saved={} through final return; A0/control gates retained")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--admission", type=Path, required=True)
    args = parser.parse_args()
    admission = json.loads(args.admission.read_text())
    if admission["execution_authorized"] is not True or admission["runtime_source_commit"].startswith("PENDING"):
        raise RuntimeError("Root has not admitted this reporting fixture")
    output = REPO / admission["output_relative_repo"]
    output.mkdir(exist_ok=False)
    capture, namespace, load, integrity, sources = actual_blocks()
    children, cases = [], []
    complete = False
    begin = time.monotonic_ns()
    old_session = os.environ.get("NET01_SESSION_ID")
    os.environ["NET01_SESSION_ID"] = str(admission["session_id"])
    try:
        for label, exit_code, expected in (("exit0", 0, 0), ("exit1", 1, 1),
                ("not_created", None, 1), ("alive", None, 1), ("missing", 0, 1)):
            case = output / label
            case.mkdir()
            process = None
            if label != "not_created":
                code = "import time; time.sleep(4)" if label == "alive" else f"raise SystemExit({exit_code})"
                process = subprocess.Popen([sys.executable, "-B", "-c", code])
                children.append(process)
                if label != "alive":
                    process.wait(timeout=2)
            namespace["controller_process"] = process
            if label != "missing":
                capture(SimpleNamespace(directory=case))
            for name in ("bound-mask-recording-saved.json", "peer-recording-saved.json"):
                (case / name).write_text(json.dumps(dict(saved=True)))
            (case / "network-gateway-saved.json").write_text(json.dumps(dict(saved=True,
                cleanup=dict(resources_destroyed=True, end_frame_flushed=True))))
            (case / "a0-direct-safety-saved.json").write_text(json.dumps(dict(saved=True,
                direct_reference=True, business_wires_installed=False,
                registered_owned_unknown_or_active=0, safety_connections=0)))
            (case / "network-gateway-exit.json").write_text(json.dumps(dict(native_exit=0)))
            result = dict(runner_exit=0, hub_exit=0, controlled_time=dict(integrity=True))
            outcome = case.with_name(case.name + ".host-exit.json")
            load(case, result, outcome)
            actual = integrity(case, result, object(), True)
            evidence = json.loads(case.with_name(case.name + ".network-integrity.json").read_text())
            row = dict(case=label, child_pid=None if process is None else process.pid,
                actual_child_returncode=None if process is None else process.poll(),
                host_record=json.loads(outcome.read_text()), network_record=evidence,
                actual_return=actual, expected_return=expected)
            cases.append(row)
            assert actual == expected, label
            assert evidence["network_run_integrity"] is (expected == 0), label
            assert evidence["controller_exit"] == result["controller_exit"], label
            if label != "missing":
                recorded = result["controller_exit"]
                assert recorded["session_id"] == admission["session_id"], label
                assert recorded["case"] == str(case.resolve()), label
                assert begin <= recorded["observed_monotonic_ns"] <= time.monotonic_ns(), label
            if label in ("exit0", "exit1"):
                assert result["controller_exit"]["started"] is True, label
                assert result["controller_exit"]["returncode"] == process.returncode, label
                assert result["controller_exit"]["pid"] == process.pid, label
            elif label in ("not_created", "alive"):
                assert result["controller_exit"]["returncode"] is None, label
                assert result["controller_exit"]["started"] is (label == "alive"), label
            else:
                assert result["controller_exit"]["reason"] == "missing controller exit evidence", label
        complete = True
    finally:
        for process in children:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=1)
        if old_session is None:
            os.environ.pop("NET01_SESSION_ID", None)
        else:
            os.environ["NET01_SESSION_ID"] = old_session
        result = dict(status="PASS" if complete else "FAIL_OR_INCOMPLETE", cases=cases,
            source_checkpoint=admission["runtime_source_commit"], actual_AST=sources,
            start_monotonic_ns=begin, end_monotonic_ns=time.monotonic_ns(),
            owned_children=[dict(pid=p.pid, returncode=p.returncode, alive=p.poll() is None) for p in children],
            scope="Reporting only; zero ROS/native/Gazebo/Policy/bag, no old evidence changes")
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(status=result["status"], cases=len(cases), output=str(output))))


if __name__ == "__main__":
    main()
