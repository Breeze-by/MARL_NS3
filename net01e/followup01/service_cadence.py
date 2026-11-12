"""Read saved collect03 only; quantify a shared prefault TF service interval.

Observed take cycles are not SDK waitset rebuild boundaries. No new ROS run.
"""
import json
import argparse
import math
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CASE = REPO/'net01e/replay/collect-03'
OUT = Path(__file__).resolve().parent


def summary(values):
    values = sorted(values)
    if not values:
        return dict(n=0)
    return dict(n=len(values), min=values[0], mean=sum(values)/len(values),
                median=values[(len(values)-1)//2], p95=values[math.ceil(.95*len(values))-1], max=values[-1])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,default=CASE)
    parser.add_argument('--output',type=Path,default=OUT/'SERVICE_CADENCE.json')
    args=parser.parse_args(); case=args.case
    saved = json.loads((case/'take-analysis.json').read_text())
    source = json.loads((case/'source/result.json').read_text())['inputs']
    gateway = json.loads((case/'gateway/network-gateway.json').read_text())
    cutoff = min(int(row['monotonic']*1e9) for row in saved['first_fault'].values() if row)
    published = [row for row in source if row['state']=='PUBLISHED' and row['phase']=='normal'
                 and row['flow'] in (23,43,63) and row['after_monotonic_ns']<cutoff]
    begin = min(row['before_monotonic_ns'] for row in published)
    span = (cutoff-begin)/1e9
    takes = sorted((row for row in saved['pairs'] if begin<=row['take_before_monotonic_ns']<cutoff),
                   key=lambda row: row['take_before_monotonic_ns'])
    flows = {}
    for flow in (23,43,63):
        src = [row for row in published if row['flow']==flow]
        received = [row for row in takes if row['flow']==flow]
        points = [row['take_before_monotonic_ns'] for row in received]
        intervals = [(b-a)/1e6 for a,b in zip(points, points[1:])]
        x = [(row['take_before_monotonic_ns']-begin)/1e9 for row in received]
        y = [row['metrics']['RMW_received_to_take_before_ms'] for row in received]
        mx=sum(x)/len(x); my=sum(y)/len(y)
        slope=sum((a-mx)*(b-my) for a,b in zip(x,y))/sum((a-mx)**2 for a in x)
        edges = Counter(tuple((e['frame_id'],e['child_frame_id']) for e in row['original_tf_edges']) for row in src)
        flows[str(flow)] = dict(actual_publications=len(src), actual_takes=len(received),
            shared_window_lambda_wall_hz=len(src)/span, shared_window_mu_wall_hz=len(received)/span,
            publication_first_last_wall_hz=(len(src)-1)/((src[-1]['after_monotonic_ns']-src[0]['after_monotonic_ns'])/1e9),
            take_first_last_wall_hz=(len(points)-1)/((points[-1]-points[0])/1e9),
            source_first_gap_ms=(src[0]['before_monotonic_ns']-begin)/1e6,
            source_last_to_cut_ms=(cutoff-src[-1]['after_monotonic_ns'])/1e6,
            take_first_gap_ms=(points[0]-begin)/1e6, take_last_to_cut_ms=(cutoff-points[-1])/1e6,
            pub_minus_take_count=len(src)-len(received),
            same_flow_take_interval_ms=summary(intervals),
            received_to_take_ms=summary(y), queue_age_first_ms=y[0], queue_age_last_ms=y[-1],
            queue_age_slope_ms_per_wall_s=slope,
            take_CPU_ms=summary([row['metrics']['take_thread_CPU_ms'] for row in received]),
            actual_published_edge_groups=[dict(edges=k,count=v) for k,v in edges.items()])
    sequence=[row['flow'] for row in takes]
    triples=[tuple(sequence[i:i+3]) for i in range(0,len(sequence),3)]
    result=dict(source_case=str(case), begin_monotonic_ns=begin, cutoff_monotonic_ns=cutoff,
        shared_span_wall_s=span, take_rows=len(takes), source_publications=len(published), flows=flows,
        nonoverlap_observed_triples=[dict(flow_order=k,count=v) for k,v in Counter(triples).items()],
        adjacent_any_flow_interval_ms=summary([(b['take_before_monotonic_ns']-a['take_before_monotonic_ns'])/1e6
                                               for a,b in zip(takes,takes[1:])]),
        whole_life_progress_aggregates=gateway['dispatch_cpu_profile']['aggregates']['progress'],
        whole_life_R_wait_aggregates=gateway['dispatch_cpu_profile']['aggregates']['R']['wait'],
        whole_life_C_wait_aggregates=gateway['dispatch_cpu_profile']['aggregates']['C']['wait'],
        boundaries=['Shared interval uses actual first normal TF publication through actual first fault, all monotonic.',
            'Publication-minus-take is not exact queue depth: no per-writer/GID identity and original source cut is censored.',
            'Lambda is actual successful publish count, not the planned 10sim corpus rate.',
            'Take triples/periods are observed service cycles, not exact SDK waitset refresh boundaries.',
            'Whole-life CPU/progress aggregates include startup and exit, so cannot be divided by the prefault span.',
            'Reported received timestamp is not independently established earliest DDS arrival.'])
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if not k.startswith('whole_life')},indent=2))


if __name__=='__main__':
    main()
