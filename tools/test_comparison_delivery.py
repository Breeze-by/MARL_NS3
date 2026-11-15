"""Focused measured-boundary/denominator/aggregation fixtures, no simulation."""
import copy
import json
from pathlib import Path
import tempfile

from analyze_comparison_delivery import analyze,aggregate


def fixtures(directory,path):
    (directory/'controller').mkdir()
    source=dict(take_seq=1,topic='/tb1/odom',metadata={'source_timestamp':1_000_000_000},
        after={'sim_ns':25_000_000_000},before={'sim_ns':25_000_000_000})
    take=dict(event_id=1,kind='hq_native_take',topic='/tb1/odom',metadata={'source_timestamp':1_005_000_000},
        after={'sim_ns':25_000_000_000,'realtime_ns':1_008_000_000})
    capture=dict(flow=22,robot=1,bytes=4,cdr_sha256='same',capture_node_sim_ns=25_000_000_000,
        source_take=source,hub_send_seq=2,direct_native_id=2,gateway_capture_clock_ns=25_000_000_000)
    destination=dict(flow=22,message_id=2,native_id=2,cdr_sha256='same',publisher_returned=True,
        destination_node_sim_ns=25_010_000_000,ns3_rx_ns=25_001_000_000,
        gateway_publication_topic='/tb1/odom',publish_before_realtime_ns=1_004_000_000,
        publish_after_realtime_ns=1_006_000_000,gateway_receive_clock_ns=25_010_000_000)
    send=dict(send_seq=2,sender=1,receiver=0,flow=22,bytes=12,admission_ns=25_000_000_000,source_stamp_ns=0)
    ingress=dict(send,native_message_id=2);ingress.pop('send_seq')
    (directory/'source-observer-takes.jsonl').write_text(json.dumps(source)+'\n')
    (directory/'source-observer-measurement.json').write_text(json.dumps({'rows':1}))
    (directory/'controller/consumer-trace.jsonl').write_text(json.dumps(take)+'\n')
    (directory/'controller/consumer-trace-summary.json').write_text(json.dumps({'rows':1}))
    (directory/'network-gateway-saved.json').write_text(json.dumps({'saved':True}))
    (directory/'controller/allocation-events.jsonl').write_text('')
    (directory/'comparison-gateway.json').write_text(json.dumps(dict(sends=[send],send_seq_total=2)))
    (directory/'network-gateway.json').write_text(json.dumps(dict(topics={'R':{'captured':[capture],'delivered':[]},'C':{'captured':[],'delivered':[destination]}})))
    (directory/'hub-ingress.json').write_text(json.dumps([ingress]))
    return source,take,capture,destination,ingress


