"""Offline ROS field-value comparison, never rclpy.init or a ROS node.

Reads only new extracted CDR/source/wire artifacts. Original raw CDR hashes
remain separate from semantic fingerprints; no handwritten CDR parser.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time

REPO=Path(__file__).resolve().parents[2]


def normalize(value):
    # Generated message equality treats signed floating zero as equal.
    # No rounding, tolerances, truncation or omitted fields.
    if isinstance(value,float) and value==0:return 0.0
    if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [normalize(v) for v in value]
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(exist_ok=False)
    sys.path[:0]=[str(REPO/'net01'),str(REPO)]
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.convert import message_to_ordereddict
    from topic_wire import flows
    specs=flows(runtime=True)
    source=json.loads((args.case/'source/result.json').read_text())['inputs']
    tail_result=json.loads((args.case/'source/tail-result.json').read_text())
    tail=tail_result['inputs'];tail_corpus=Path(tail_result['corpus'])
    if not tail_corpus.is_absolute():tail_corpus=REPO/tail_corpus
    wire=[json.loads(line) for line in (args.case/'gateway/wire-records.jsonl').read_text().splitlines()]
    begin=time.monotonic_ns();counts=Counter();source_sem=Counter();wire_sem=Counter()
    source_raw=Counter();wire_raw=Counter();source_hashes=defaultdict(set);wire_hashes=defaultdict(set)
    per_row=[];zero_keys=set();expected_flows={row['flow'] for row in source+tail}
    def fingerprints(flow,body):
        message=deserialize_message(body,specs[flow]['cls'])
        fields=normalize(message_to_ordereddict(message))
        canonical=json.dumps(fields,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
        typename=specs[flow]['cls'].__module__+'.'+specs[flow]['cls'].__name__
        semantic=hashlib.sha256(typename.encode()+b'\n'+canonical).hexdigest()
        raw=hashlib.sha256(body).hexdigest()
        return semantic,raw,(flow%20==6 and message==specs[flow]['cls']())
    with (REPO/'net01e/replay/corpus-01/bodies.bin').open('rb') as main_reader, \
            (tail_corpus/'bodies.bin').open('rb') as tail_reader, \
            (args.case/'gateway/wire-bodies.bin').open('rb') as wire_reader:
        for phase,rows,reader in (('main',source,main_reader),('tail',tail,tail_reader)):
            for row in rows:
                counts[phase+'_planned']+=1
                if row['state']!='PUBLISHED':
                    counts[phase+'_'+row['state']]+=1;continue
                offset=row.get('original_tail_body_offset',row['body_offset']) if phase=='tail' else row['body_offset']
                reader.seek(offset);body=reader.read(row['body_bytes'])
                semantic,raw,zero=fingerprints(row['flow'],body)
                key=row['flow'],semantic;source_sem[key]+=1;source_raw[(row['flow'],raw)]+=1
                source_hashes[key].add(raw);counts[phase+'_published_decoded']+=1
                if zero:zero_keys.add(key)
                per_row.append(dict(side='source',phase=phase,ordinal=row['ordinal'],flow=row['flow'],
                    source_phase=row['phase'],
                    source_record_id=row['source_record_id'],raw_CDR_SHA256=raw,semantic_SHA256=semantic))
        for row in wire:
            flow=row['flow']
            # Bound masks are envelopes, Action flows use generated Action
            # service types, and link frames are not ROS TopicWire CDR.
            if flow not in specs or flow in (30,50,70):
                counts['wire_non_TopicWire_CDR_excluded']+=1;continue
            wire_reader.seek(row['body_offset']);body=wire_reader.read(row['body_bytes'])
            semantic,raw,zero=fingerprints(flow,body)
            key=flow,semantic;wire_sem[key]+=1;wire_raw[(flow,raw)]+=1
            wire_hashes[key].add(raw);counts['wire_topic_decoded']+=1
            if zero:zero_keys.add(key)
            per_row.append(dict(side='wire',ordinal=row['ordinal'],flow=flow,
                raw_CDR_SHA256=raw,semantic_SHA256=semantic))
    flow_result={}
    for flow in sorted(expected_flows):
        src=Counter({k:v for k,v in source_sem.items() if k[0]==flow})
        dst=Counter({k:v for k,v in wire_sem.items() if k[0]==flow})
        sr=Counter({k:v for k,v in source_raw.items() if k[0]==flow})
        dr=Counter({k:v for k,v in wire_raw.items() if k[0]==flow})
        flow_result[str(flow)]=dict(source_published=sum(src.values()),wire_captured=sum(dst.values()),
            semantic_content_units_without_wire_match=sum((src-dst).values()),
            extra_wire_semantic_content_units=sum((dst-src).values()),
            raw_CDR_units_without_wire_match=sum((sr-dr).values()),
            semantic_groups_with_disjoint_raw_CDR_hashes=sum(not(source_hashes[k]&wire_hashes[k]) for k in src if k in dst),
            known_Twist_zero_source_units=sum(v for k,v in src.items() if k in zero_keys),
            known_Twist_zero_wire_units=sum(v for k,v in dst.items() if k in zero_keys),
            attribution='Extra LocalStop zero writers: semantic multiset is not exact publisher/ID attribution' if flow%20==6
                        else 'Fixture known source role; repeated semantic values still do not identify each original packet')
    result=dict(case=str(args.case),counts=dict(counts),flows=flow_result,
        fields_API='rosidl_runtime_py.convert.message_to_ordereddict; no_arr/no_str/truncation disabled defaults',
        processing_wall_ns=time.monotonic_ns()-begin,
        semantic_fingerprint='All generated fields plus generated type; signed floating zero normalized, no numeric tolerance',
        published_source_to_wire_semantic_deficit=sum(v['semantic_content_units_without_wire_match'] for v in flow_result.values()),
        boundaries=['No ROS initialization/node/model/simulator/network run; saved extracted and wire bodies only.',
            'Semantic equality is distinct from raw CDR equality; both hashes retained per row.',
            'Published-source and wire multisets do not establish unique repeated-content IDs or source DDS writer GID.',
            'Twist has additional true LocalStop zero writers; zeros cannot be uniquely attributed to the source.',
            'Main and closing-tail semantic counters are jointly reconciled to avoid inventing phase identity for repeated values.',
            'Wire capture is not network delivery or final ROS consumption; no wireless loss PASS follows.',
            'Bound-mask envelopes/Action/link frames excluded from this TopicWire six-class analysis.'])
    (args.output/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
    with (args.output/'fingerprints.jsonl').open('x') as stream:
        for row in per_row:stream.write(json.dumps(row)+'\n')
    print(json.dumps(dict(counts=result['counts'],semantic_deficit=result['published_source_to_wire_semantic_deficit'],
        wall_ns=result['processing_wall_ns'],output=str(args.output))))


if __name__=='__main__':main()
