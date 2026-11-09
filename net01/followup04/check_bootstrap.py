"""Three zero-Node checks of the exact new journal handoff boundary."""
import argparse
import ast
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import controller_bootstrap as bootstrap


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    result=dict(scope='0Node/ROS/GZ/NN; actual stdlib bootstrap plus exact original I/O statements',checks={})
    original_argv=sys.argv[:];original_path=sys.path[:]
    class InterruptHeavyImport:
        def find_spec(self,fullname,path=None,target=None):
            if fullname=='headquarters':raise KeyboardInterrupt('controlled pre-heavy-import interruption')
    hook=InterruptHeavyImport()
    try:
        interrupted=out/'interrupted';sys.argv=['controller_bootstrap.py','--run-dir',str(interrupted)]
        sys.meta_path.insert(0,hook)
        try:bootstrap.main()
        except KeyboardInterrupt:pass
        else:raise AssertionError('controlled import was not interrupted')
        finally:sys.meta_path.remove(hook)
        state=json.loads((interrupted/'bootstrap-state.json').read_text())
        assert (interrupted/'allocation-events.jsonl').read_bytes()==b'' and state['closed']
        assert not state['journal_claimed'] and 'numpy' not in sys.modules and 'torch' not in sys.modules
        result['checks']['before_heavy_import_real_empty_journal_closed']=state

        directory=out/'normal';directory.mkdir();journal=(directory/'allocation-events.jsonl').open('x',buffering=1)
        state=dict(directory_claimed=False,journal_claimed=False)
        Owned=bootstrap.owned_path_type(directory,journal,state);owned=Owned(directory)
        main_ast=ast.parse((bootstrap.FROZEN/'gz01/headquarters.py').read_text())
        fn=next(n for n in main_ast.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        mkdir=next(n for n in fn.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
            and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='mkdir')
        exec(compile(ast.Module(body=[mkdir],type_ignores=[]),'original-main-mkdir','exec'),dict(args=SimpleNamespace(run_dir=owned)))
        policy=ast.parse((bootstrap.FROZEN/'rl01/ros_policy.py').read_text())
        cls=next(n for n in policy.body if isinstance(n,ast.ClassDef) and n.name=='CheckpointHeadquarters')
        ctor=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
        node=SimpleNamespace(evaluator=SimpleNamespace(event=lambda event:None))
        exec(compile(ast.Module(body=[ctor.body[0]],type_ignores=[]),'original-constructor-open','exec'),dict(self=node,directory=owned))
        assert node.events is journal and node.events.fileno()==state['claimed_fileno']
        assert os.fstat(node.events.fileno()).st_ino==(directory/'allocation-events.jsonl').stat().st_ino
        core=ast.parse((bootstrap.FROZEN/'src/multi_robot_exploration/multi_robot_exploration/control.py').read_text())
        record=next(n for c in core.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='record')
        scope=dict(json=json);exec(compile(ast.Module(body=[record],type_ignores=[]),'original-record','exec'),scope)
        scope['record'](node,dict(kind='fixture_original_write',request_uuid='no-real-request'))
        journal.close();assert json.loads((directory/'allocation-events.jsonl').read_text())['kind']=='fixture_original_write'
        result['checks']['exact_original_mkdir_open_record_same_fd_inode']=True

        try:owned.mkdir(parents=True,exist_ok=False)
        except FileExistsError:pass
        else:raise AssertionError('second directory claim accepted')
        try:(owned/'allocation-events.jsonl').open('x',buffering=1)
        except FileExistsError:pass
        else:raise AssertionError('second journal claim accepted')
        existing=out/'already-owned';existing.mkdir();sentinel=existing/'allocation-events.jsonl';sentinel.write_text('historical-sentinel')
        sys.argv=['controller_bootstrap.py','--run-dir',str(existing)]
        try:bootstrap.main()
        except FileExistsError:pass
        else:raise AssertionError('existing directory accepted')
        assert sentinel.read_text()=='historical-sentinel'
        result['checks']['existing_and_second_claims_still_exclusive']=True
        result['status']='PASS'
    finally:
        sys.argv=original_argv;sys.path[:]=original_path
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
