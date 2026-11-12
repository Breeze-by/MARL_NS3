"""Direct actual helper and narrow event AST; standard library, no ROS/model."""
import argparse
import ast
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "net01"))
from controller_bootstrap import observed_spin

RAW_PAYLOAD = "RAW-MESSAGE-MUST-NOT-BE-SAVED"


class Message:
    pass


class Subscription:
    topic_name = "/fixture/topic"
    msg_type = Message
    raw = False
    payload = RAW_PAYLOAD


class BrokenSubscription(Subscription):
    @property
    def topic_name(self):
        raise OSError("fixture metadata unavailable")


class Unwritable:
    def __truediv__(self, name):
        return self

    def open(self, mode):
        raise OSError("fixture diagnostic write failure")


def _take_subscription(sub, error):
    raise error


def exception_case(directory, subscription, error):
    state = {}
    cause, context = error.__cause__, error.__context__
    try:
        observed_spin(_take_subscription, directory, state)(subscription, error)
    except BaseException as caught:
        assert caught is error
        assert caught.__cause__ is cause and caught.__context__ is context
    else:
        raise AssertionError("original exception did not propagate")
    return state


def source_checks():
    restored = []
    for relative in ("net01/controller_bootstrap.py", "net01/a0_controller_bootstrap.py"):
        tree = ast.parse((REPO / relative).read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        blocks = [n for n in ast.walk(main) if isinstance(n, ast.Try)
                  and any(isinstance(x, ast.Assign) and ast.unparse(x.targets[0]) == "frozen.rclpy.spin"
                          and ast.unparse(x.value).startswith("observed_spin(") for x in n.body)]
        assert len(blocks) == 1
        assert any(isinstance(x, ast.Assign) and ast.unparse(x.targets[0]) == "frozen.rclpy.spin"
                   and ast.unparse(x.value) == "original_spin" for x in blocks[0].finalbody)
        restored.append(relative)
    tree = ast.parse((REPO / "net01/controller_bootstrap.py").read_text())
    helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "observed_spin")
    raises = [n for n in ast.walk(helper) if isinstance(n, ast.Raise)]
    assert len(raises) == 1 and raises[0].exc is None and raises[0].cause is None

    tree = ast.parse((REPO / "net01/run_network_case.py").read_text())
    observer = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "NetworkObserver")
    method = next(n for n in observer.body if isinstance(n, ast.FunctionDef) and n.name == "event")
    class Base:
        controlled_time = False

        def event(self, kind, **fields):
            self.calls.append((kind, fields))
    clock_calls = []
    def now():
        clock_calls.append(True)
        return 123456789
    node = ast.ClassDef(name="ActualObserver", bases=[ast.Name(id="Base", ctx=ast.Load())],
                        keywords=[], body=[method], decorator_list=[])
    namespace = dict(Base=Base, time=SimpleNamespace(monotonic_ns=now))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 "actual-NetworkObserver.event", "exec"), namespace)
    actual = namespace["ActualObserver"]()
    actual.calls = []
    for kind, process in (("process_signal", "exploration"), ("process_signal", "bag"),
                          ("process_exit", "exploration")):
        fields = dict(process=process, pid=321, signal="SIGINT", unchanged="value")
        actual.event(kind, **fields)
        received_kind, received = actual.calls[-1]
        expected = dict(fields)
        if (kind, process) == ("process_signal", "exploration"):
            expected["controller_signal_event_monotonic_ns"] = 123456789
        assert received_kind == kind and received == expected
    assert len(clock_calls) == 1
    return dict(bootstrap_finally_restores=restored, bare_raise=True,
                event_cases=actual.calls, event_monotonic_calls=len(clock_calls))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--admission", type=Path, required=True)
    args = parser.parse_args()
    admission = json.loads(args.admission.read_text())
    if admission["execution_authorized"] is not True or admission["runtime_source_commit"].startswith("PENDING"):
        raise RuntimeError("Root has not admitted this observer fixture")
    output = REPO / admission["output_relative_repo"]
    output.mkdir(exist_ok=False)
    rows, complete, begin = [], False, time.monotonic_ns()
    previous = os.environ.get("NET01_SESSION_ID")
    os.environ["NET01_SESSION_ID"] = str(admission["session_id"])
    try:
        normal = output / "normal"
        normal.mkdir()
        calls, state, token, argument, keyword = [], {}, object(), object(), object()
        def original(*args, **kwargs):
            calls.append((args, kwargs))
            return token
        result = observed_spin(original, normal, state)(argument, named=keyword)
        assert result is token and calls == [((argument,), dict(named=keyword))]
        assert state == {} and not list(normal.iterdir())
        rows.append(dict(case="normal", original_calls=len(calls), return_identity=True, nofile=True))
        for label, sub in (("runtime_error", Subscription()), ("metadata_failure", BrokenSubscription())):
            directory = output / label
            directory.mkdir()
            error = RuntimeError(label)
            error.__cause__ = ValueError("fixture original cause")
            state = exception_case(directory, sub, error)
            path = directory / "controller-spin-exception.json"
            raw = path.read_text()
            evidence = json.loads(raw)
            assert RAW_PAYLOAD not in raw and "_take_subscription" in evidence["traceback"]
            assert "fixture original cause" in evidence["traceback"]
            metadata = evidence["subscriptions"][0]
            assert metadata["msg_type"] == Message.__module__ + "." + Message.__qualname__
            assert metadata["raw"] is False
            if label == "runtime_error":
                assert metadata["topic_name"] == Subscription.topic_name
            else:
                assert metadata["topic_name_error"] == "OSError"
            assert "spin_exception_record_failure" not in state
            rows.append(dict(case=label, same_exception=True, raw_payload_absent=True,
                             evidence=str(path.relative_to(output)), state=state))
        state = exception_case(Unwritable(), Subscription(), KeyboardInterrupt("fixture original"))
        assert state["spin_exception_record_failure"] == "OSError"
        rows.append(dict(case="write_failure", same_original_KeyboardInterrupt=True, state=state))
        checks = source_checks()
        complete = True
    finally:
        if previous is None:
            os.environ.pop("NET01_SESSION_ID", None)
        else:
            os.environ["NET01_SESSION_ID"] = previous
        result = dict(status="PASS" if complete else "FAIL_OR_INCOMPLETE", cases=rows,
            source_checkpoint=admission["runtime_source_commit"], source_checks=checks if complete else None,
            start_monotonic_ns=begin, end_monotonic_ns=time.monotonic_ns(),
            scope="Actual observer transparency only; 0ROS/native/GZ/NN/bag/signal/thread/child processes")
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(status=result["status"], cases=len(rows), output=str(output))))


if __name__ == "__main__":
    main()
