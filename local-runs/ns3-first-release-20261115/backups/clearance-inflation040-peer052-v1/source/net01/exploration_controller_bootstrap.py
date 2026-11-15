"""Explicit new candidate behavior over the existing traced/graceful HQ owner."""
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def main():
    from execution_profile import load_profile
    from candidate_clearance import VERSION, candidate_headquarters
    profile = load_profile(os.environ.get('NET01_EXECUTION_PROFILE'))
    if profile is None or profile.get('candidate_clearance', {}).get('id') != VERSION:
        raise ValueError('Exploration bootstrap requires the explicit new candidate baseline')
    for path in (REPO/'workspace/gz01', REPO/'workspace/rl04', REPO/'workspace/rl02',
                 REPO/'workspace/rl01', REPO/'workspace/src/multi_robot_exploration'):
        sys.path.insert(0, str(path))
    import headquarters as frozen
    import consumer_controller_bootstrap
    freshness = None
    if profile.get('source_freshness') is not None:
        from ros_delay_runtime import install_source_freshness
        freshness = install_source_freshness(profile, 'HQ')
    original = frozen.GZHeadquarters
    configured = original
    if freshness is not None:
        class ConfiguredHeadquarters(original):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.record(dict(kind='ros_delay_source_freshness', sim=self.now(), applied=freshness))
        configured = ConfiguredHeadquarters
    frozen.GZHeadquarters = candidate_headquarters(configured, profile)
    try:
        return consumer_controller_bootstrap.main()
    finally:
        frozen.GZHeadquarters = original


if __name__ == '__main__':
    main()
