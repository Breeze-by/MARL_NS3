"""Common-source preflight then exec the existing graceful/original host chain."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ready', type=Path, required=True)
    args = parser.parse_args()
    network = json.loads(args.ready.read_text())['network']
    sys.path.insert(0,str(REPO/'net01'))
    from execution_profile import SIM_BUSINESS_PROFILE_FILES,FIXED_START_PROFILE_IDS,FIXED_START_ADAPTER_FILES,REPAIR120_PROFILE_ID,REPAIR_ADAPTER_FILES,REPAIR_PROFILE_IDS,COMPARISON_PROFILE_IDS,COMPARISON_ADAPTER_FILES,ROS_DELAY_PROFILE_ID,ROS_DELAY_ADAPTER_FILES
    if network.get('execution_profile') in SIM_BUSINESS_PROFILE_FILES:
        # A new per-case source binding replaces historical experiment admission.
        expected_profile=network['execution_profile']
        expected_controller='net01e-graceful-v1'
        keys=['host_run.py','tools/packet_hub.py','execution_profile.py','business_peer.py','bound_peer.py','action_wire.py','gateway.py',
            'boot_network.py','run_network_case.py','time_control_state.py','time_control_runtime.py',
            'config/'+SIM_BUSINESS_PROFILE_FILES[expected_profile]]
        if expected_profile in FIXED_START_PROFILE_IDS:keys += list(FIXED_START_ADAPTER_FILES)
        if expected_profile in REPAIR_PROFILE_IDS:
            keys += list(REPAIR_ADAPTER_FILES)+['../net01e/followup02/static_footprint_launch.py']
        if expected_profile in COMPARISON_PROFILE_IDS:keys += list(COMPARISON_ADAPTER_FILES)
        if expected_profile == ROS_DELAY_PROFILE_ID:keys += list(ROS_DELAY_ADAPTER_FILES)
        if network.get('navigation_clearance') is not None:
            keys += ['clearance_tuning.py','clearance_tuning_launch.py']
        keys += ['../net01e/followup01/'+name for name in
            ('production_gateway.py','production_host.py','raw_destination_wire.py')]
    else:
        admission = json.loads((HERE / 'PRODUCTION_ADMISSION.json').read_text())
        if not admission['execution_authorized'] or not admission['production_activation_allowed']:
            raise ValueError('Common production activation remains unadmitted')
        expected_profile=admission['execution_profile']
        expected_controller=admission['controller_exit_adapter']
        keys = ['../net01e/followup01/' + name for name in
            ('production_gateway.py', 'production_host.py', 'PRODUCTION_ADMISSION.json', 'raw_destination_wire.py')]
        keys.append('config/EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE20_RASTER_SIMHEALTH.json')
    if (network.get('raw_destination') is not True
            or network.get('execution_profile') != expected_profile
            or network.get('controller_exit_adapter') != expected_controller):
        raise ValueError('Every arm requires the same explicit raw/profile/graceful version')
    for key in keys:
        if hashlib.sha256((REPO / 'net01' / key).read_bytes()).hexdigest() != network['adapter_sha256'][key]:
            raise ValueError('Common production source/config changed: ' + key)
    # Exec keeps the original host as __main__; importing another host_run
    # module would collide with the controller host's import of net01.host_run.
    os.execv(sys.executable, [sys.executable, '-B', str(REPO / 'net01e/controller/host_run.py'),
        '--ready', str(args.ready.resolve())])


if __name__ == '__main__':
    main()
