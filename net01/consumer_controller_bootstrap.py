"""Opt-in consumer provenance + fixed-startup over existing graceful owner."""
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def main():
    from execution_profile import load_profile
    profile = load_profile(os.environ.get('NET01_EXECUTION_PROFILE'))
    if profile is None or profile.get('consumer_trace') != 'hq-consumer-trace-v1':
        raise ValueError('Consumer bootstrap requires its explicit common execution profile')
    for path in (REPO / 'workspace/gz01', REPO / 'workspace/rl04',
                 REPO / 'workspace/rl02', REPO / 'workspace/rl01',
                 REPO / 'workspace/src/multi_robot_exploration',
                 REPO / 'net01e/controller'):
        sys.path.insert(0, str(path))
    import headquarters as frozen
    import graceful_controller_bootstrap as graceful
    from consumer_trace import metadata_executor, traced_headquarters
    from fixed_startup import install_startup_gate
    original_class, original_spin_factory = frozen.GZHeadquarters, graceful.make_graceful_spin

    def spin_factory(directory):
        spin = original_spin_factory(directory)
        def traced_spin(node, executor=None):
            if executor is not None:
                raise ValueError('Consumer profile owns exactly one HQ executor')
            executor = metadata_executor(node)
            try:
                return spin(node, executor=executor)
            finally:
                executor.shutdown(timeout_sec=0)
        return traced_spin

    frozen.GZHeadquarters = traced_headquarters(original_class,
        startup=lambda node: install_startup_gate(node, profile))
    graceful.make_graceful_spin = spin_factory
    try:
        return graceful.main()
    finally:
        graceful.make_graceful_spin = original_spin_factory
        frozen.GZHeadquarters = original_class


if __name__ == '__main__':
    main()
