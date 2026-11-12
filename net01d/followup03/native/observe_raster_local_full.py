"""Inert A1 originalPACE10+raster configuration ablation; no separate clock lane."""
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'net01d/followup02/native'))
from observe_lto_full import main as observe_full
BASE=REPO/'net01d/followup03'

def main():
    (BASE/'evidence').mkdir(exist_ok=True)
    return observe_full(BASE/'TCP_RASTER_LOCAL_FULL_ADMISSION.json',BASE/'evidence/tcp-raster-local-01-loader')

if __name__=='__main__':raise SystemExit(main())
