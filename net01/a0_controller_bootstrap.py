"""A0-only hook over original HQ/LoggedActionClient, after exclusive journal.

No frozen source is edited. The original HQ constructor/model/arguments run
unchanged. Its executor starts only after construction, so the object hook is
installed before any original ActionClient can submit a Goal.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from controller_bootstrap import owned_path_type,observed_spin

HERE=Path(__file__).resolve().parent
FROZEN=HERE.parent/'workspace'


def main():
    if os.environ.get('NET01_DIRECT_REFERENCE')!='1' or os.environ.get('ROS_DOMAIN_ID')!='92':
        raise ValueError('A0 HQ must be explicitly admitted in direct R92')
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--run-dir',type=Path,required=True)
    args,_=parser.parse_known_args()
    directory=args.run_dir
    directory.mkdir(parents=True,exist_ok=False)
    journal=(directory/'allocation-events.jsonl').open('x',buffering=1)
    state=dict(pid=os.getpid(),created_monotonic_ns=time.monotonic_ns(),
        created_fileno=journal.fileno(),directory_claimed=False,journal_claimed=False,
        direct_reference=True,safety_hook_installed=False,
        scope='Original HQ and LoggedActionClient; external UUID-only independent safety admission')
    try:
        for path in (FROZEN/'gz01',FROZEN/'rl04',FROZEN/'rl02',FROZEN/'rl01',
                FROZEN/'src/multi_robot_exploration'):
            sys.path.insert(0,str(path))
        import headquarters as frozen
        from a0_runtime import SafetyClient,install_hq_record_hook
        original_path=frozen.Path
        original_hq=frozen.GZHeadquarters
        original_spin=frozen.rclpy.spin
        class DirectHeadquarters(original_hq):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs)
                safety=SafetyClient(Path(os.environ['NET01_A0_SAFETY_SOCKET']),int(os.environ['NET01_SESSION_ID']))
                install_hq_record_hook(self,safety)
                state['safety_hook_installed']=True
                self.record(dict(kind='a0_direct_safety_bound',sim=self.now(),
                    safety_ack_wall_s=.1,original_UUID_Goal_and_journal=True))
        frozen.Path=owned_path_type(directory,journal,state)
        frozen.GZHeadquarters=DirectHeadquarters
        try:
            frozen.rclpy.spin=observed_spin(original_spin,directory,state)
            return frozen.main()
        finally:
            frozen.rclpy.spin=original_spin
            frozen.Path=original_path
            frozen.GZHeadquarters=original_hq
    finally:
        journal.close()
        state.update(closed=journal.closed,finished_monotonic_ns=time.monotonic_ns())
        with (directory/'bootstrap-state.json').open('x') as stream:
            json.dump(state,stream)


if __name__=='__main__':
    main()
