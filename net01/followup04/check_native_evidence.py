"""One small-file/stdlib check of actual RAM evidence helpers; 0Node/native/GZ."""
import argparse
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output;output.mkdir(exist_ok=False)
    source=Path(__file__).resolve().parents[1]/'tools/packet_hub.py'
    spec=importlib.util.spec_from_file_location('actual_packet_hub',source)
    hub=importlib.util.module_from_spec(spec);spec.loader.exec_module(hub)
    ram=Path('/dev/shm/net01-native-evidence-small-01');checks={}
    try:hub.prepare_native_evidence(Path('/tmp/not-net01-ram'),output/'unused')
    except ValueError:checks['non_dev_shm_path_rejected']=True
    with patch.object(hub.os,'statvfs',return_value=SimpleNamespace(f_bavail=0,f_frsize=4096)):
        try:hub.prepare_native_evidence(Path('/dev/shm/net01-native-evidence-resource-fail-01'),output/'unused')
        except RuntimeError:checks['insufficient_space_rejected_before_mkdir']=not Path('/dev/shm/net01-native-evidence-resource-fail-01').exists()
    storage=hub.prepare_native_evidence(ram,output/'native-copy')
    try:hub.prepare_native_evidence(ram,output/'unused')
    except FileExistsError:checks['owned_RAM_is_exclusive']=True
    # Explicit tiny copy fixtures, not real model records/PCAP validation.
    for n in range(4):(ram/f'wifi-{n}-0.pcap').write_bytes(b'fixture-only-not-real-PCAP'+bytes([n]))
    (ram/'configured-lock.json').write_text('{}')
    (ram/'packet-ledger.jsonl').write_text('{"kind":"transport_end"}\n')
    (ram/'control-step-trace.jsonl').write_text('{"fixture":true}\n')
    (ram/'ledger-status.json').write_text(json.dumps(dict(failed=False,attempted=1,captured=1,written=1)))
    (ram/'native-summary.json').write_text(json.dumps(dict(counts=dict(transport_end=1))))
    alive=dict(storage,destination=str(output/'must-not-copy-live'))
    try:hub.copy_native_evidence(alive,None,True)
    except RuntimeError:checks['live_child_not_copied']=not (output/'must-not-copy-live').exists()
    hub.copy_native_evidence(storage,0,True)
    checks['every_small_file_exact_after_exit']=all((ram/name).read_bytes()==(output/'native-copy'/name).read_bytes() for name in storage['source_files']) and storage['complete']
    failed=dict(storage,destination=str(output/'native-copy'))
    try:hub.copy_native_evidence(failed,0,True)
    except FileExistsError:checks['existing_destination_not_overwritten_and_error_recorded']=failed['complete'] is False and 'error' in failed and all((ram/name).read_bytes()==(output/'native-copy'/name).read_bytes() for name in storage['source_files'])
    (ram/'control-step-trace.jsonl').unlink()
    incomplete=dict(storage,destination=str(output/'incomplete-copy'))
    try:hub.copy_native_evidence(incomplete,0,True)
    except RuntimeError:checks['missing_required_artifact_FAIL_retains_partial_copy_and_RAM']=incomplete['complete'] is False and ram.exists() and (output/'incomplete-copy').exists()
    result=dict(scope='Actual helpers, tiny explicitly synthetic files only; 0Node/native/ROS/GZ, not model equality or timing qualification',checks=checks,status='PASS' if len(checks)==7 and all(checks.values()) else 'FAIL',success=storage,copy_failure=failed,incomplete=incomplete,RAM_source_preserved=str(ram))
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    return int(result['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())
