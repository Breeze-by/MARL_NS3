"""Inert ARM-activation A1 Full; reuse the original single load observer."""
from pathlib import Path
import sys
import os
REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'net01d/followup02/native'))
from observe_lto_full import main as observe_full
BASE=REPO/'net01d/followup04'
def main():
    for key in ('LD_PROFILE','LD_PROFILE_OUTPUT'):os.environ.pop(key,None)
    (BASE/'evidence').mkdir(exist_ok=True)
    return observe_full(BASE/'TCP_SIMHEALTH_ARMED_LOCAL_FULL_ADMISSION.json',BASE/'evidence/tcp-arm-local-01-loader')
if __name__=='__main__':raise SystemExit(main())
