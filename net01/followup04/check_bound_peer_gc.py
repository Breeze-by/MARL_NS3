"""Exact constructor tail/restore/finally AST with controlled stubs; 0Node.

Uses real CPython GC state and resource accounting, never init ROS or collect.
"""
import argparse
import ast
import gc
import json
from pathlib import Path
import resource
import time
from types import SimpleNamespace


def main(output):
    source=Path(__file__).resolve().parents[1]/'bound_peer.py'
    module=ast.parse(source.read_text())
    cls=next(x for x in module.body if isinstance(x,ast.ClassDef) and x.name=='BoundPeer')
    constructor=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='__init__')
    start=next(i for i,x in enumerate(constructor.body) if isinstance(x,ast.Assign)
        and isinstance(x.targets[0],ast.Attribute) and x.targets[0].attr=='gc_original_enabled')
    restore=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='restore_runtime_gc')
    original_main=next(x for x in module.body if isinstance(x,ast.FunctionDef) and x.name=='main')
    cleanup=next(x for x in original_main.body if isinstance(x,ast.Try)).finalbody
    def function(name,arg,body):
        return ast.FunctionDef(name=name,args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=arg)],
            kwonlyargs=[],kw_defaults=[],defaults=[]),body=body,decorator_list=[])
    scope={'gc':gc,'time':time,'resource':resource}
    tree=ast.Module(body=[function('after_resources','self',constructor.body[start:]),restore,
        function('actual_finally','node',cleanup)],type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree),str(source),'exec'),scope)
    checks={};initial=gc.isenabled();threshold=gc.get_threshold();states=[]
    class SpinInterrupted(Exception):pass
    class PersistFailed(Exception):pass
    try:
        for enabled,persist_error in ((True,False),(False,False),(True,True)):
            if enabled:gc.enable()
            else:gc.disable()
            node=SimpleNamespace();order=[]
            scope['after_resources'](node)
            assert not gc.isenabled() and node.gc_runtime['processing_start_enabled'] is False
            assert gc.get_threshold()==threshold
            def persist():
                order.append('persist')
                assert gc.isenabled()==enabled and node.gc_runtime['processing_end_enabled'] is False
                assert node.gc_runtime['restored_enabled']==enabled
                if persist_error:raise PersistFailed()
            node.restore_runtime_gc=lambda:scope['restore_runtime_gc'](node)
            node.persist_records=persist;node.destroy_node=lambda:order.append('destroy')
            scope['rclpy']=SimpleNamespace(try_shutdown=lambda:order.append('try_shutdown'))
            try:
                try:raise SpinInterrupted()
                finally:scope['actual_finally'](node)
            except (SpinInterrupted,PersistFailed) as error:
                assert isinstance(error,PersistFailed if persist_error else SpinInterrupted)
            else:raise AssertionError('Original exception swallowed')
            assert order==['persist','destroy','try_shutdown']
            assert gc.isenabled()==enabled and gc.get_threshold()==threshold
            assert node.gc_runtime['peak_rss_KiB']>0
            name='persist_failure_visible' if persist_error else 'initial_GC_'+str(enabled)
            checks[name]=True;states.append(dict(case=name,gc_runtime=node.gc_runtime,order=order))
    finally:
        if initial:gc.enable()
        else:gc.disable()
    output.mkdir(parents=True,exist_ok=False)
    result=dict(status='PASS',scope='Actual AST constructor GC tail/restore/main finally, real CPython GC; stub persist/Node/try_shutdown. 0ROS/GZ/NN; not timing/memory endurance or actual ROS shutdown PASS',checks=checks,states=states)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
