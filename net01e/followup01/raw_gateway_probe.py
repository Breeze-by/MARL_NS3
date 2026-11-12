"""Child-only destination publication candidate with original active RAM probe."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    admission = json.loads((HERE/'RAW_REPLAY_ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:
        raise RuntimeError('Inert raw destination regression: Root unique START required')
    sys.path[:0] = [str(HERE), str(REPO/'net01'), str(REPO)]
    import gateway
    from raw_destination_wire import RawDestinationTopicWire
    import gateway_active_probe
    original = gateway.TopicWire
    gateway.TopicWire = RawDestinationTopicWire
    try:
        return gateway_active_probe.main()
    finally:
        gateway.TopicWire = original


if __name__=='__main__':
    raise SystemExit(main())
