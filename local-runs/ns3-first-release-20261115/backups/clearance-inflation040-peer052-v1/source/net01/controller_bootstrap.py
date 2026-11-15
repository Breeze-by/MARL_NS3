"""Own the real request journal before heavy frozen-controller imports.

Only the new exclusive run directory and its exclusive journal are handed once
into the frozen main/constructor. No old log is repaired and no request is made
here. The original main parses the original argv and owns all ROS/policy work.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
FROZEN=HERE.parent/"workspace"


def observed_spin(original_spin,directory,state):
    def spin(*args,**kwargs):
        try:
            return original_spin(*args,**kwargs)
        except BaseException as error:
            try:
                observed=time.monotonic_ns()
                state['spin_exception_observed_monotonic_ns']=observed
                row=dict(pid=os.getpid(),session_id=os.environ.get('NET01_SESSION_ID'),
                    observed_monotonic_ns=observed,
                    scope='Raw spin exception observation, not a fault verdict; original handler remains authoritative',
                    exception_type=type(error).__module__+'.'+type(error).__qualname__,
                    exception_repr=repr(error),cause_repr=repr(error.__cause__),
                    context_repr=repr(error.__context__),
                    traceback=''.join(traceback.format_exception(type(error),error,error.__traceback__)),
                    subscriptions=[])
                tb=error.__traceback__
                while tb is not None:
                    if tb.tb_frame.f_code.co_name=='_take_subscription':
                        item=dict(filename=tb.tb_frame.f_code.co_filename,line=tb.tb_lineno)
                        sub=tb.tb_frame.f_locals.get('sub')
                        value=None
                        for name in ('topic_name','msg_type','raw'):
                            try:
                                value=getattr(sub,name)
                                item[name]=(value.__module__+'.'+value.__qualname__
                                    if name=='msg_type' else value)
                            except BaseException as metadata_error:
                                item[name+'_error']=type(metadata_error).__name__
                        row['subscriptions'].append(item)
                        del sub,value
                    tb=tb.tb_next
                del tb
                with (directory/'controller-spin-exception.json').open('x') as stream:
                    json.dump(row,stream,indent=2)
            except BaseException as diagnostic_error:
                state['spin_exception_record_failure']=type(diagnostic_error).__name__
            raise
    return spin


def owned_path_type(directory,journal,state):
    base=type(Path())
    target=directory/'allocation-events.jsonl'
    class OwnedPath(base):
        def mkdir(self,mode=0o777,parents=False,exist_ok=False):
            if self==directory and mode==0o777 and parents and not exist_ok and not state['directory_claimed']:
                state['directory_claimed']=True
                return
            return super().mkdir(mode=mode,parents=parents,exist_ok=exist_ok)

        def open(self,mode='r',buffering=-1,encoding=None,errors=None,newline=None):
            if (self==target and mode=='x' and buffering==1 and encoding is None
                    and errors is None and newline is None and not state['journal_claimed']):
                state['journal_claimed']=True
                state['claimed_fileno']=journal.fileno()
                return journal
            return super().open(mode,buffering,encoding,errors,newline)
    return OwnedPath


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--run-dir',type=Path,required=True)
    args,_=parser.parse_known_args()
    directory=args.run_dir
    directory.mkdir(parents=True,exist_ok=False)
    journal=(directory/'allocation-events.jsonl').open('x',buffering=1)
    state=dict(pid=os.getpid(),created_monotonic_ns=time.monotonic_ns(),
        created_fileno=journal.fileno(),directory_claimed=False,journal_claimed=False,
        scope='Actual exclusive bootstrap journal; not a synthetic request/accept/result')
    try:
        for path in (FROZEN/'gz01',FROZEN/'rl04',FROZEN/'rl02',FROZEN/'rl01',
                FROZEN/'src/multi_robot_exploration'):
            sys.path.insert(0,str(path))
        import headquarters as frozen
        original_path=frozen.Path
        original_spin=frozen.rclpy.spin
        frozen.Path=owned_path_type(directory,journal,state)
        try:
            frozen.rclpy.spin=observed_spin(original_spin,directory,state)
            return frozen.main()
        finally:
            frozen.rclpy.spin=original_spin
            frozen.Path=original_path
    finally:
        journal.close()
        state.update(closed=journal.closed,finished_monotonic_ns=time.monotonic_ns())
        with (directory/'bootstrap-state.json').open('x') as stream:json.dump(state,stream)


if __name__=='__main__':main()
