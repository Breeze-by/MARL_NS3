"""Inert common physical-run entry; original Gateway ownership/stop stay intact."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
POSTSTOP_EXIT_REVISION = 'comparison40-v3-poststop-explicit-exit-v1'


def poststop_success(node, direct):
    """Use only the original close/persist evidence; never repair a failed close."""
    directory = node.directory
    try:
        closed = json.loads((directory/'network-gateway-resources-closed.json').read_text())
        saved = json.loads((directory/'network-gateway-saved.json').read_text())
        phases = [json.loads(line) for line in
            (directory/'network-gateway-close-phases.jsonl').read_text().splitlines()]
        safety = json.loads((directory/'a0-direct-safety-saved.json').read_text()) if direct else None
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    identity = dict(pid=os.getpid(), session_id=node.session_id, case=str(directory.resolve()))
    expected = ['close_begin', 'resources_closed', 'persist_begin', 'persist_end',
        'close_return', 'main_return']
    if ([row.get('phase') for row in phases] != expected
            or any(any(row.get(key) != value for key, value in identity.items()) for row in phases)
            or phases[1] != closed or closed.get('safe_closed') is not True
            or phases[-2].get('clean') is not True or phases[-1].get('exit_code') != 0):
        return False
    stamps = [row['monotonic_ns'] for row in phases]
    if stamps != sorted(stamps):
        return False
    cleanup = node.cleanup
    hub = cleanup.get('hub_shutdown', {})
    sampler = cleanup.get('main_thread_sampler')
    confirmations = cleanup.get('action_confirmation_states')
    if (node.failure is not None or saved.get('saved') is not True or saved.get('failure') is not None
            or saved.get('cleanup') != cleanup or closed.get('cleanup') != cleanup
            or cleanup.get('resources_destroyed') is not True
            or cleanup.get('end_frame_flushed') is not True
            or cleanup.get('executor_shutdown') != [True, True]
            or cleanup.get('unresolved_C_RPC') != [] or cleanup.get('unresolved_R_RPC') != []
            or any(cleanup.get('unresolved_local_cleanup_futures', {'missing': 1}).values())
            or hub.get('peer_eof') is not True or 'error' in hub
            or (sampler is not None and (not sampler['joined'] or sampler['failure'] is not None))
            or (confirmations is not None and any(state['waiting'] or state['unconfirmed']
                for state in (confirmations['C'], *confirmations['R'].values())))):
        return False
    return (not direct or (safety.get('saved') is True and safety.get('direct_reference') is True
        and safety.get('business_wires_installed') is False
        and safety.get('registered_owned_unknown_or_active') == 0 and safety.get('safety_connections') == 0))


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--execution-profile', required=True)
    selected, _ = parser.parse_known_args()
    sys.path.insert(0,str(REPO/'net01'))
    from execution_profile import SIM_BUSINESS_PROFILE_FILES,FIXED_START_PROFILE_IDS,COMPARISON_PROFILE_IDS,COMPARISON40_V3_PROFILE_ID,ROS_DELAY_PROFILE_ID,load_profile
    if selected.execution_profile in SIM_BUSINESS_PROFILE_FILES:
        expected_profile=selected.execution_profile
        expected_controller='net01e-graceful-v1'
    else:
        admission = json.loads((HERE / 'PRODUCTION_ADMISSION.json').read_text())
        if not admission['execution_authorized'] or not admission['production_activation_allowed']:
            raise RuntimeError('Inert production entry: specific case admission required')
        expected_profile=admission['execution_profile']
        expected_controller=admission['controller_exit_adapter']
    if (os.environ.get('NET01_RAW_DESTINATION') != '1'
            or selected.execution_profile != expected_profile
            or os.environ.get('NET01_EXECUTION_PROFILE') != selected.execution_profile
            or os.environ.get('NET01_CONTROLLER_EXIT_ADAPTER') != expected_controller):
        raise ValueError('Actual production entry does not match common raw/graceful/profile selection')
    sys.path[:0] = [str(HERE), str(REPO / 'net01'), str(REPO)]
    import gateway
    from raw_destination_wire import RawDestinationTopicWire
    direct = os.environ.get('NET01_DIRECT_REFERENCE') == '1'
    comparison = selected.execution_profile in COMPARISON_PROFILE_IDS
    delay_profile = selected.execution_profile == ROS_DELAY_PROFILE_ID
    explicit_poststop_exit = selected.execution_profile in (COMPARISON40_V3_PROFILE_ID, ROS_DELAY_PROFILE_ID)
    retained = []
    if direct:
        from a0_gateway import DirectReferenceGateway
        if comparison:
            from comparison_direct_gateway import ComparisonDirectReferenceGateway
            original_factory=ComparisonDirectReferenceGateway
        else:
            original_factory = DirectReferenceGateway
    else:
        if delay_profile:
            from ros_delay_gateway import ROSDelayGateway
            original_factory = ROSDelayGateway
        else:
            original_factory = gateway.Gateway
    original_wire = gateway.TopicWire
    original_hub = gateway.HubClient
    if comparison:
        from comparison_measurement import ComparisonHubClient
        from comparison_topic_wire import ComparisonTopicWire
        gateway.HubClient=ComparisonHubClient
        gateway.TopicWire=ComparisonTopicWire
    elif selected.execution_profile in FIXED_START_PROFILE_IDS:
        from consumer_topic_wire import ConsumerTraceTopicWire
        gateway.TopicWire = ConsumerTraceTopicWire
    else:
        gateway.TopicWire = RawDestinationTopicWire

    def factory(*args, **kwargs):
        freshness = None
        if delay_profile:
            from ros_delay_runtime import install_source_freshness
            freshness = install_source_freshness(load_profile(selected.execution_profile), 'Gateway_C91_R92' if not direct else 'Gateway_A0_R92')
        node = original_factory(*args, **kwargs)
        if freshness is not None and 'receipt_freshness_applied' in freshness:
            freshness['receipt_freshness_applied']['applicable_instance_limits']={str(robot):dict(
                health_receipt_limit_sim_s=stop.guard.health_receipt_limit_s,
                mask_receipt_limit_sim_s=stop.guard.mask_receipt_limit_s,
                health_receipt_limit_ns=stop.guard.health_receipt_limit_ns,
                mask_receipt_limit_ns=stop.guard.mask_receipt_limit_ns,
                integer_ros_receipt=stop.guard.integer_sim_receipt)
                for robot,stop in node.guards.items()}
        if explicit_poststop_exit:
            # Keep the original local node alive through Gateway.main's return.
            retained.append(node)
        if comparison:
            from comparison_measurement import install_gateway_takes
            install_gateway_takes(node)
        node.record('common_raw_destination_production_entry', execution_profile=node.execution_profile['id'],
            direct_reference=direct, selected_topic_wire=gateway.TopicWire.__name__,
            destination_path=('not_applicable_A0_direct_DDS_no_business_wires' if direct else
                'original_validated_CDR_to_public_raw_publish_when_business_wires_installed'),
            unchanged_stop_owner='original Gateway/main/NetworkObserver; no no-motion helper',
            **({'source_freshness_applied': freshness} if freshness is not None else {}))
        return node
    try:
        code = gateway.main(gateway_factory=factory)
    finally:
        gateway.TopicWire = original_wire
        gateway.HubClient = original_hub
    if explicit_poststop_exit and code == 0 and len(retained) == 1 and poststop_success(retained[0], direct):
        node = retained[0]
        sys.stdout.flush()
        sys.stderr.flush()
        with (node.directory/'network-gateway-production-exit.json').open('x') as stream:
            json.dump(dict(revision=POSTSTOP_EXIT_REVISION, phase='explicit_exit_intent',
                actual_main_return_code=code, original_factories_restored=True,
                stdout_stderr_flushed=True, pid=os.getpid(), session_id=node.session_id,
                case=str(node.directory.resolve()), execution_profile=selected.execution_profile,
                monotonic_ns=time.monotonic_ns(), realtime_ns=time.time_ns(),
                scope='Post-close process exit only; original resources and persistence succeeded'), stream)
        os._exit(0)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
