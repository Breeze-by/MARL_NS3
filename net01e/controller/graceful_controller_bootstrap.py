"""Inert proposed entry point over original A0/other-arm bootstrap and finally."""
import json
import os
from pathlib import Path
import sys

from graceful_spin import make_graceful_spin


def main():
    admission = json.loads(Path(__file__).with_name('GRACEFUL_ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True or admission['production_activation_allowed'] is not True:
        raise RuntimeError('Inert candidate: source review, regression admission and Root START required')
    import argparse
    import rclpy

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--run-dir', type=Path, required=True)
    args, _ = parser.parse_known_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'net01'))
    if os.environ.get('NET01_DIRECT_REFERENCE') == '1':
        import a0_controller_bootstrap as original_bootstrap
    else:
        import controller_bootstrap as original_bootstrap
    original_spin = rclpy.spin
    rclpy.spin = make_graceful_spin(args.run_dir)
    try:
        return original_bootstrap.main()
    finally:
        rclpy.spin = original_spin


if __name__ == '__main__':
    main()