def main():
    checks={}
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        for path in ('A1','B','C'):
            directory=root/path;directory.mkdir();source,take,capture,destination,ingress=fixtures(directory,path)
            result=analyze(directory,path,directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
            assert result['source_cohort']['exact_success_rate']==1
            assert result['source_publish_to_hq_take_return_wall_ms']['mean']==8
            assert result['wire_capture_to_destination_publish']['exact_success_rate']==1
            if path!='A1':assert result['ingress_to_native_rx_sim_ms']['mean']==1
            else:assert result['a1_local_fifo_clock_witness_delta_sim_ms']['mean']==10
            checks[path+'_original_source_not_republisher_and_separate_clock_units']=True
        directory=root/'A0';directory.mkdir();source,take,*_=fixtures(directory,'A0')
        take['metadata']['source_timestamp']=source['metadata']['source_timestamp']
        (directory/'controller/consumer-trace.jsonl').write_text(json.dumps(take)+'\n')
        direct=analyze(directory,'A0',None,20_000_000_000,140_000_000_000)
        assert direct['source_cohort']['exact_success_rate']==1 and direct['wire_capture_to_destination_publish'] is None
        checks['A0_no_wire_is_not_a_drop_or_fake_100percent_wire_rate']=True
        (directory/'source-observer-takes.jsonl').write_text(json.dumps(source)+'\n'+json.dumps(dict(source,take_seq=2))+'\n')
        (directory/'source-observer-measurement.json').write_text(json.dumps({'rows':2}))
        ambiguous=analyze(directory,'A0',None,20_000_000_000,140_000_000_000)['source_cohort']
        assert ambiguous['denominator']==2 and ambiguous['exact_success_rate'] is None
        assert ambiguous['status_counts']['AMBIGUOUS_SOURCE_PUBLICATION_TIMESTAMP']==2
        checks['duplicate_timestamp_retained_in_denominator_and_ambiguous']=True
        source['metadata']=None
        (directory/'source-observer-measurement.json').write_text(json.dumps({'rows':1}))
        (directory/'source-observer-takes.jsonl').write_text(json.dumps(source)+'\n')
        unknown=analyze(directory,'A0',None,20_000_000_000,140_000_000_000)['source_cohort']
        assert unknown['denominator']==1 and unknown['status_counts']=={'UNKNOWN_SOURCE_METADATA':1}
        checks['missing_source_metadata_not_silently_excluded']=True
        source['metadata']={'source_timestamp':1_000_000_000}
        take['after']['realtime_ns']=900_000_000
        (directory/'source-observer-takes.jsonl').write_text(json.dumps(source)+'\n')
        (directory/'controller/consumer-trace.jsonl').write_text(json.dumps(take)+'\n')
        negative=analyze(directory,'A0',None,20_000_000_000,140_000_000_000)
        assert negative['negative_wall_intervals']==1 and negative['source_publish_to_hq_take_return_wall_ms']['mean'] is None
        checks['negative_realtime_interval_invalidates_delay_not_clamped_or_hidden']=True
        directory=root/'B';ingress=json.loads((directory/'hub-ingress.json').read_text());ingress[0]['flow']=99
        (directory/'hub-ingress.json').write_text(json.dumps(ingress))
        invalid=analyze(directory,'B',directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
        assert invalid['source_cohort']['status_counts']=={'UNKNOWN_CAPTURE_IDENTITY':1}
        checks['fifo_native_id_verified_against_actual_ingress_route']=True
        directory=root/'overlap';directory.mkdir();source,take,capture,destination,ingress=fixtures(directory,'B')
        network=json.loads((directory/'network-gateway.json').read_text())
        extra=dict(destination,message_id=3);network['topics']['C']['delivered'].append(extra)
        (directory/'network-gateway.json').write_text(json.dumps(network))
        ambiguous=analyze(directory,'B',directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
        assert ambiguous['source_cohort']['status_counts']=={'AMBIGUOUS_DESTINATION_PUBLICATION':1}
        checks['overlapping_destination_brackets_not_called_packet_loss']=True
        network['topics']['C']['delivered']=[dict(destination,cdr_sha256='changed')]
        (directory/'network-gateway.json').write_text(json.dumps(network))
        invalid=analyze(directory,'B',directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
        assert invalid['source_cohort']['status_counts']=={'UNKNOWN_CAPTURE_IDENTITY':1}
        assert invalid['ingress_to_native_rx_sim_ms']['n']==0
        checks['full_original_CDR_integrity_failure_not_delivered_latency']=True
        directory=root/'unmatched';directory.mkdir();source,take,capture,destination,ingress=fixtures(directory,'B')
        take['metadata']['source_timestamp']=1_200_000_000
        (directory/'controller/consumer-trace.jsonl').write_text(json.dumps(take)+'\n')
        unmatched=analyze(directory,'B',directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
        assert unmatched['source_cohort']['status_counts']=={'UNKNOWN_DESTINATION_PUBLICATION_MATCH':1}
        assert unmatched['source_cohort']['success_rate_lower']==0 and unmatched['source_cohort']['success_rate_upper']==1
        checks['unmatched_valid_HQ_timestamp_is_unknown_not_a_known_drop']=True
        take['metadata']['source_timestamp']=1_005_000_000
        (directory/'controller/consumer-trace.jsonl').write_text(json.dumps(take)+'\n')
        (directory/'hub-ingress.json').write_text(json.dumps([ingress,ingress]))
        duplicate=analyze(directory,'B',directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
        assert duplicate['duplicate_native_ingress_ids']==[2]
        assert duplicate['source_cohort']['status_counts']=={'UNKNOWN_CAPTURE_IDENTITY':1}
        assert not duplicate['measurement_valid']
        (directory/'hub-ingress.json').write_text(json.dumps([ingress]))
        network=json.loads((directory/'network-gateway.json').read_text())
        network['topics']['C']['delivered'].append(dict(destination))
        (directory/'network-gateway.json').write_text(json.dumps(network))
        duplicate=analyze(directory,'B',directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
        assert duplicate['duplicate_destination_ids']==[(22,2)]
        assert duplicate['source_cohort']['status_counts']=={'UNKNOWN_CAPTURE_IDENTITY':1}
        assert not duplicate['measurement_valid']
        checks['duplicate_ingress_or_destination_identity_never_overwrites_into_unique']=True
        directory=root/'incomplete';directory.mkdir();fixtures(directory,'B')
        (directory/'controller/consumer-trace-summary.json').unlink()
        incomplete=analyze(directory,'B',directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
        assert not incomplete['measurement_valid'] and 'HQ_TRACE_INCOMPLETE' in incomplete['measurement_invalid_reasons']
        assert incomplete['source_cohort']['status_counts']=={'UNKNOWN_HQ_TRACE_INCOMPLETE':1}
        assert incomplete['source_cohort']['exact_success_rate'] is None
        assert incomplete['source_cohort']['success_rate_lower']==0 and incomplete['source_cohort']['success_rate_upper']==1
        assert incomplete['source_publish_to_hq_take_return_wall_ms']['mean'] is None
        (directory/'controller/consumer-trace-summary.json').write_text(json.dumps({'rows':2}))
        mismatch=analyze(directory,'B',directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
        assert 'HQ_TRACE_INCOMPLETE' in mismatch['measurement_invalid_reasons']
        checks['missing_or_inconsistent_HQ_completion_is_unknown_not_zero_delivery']=True
        (directory/'controller/consumer-trace-summary.json').write_text(json.dumps({'rows':1}))
        (directory/'source-observer-measurement.json').write_text(json.dumps({'rows':2}))
        mismatch=analyze(directory,'B',directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
        assert 'SOURCE_TRACE_INCOMPLETE' in mismatch['measurement_invalid_reasons']
        assert not mismatch['source_cohort_denominator_complete']
        (directory/'source-observer-measurement.json').write_text(json.dumps({'rows':1}))
        (directory/'network-gateway-saved.json').write_text(json.dumps({'saved':False}))
        mismatch=analyze(directory,'B',directory/'hub-ingress.json',20_000_000_000,140_000_000_000)
        assert 'WIRE_TRACE_INCOMPLETE' in mismatch['measurement_invalid_reasons']
        assert mismatch['wire_capture_to_destination_publish'] is None
        checks['source_and_wire_completion_checked_without_inventing_denominator']=True
        rows=[dict(map='fixture',path='B',t95_sim_s=t,last_coverage=.9,source_delivery_rate=r,wire_delivery_rate=r,
                   source_to_hq_mean_wall_ms=r,source_to_hq_p95_wall_ms=r,native_service_p95_sim_ms=r)
              for t,r in zip((40,50,None,None,60),(.2,.4,.6,.8,1.))]
        complete=[dict(row,map=map_name,path=path) for map_name in ('fixture1','fixture2')
            for path in ('A0','A1','B','C') for row in rows]
        group=aggregate(complete)['groups'][0]
        assert group['task_successes']==3 and group['task_denominator']==5
        assert group['t95_all_five_mean'] is None and group['reached_only_t95']['mean']==50
        assert group['metrics']['source_delivery_rate']['mean']==.6
        checks['all_five_slots_equal_weight_null_not_replaced_reached_only_labeled']=True
    print(json.dumps(dict(status='PASS',checks=checks)))


if __name__=='__main__':main()
