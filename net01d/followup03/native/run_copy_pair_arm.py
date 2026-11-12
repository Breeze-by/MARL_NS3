"""One root-admitted fixed native stream arm; reuses the original runner unchanged."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[3]
BASE=REPO/'net01d/followup03'
WS=REPO.parents[1]
REFERENCE=WS/'net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp'
CANDIDATE=WS/'net-01d/native-copy-cost-followup03/driver-out/net01-payload-tcp'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--arm',choices=('reference','candidate'),required=True)
    args=parser.parse_args()
    for key in ('LD_PRELOAD','LD_AUDIT','LD_PROFILE','LD_PROFILE_OUTPUT'):os.environ.pop(key,None)
    os.environ['LD_LIBRARY_PATH']=str(WS/'net-01d/ns3-lto-portable-followup02/build/lib')
    source=REPO/'net01d/followup02/native/run_native_tcp.py'
    spec=importlib.util.spec_from_file_location('copy_original_runner',source)
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    runner.BASE=BASE
    native=REFERENCE if args.arm=='reference' else CANDIDATE
    name='ntcp-copy-r1' if args.arm=='reference' else 'ntcp-copy-c1'
    return runner.main('stream-01',native,output_name=name,native_transport='tcp-mtu-v2')

if __name__=='__main__':raise SystemExit(main())
