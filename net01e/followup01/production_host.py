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
    admission = json.loads((HERE / 'PRODUCTION_ADMISSION.json').read_text())
    if not admission['execution_authorized'] or not admission['production_activation_allowed']:
        raise ValueError('Common production activation remains unadmitted')
    if (network.get('raw_destination') is not True
            or network.get('execution_profile') != admission['execution_profile']
            or network.get('controller_exit_adapter') != admission['controller_exit_adapter']):
        raise ValueError('Every new arm requires the same explicit raw/pace20/graceful version')
    keys = ['../net01e/followup01/' + name for name in
        ('production_gateway.py', 'production_host.py', 'PRODUCTION_ADMISSION.json', 'raw_destination_wire.py')]
    keys.append('config/EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE20_RASTER_SIMHEALTH.json')
    for key in keys:
        if hashlib.sha256((REPO / 'net01' / key).read_bytes()).hexdigest() != network['adapter_sha256'][key]:
            raise ValueError('Common production source/config changed: ' + key)
    # Exec keeps the original host as __main__; importing another host_run
    # module would collide with the controller host's import of net01.host_run.
    os.execv(sys.executable, [sys.executable, '-B', str(REPO / 'net01e/controller/host_run.py'),
        '--ready', str(args.ready.resolve())])


if __name__ == '__main__':
    main()
