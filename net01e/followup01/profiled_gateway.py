"""Explicit common profile selection around original Gateway construction.

The sealed collector retains its original CLI. This child consumes the new
selection and passes it to the original Gateway constructor, then reuses the
same active probe and original collector. No hidden profile alias is installed.
"""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    sys.path[:0] = [str(HERE), str(REPO/'net01'), str(REPO)]
    from execution_profile import CONTROLLED_PROFILE_IDS
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--execution-profile',choices=CONTROLLED_PROFILE_IDS,required=True)
    parser.add_argument('--raw-destination',action='store_true')
    selected,remaining=parser.parse_known_args()
    admission=json.loads((HERE/'PACE20_ADMISSION.json').read_text())
    if (not admission['execution_authorized'] or selected.execution_profile!=admission['execution_profile']
            or selected.raw_destination!=admission['raw_destination']):
        raise RuntimeError('Explicit common profile requires matching Root unique START')
    import gateway
    import gateway_active_probe
    from raw_destination_wire import RawDestinationTopicWire
    original_gateway=gateway.Gateway; original_wire=gateway.TopicWire
    class ProfiledGateway(original_gateway):
        def __init__(self,*args,**kwargs):
            inherited=kwargs['execution_profile']
            kwargs['execution_profile']=selected.execution_profile
            super().__init__(*args,**kwargs)
            self.record('explicit_common_execution_profile',
                selected_profile=selected.execution_profile,
                inherited_collector_profile=inherited,
                actual_profile=self.execution_profile,
                raw_destination=selected.raw_destination)
    gateway.Gateway=ProfiledGateway
    if selected.raw_destination:
        gateway.TopicWire=RawDestinationTopicWire
    original_argv=sys.argv
    sys.argv=[sys.argv[0],*remaining]
    try:
        return gateway_active_probe.main()
    finally:
        sys.argv=original_argv
        gateway.Gateway=original_gateway
        gateway.TopicWire=original_wire


if __name__=='__main__':
    raise SystemExit(main())
