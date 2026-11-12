"""Explicit pace10 admission; reuse the original one-time LTO load observer."""
from observe_lto_full import main as observe_full
from observe_lto_pair import BASE


def main():
    return observe_full(BASE/'TCP_PACE10_FULL_ADMISSION.json',BASE/'evidence/tcp-pace10-01-loader')


if __name__=='__main__':raise SystemExit(main())
