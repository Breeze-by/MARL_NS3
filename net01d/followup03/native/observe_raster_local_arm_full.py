"""Inert original A1 Full after fixture ARM lifecycle repair; same raster-only profile."""
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'net01d/followup02/native'))
from observe_lto_full import main as observe_full
BASE=REPO/'net01d/followup03'

def main():
    (BASE/'evidence').mkdir(exist_ok=True)
    return observe_full(BASE/'TCP_RASTER_LOCAL_ARM_FULL_ADMISSION.json',BASE/'evidence/tcp-raster-local-arm-01-loader')

if __name__=='__main__':raise SystemExit(main())
