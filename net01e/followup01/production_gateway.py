"""Inert common physical-run entry; original Gateway ownership/stop stay intact."""
import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    admission = json.loads((HERE / 'PRODUCTION_ADMISSION.json').read_text())
    if not admission['execution_authorized'] or not admission['production_activation_allowed']:
        raise RuntimeError('Inert production entry: common source pin and specific Root READY/START required')
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--execution-profile', required=True)
    selected, _ = parser.parse_known_args()
    if (os.environ.get('NET01_RAW_DESTINATION') != '1'
            or selected.execution_profile != admission['execution_profile']
            or os.environ.get('NET01_EXECUTION_PROFILE') != selected.execution_profile
            or os.environ.get('NET01_CONTROLLER_EXIT_ADAPTER') != admission['controller_exit_adapter']):
        raise ValueError('Actual production entry does not match common raw/graceful/profile selection')
    sys.path[:0] = [str(HERE), str(REPO / 'net01'), str(REPO)]
    import gateway
    from raw_destination_wire import RawDestinationTopicWire
    direct = os.environ.get('NET01_DIRECT_REFERENCE') == '1'
    if direct:
        from a0_gateway import DirectReferenceGateway
        original_factory = DirectReferenceGateway
    else:
        original_factory = gateway.Gateway
    original_wire = gateway.TopicWire
    gateway.TopicWire = RawDestinationTopicWire

    def factory(*args, **kwargs):
        node = original_factory(*args, **kwargs)
        node.record('common_raw_destination_production_entry', execution_profile=node.execution_profile['id'],
            direct_reference=direct, selected_topic_wire='RawDestinationTopicWire',
            destination_path=('not_applicable_A0_direct_DDS_no_business_wires' if direct else
                'original_validated_CDR_to_public_raw_publish_when_business_wires_installed'),
            unchanged_stop_owner='original Gateway/main/NetworkObserver; no no-motion helper')
        return node
    try:
        return gateway.main(gateway_factory=factory)
    finally:
        gateway.TopicWire = original_wire


if __name__ == '__main__':
    raise SystemExit(main())
