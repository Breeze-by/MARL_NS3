"""NET-01E common-controller entry, retaining the original one-case host owner."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ready', type=Path, required=True)
    args = parser.parse_args()
    ready = json.loads(args.ready.read_text())
    network = ready['network']
    if network.get('controller_exit_adapter') != 'net01e-graceful-v1':
        raise ValueError('NET-01E requires the same explicit graceful controller adapter in every arm')
    for name in ('graceful_controller_bootstrap.py', 'graceful_spin.py', 'GRACEFUL_ADMISSION.json', 'host_run.py'):
        key = '../net01e/controller/' + name
        expected = network['adapter_sha256'][key]
        if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Reviewed NET-01E controller source changed: ' + name)
    admission = json.loads((HERE / 'GRACEFUL_ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True or admission['production_activation_allowed'] is not True:
        raise ValueError('NET-01E production controller activation has not been admitted')
    sys.path.insert(0, str(REPO / 'net01'))
    import host_run as original_host
    return original_host.main()


if __name__ == '__main__':
    raise SystemExit(main())
