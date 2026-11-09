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

HERE=Path(__file__).resolve().parent
FROZEN=HERE.parent/"workspace"


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
        frozen.Path=owned_path_type(directory,journal,state)
        try:return frozen.main()
        finally:frozen.Path=original_path
    finally:
        journal.close()
        state.update(closed=journal.closed,finished_monotonic_ns=time.monotonic_ns())
        with (directory/'bootstrap-state.json').open('x') as stream:json.dump(state,stream)


if __name__=='__main__':main()
