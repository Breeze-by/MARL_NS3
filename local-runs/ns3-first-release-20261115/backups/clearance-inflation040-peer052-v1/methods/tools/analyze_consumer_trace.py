"""Join measured same-topic DDS publication candidates; never guess identities."""
import argparse
from bisect import bisect_left, bisect_right
from collections import Counter
import json
from pathlib import Path


def publication_candidates(take, publications):
    metadata = take.get('metadata')
    stamp = None if metadata is None else metadata.get('source_timestamp')
    if stamp is None or stamp <= 0:
        return dict(status='UNKNOWN_NO_MEASURED_SOURCE_TIMESTAMP', candidates=[])
    matches = [row for row in publications
        if row['gateway_publication_topic'] == take['topic'] and
           row['publish_before_realtime_ns'] <= stamp <= row['publish_after_realtime_ns']]
    status = ('UNIQUE_OBSERVED_PUBLICATION_CANDIDATE' if len(matches) == 1 else
              'UNKNOWN_NO_PUBLICATION_CANDIDATE' if not matches else
              'AMBIGUOUS_MULTIPLE_PUBLICATION_CANDIDATES')
    return dict(status=status, candidates=matches)


class PublicationIndex:
    """Prune impossible intervals; the original matcher remains authoritative."""
    def __init__(self, publications):
        self.topics = {}
        for order, row in enumerate(publications):
            self.topics.setdefault(row['gateway_publication_topic'], []).append((order, row))
        for topic, entries in self.topics.items():
            entries.sort(key=lambda item: item[1]['publish_before_realtime_ns'])
            starts, maximum_ends = [], []
            maximum_end = -1
            for _, row in entries:
                starts.append(row['publish_before_realtime_ns'])
                maximum_end = max(maximum_end, row['publish_after_realtime_ns'])
                maximum_ends.append(maximum_end)
            self.topics[topic] = entries, starts, maximum_ends

    def possible(self, take):
        metadata = take.get('metadata')
        stamp = None if metadata is None else metadata.get('source_timestamp')
        if stamp is None or stamp <= 0 or take['topic'] not in self.topics:
            return []
        entries, starts, maximum_ends = self.topics[take['topic']]
        stop = bisect_right(starts, stamp)
        begin = bisect_left(maximum_ends, stamp, 0, stop)
        # Preserve original publication order, including duplicate/overlap rows.
        return [row for _, row in sorted(entries[begin:stop], key=lambda item: item[0])]


def analyze(case):
    controller = case / 'controller'
    rows = [json.loads(line) for line in (controller / 'consumer-trace.jsonl').read_text().splitlines()]
    by_id = {row['event_id']: row for row in rows}
    gateway = json.loads((case / 'network-gateway.json').read_text())
    publications = [row for row in gateway['topics']['C']['delivered']
                    if 'gateway_publication_topic' in row]
    publication_index = PublicationIndex(publications)
    takes = {}
    statuses = Counter()
    for take in rows:
        if take['kind'] != 'hq_native_take':
            continue
        if take['topic'] in ('/merge_map', '/peer_keepout_state'):
            match = dict(status='C_LOCAL_DERIVED_PUBLICATION_NOT_GATEWAY_UPLINK_PUBLISH', candidates=[])
        else:
            match = publication_candidates(take, publication_index.possible(take))
        takes[take['event_id']] = match
        statuses[match['status']] += 1
    uses = []
    for use in rows:
        if use['kind'] != 'hq_policy_use':
            continue
        sources = {}
        for role, callback_id in use['source_callback_refs'].items():
            callback = by_id[callback_id]
            source = dict(callback_event_id=callback_id, callback_kind=callback['kind'],
                          callback_begin=callback['begin'], callback_end=callback['end'])
            if callback['kind'] == 'hq_input_callback':
                take_id = callback['take_event_id']
                source.update(topic=callback['topic'], receipt_seq=callback['receipt_seq'],
                    take_event_id=take_id, generated_sim_ns=callback['generated_sim_ns'],
                    generated_time_status=callback['generated_time_status'],
                    header_stamp_ns=callback['header_stamp_ns'],
                    header_stamp_semantics=callback['header_stamp_semantics'],
                    callback_to_policy_use_sim_ns=use['begin']['sim_ns'] - callback['begin']['sim_ns'],
                    callback_to_policy_use_monotonic_ns=use['begin']['monotonic_ns'] - callback['begin']['monotonic_ns'],
                    wire_match=takes.get(take_id, dict(status='UNKNOWN_NO_TAKE', candidates=[])))
                if 'generated_sim' in callback:
                    source['generated_sim'] = callback['generated_sim']
            sources[role] = source
        uses.append(dict(policy_use_event_id=use['event_id'], decision_id=use['decision_id'],
                         map_version=use['map_version'], begin=use['begin'], end=use['end'],
                         observation_event_id=use['observation_event_id'],
                         source_ref_scope=use['source_ref_scope'], sources=sources,
                         original_observation_read_records=[by_id[ref] for ref in
                             by_id[use['observation_event_id']]['original_read_event_ids']]))
    return dict(schema='consumer-chain-analysis-v1', take_match_counts=dict(statuses), policy_uses=uses,
        first_decision=json.loads((controller / 'consumer-trace-summary.json').read_text()),
        semantics='Unique observed candidate is measured matching, not inferred publisher generation or proof of TF publication identity; zero/multiple candidates remain unresolved. Local HQ derived-map receipt is separate from the central Gateway T95 evaluation capture.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.case)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
