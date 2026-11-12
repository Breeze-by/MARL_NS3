"""Static until Root admission: descriptive tables/plots from the twelve original V2 cases."""
import argparse
import csv
from collections import Counter
import itertools
import json
import math
from pathlib import Path
import statistics

REPO=Path(__file__).resolve().parents[2]
BASE=REPO/'net01e/followup01'
ARMS=('A1','B','A0','C')
ROBOTS=('tb1','tb2','tb3')
PAIRS=(('A0','A1'),('A1','B'),('B','C'),('A1','C'),('A0','B'),('A0','C'))
METRICS=('T90_quality_sim_s','T95_quality_sim_s','initial_coverage_raw',
    'final_observed_coverage_raw','full180_budget_final_observed_coverage','path_total_m','autonomous_wall_s')


def read_json(path):
    with path.open() as stream:return json.load(stream)


def read_csv(path):
    with path.open(newline='') as stream:return list(csv.DictReader(stream))


def controller_operations(path):
    evidence=dict(path=str(path.relative_to(REPO)),status='UNMEASURED',records=None,
        operation_counts=None,policy_forward_deltas=None,training_optimizer_related_records=None,
        scope='Runtime controller ledger only, not canonical evaluator calls. Absent training/update operations mean not recorded in this ledger, not proof of no training anywhere.')
    if not path.exists():return None,None,evidence
    with path.open() as stream:records=[json.loads(line) for line in stream if line.strip()]
    counts=Counter(record['operation'] for record in records)
    forward=[record.get('delta',{}).get('policy_forward') for record in records if record['operation']=='policy_forward']
    measured=bool(forward) and all(isinstance(value,(int,float)) and not isinstance(value,bool) for value in forward)
    nn_forward=sum(forward) if measured else None
    decisions=counts['ros_joint_decision_attempt'] if 'ros_joint_decision_attempt' in counts else None
    related=[record for record in records if any(token in json.dumps(record).lower()
        for token in ('train','optim','backward','gradient','update'))]
    evidence.update(status='LEDGER_OBSERVED',records=len(records),operation_counts=dict(counts),
        policy_forward_deltas=forward,training_optimizer_related_records=related,
        NN_forward=nn_forward,decision_attempts=decisions,
        count_semantics='NN sums delta.policy_forward only on operation=policy_forward. Decisions count operation=ros_joint_decision_attempt only; overlapping delta keys are not added. Missing operation/delta leaves the corresponding table value UNMEASURED/null.')
    return nn_forward,decisions,evidence


def truth(value):
    if value in (True,'True','true'):return True
    if value in (False,'False','false'):return False
    raise ValueError('Unknown original quality flag '+str(value))


def write_tables(output,name,rows):
    (output/(name+'.json')).write_text(json.dumps(rows,indent=2)+'\n')
    with (output/(name+'.csv')).open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def load_case(round_no,arm):
    name=f'corr6201-v2-r{round_no:02d}-{arm.lower()}'
    analysis=BASE/'gz-analysis'/name;case=BASE/'gz-runs'/name
    paths=dict(metrics=analysis/'metrics.small-result.json',proof=analysis/'pre-evaluation-exit-proof.json',
        coverage=analysis/'metrics/coverage.csv',trajectory=case/'trajectories.csv')
    row=dict(case=name,round=round_no,arm=arm,report_input_status='NOT_RUN_OR_INPUTS_INCOMPLETE',
        process_status='UNMEASURED',case_process_status_raw=None,entry_exit=None,runner_exit=None,
        controller_exit=None,gateway_exit=None,Hub_exit=None,native_exit=None,coordinator_exit=None,
        network_integrity=None,all_known_PIDs_gone=None,evaluator_exit=None,first_error=None,
        start_sim=None,end_sim=None,actual_main_sim_s=None,autonomous_wall_s=None,
        initial_coverage_raw=None,initial_curve_coverage_raw=None,initial_quality_valid=None,
        final_observed_coverage_raw=None,final_sample_elapsed_sim_s=None,final_quality_valid=None,
        full180_budget_observed=False,full180_budget_final_observed_coverage=None,
        T90_quality_sim_s=None,T95_quality_sim_s=None,T95_quality_initially_reached=None,
        T95_raw_sim_s=None,quality_valid_samples=None,original_samples=None,observed_stop=None,
        path_total_m=None,goals_total=None,succeeded_main_total=None,NN_forward=None,
        decision_attempts=None,controller_ledger_status='UNMEASURED',missing_inputs=None)
    for robot in ROBOTS:
        row.update({robot+'_path_m':None,robot+'_goals':None,robot+'_succeeded_main':None,
                    robot+'_aborted_main':None,robot+'_canceled_main':None})
    missing=[str(path.relative_to(REPO)) for path in paths.values() if not path.exists()]
    row['missing_inputs']=';'.join(missing)
    if missing:return row,None
    proof=read_json(paths['proof'])
    row['all_known_PIDs_gone']=proof.get('all_known_writer_and_owned_gone')
    if row['all_known_PIDs_gone'] is not True:
        row['missing_inputs']='NOT_RUN_OR_UNFINISHED: original exit proof has not confirmed writers gone'
        return row,None
    metric=read_json(paths['metrics']);curve=read_csv(paths['coverage']);trajectory=read_csv(paths['trajectory'])
    ledger_path=case/'controller/ledger.jsonl'
    nn_forward,decisions,operations=controller_operations(ledger_path)
    row.update(NN_forward=nn_forward,decision_attempts=decisions,controller_ledger_status=operations['status'])
    host=proof.get('host',{});integrity=proof.get('network_integrity',{})
    gateway=integrity.get('gateway_exit',{});controller=integrity.get('controller_exit',{})
    original_result=proof.get('original_result_small',{})
    actual_exits=(proof.get('actual_entry_exit'),host.get('runner_exit'),controller.get('returncode'),
        gateway.get('native_exit'),host.get('hub_exit'),proof.get('hub',{}).get('native_exit'),
        host.get('controlled_time',{}).get('exits',{}).get('coordinator'))
    original_errors=(metric.get('error'),metric.get('first_error'),proof.get('error'),host.get('error'),
        integrity.get('error'),controller.get('error'),gateway.get('error'),proof.get('hub',{}).get('error'),
        original_result.get('error'))
    failed=(any(code not in (None,0) for code in actual_exits)
        or any(flag is False for flag in (integrity.get('network_run_integrity'),
            metric.get('run_integrity'),metric.get('network_run_integrity'),original_result.get('run_integrity')))
        or any(error is not None for error in original_errors))
    process=('PROCESS_FAIL' if failed else 'PROCESS_PASS' if proof.get('actual_entry_exit')==0
        and integrity.get('network_run_integrity') is True else 'UNMEASURED')
    start=metric['start_sim'];end=metric['end_sim'];elapsed=metric['autonomy_sim_s']
    initial=next((r for r in curve if float(r['elapsed_sim_s'])==0),None)
    full=math.isclose(elapsed,180.0,abs_tol=1e-6,rel_tol=0)
    row.update(report_input_status='ORIGINAL_INPUTS_AVAILABLE',process_status=process,
        case_process_status_raw=metric.get('case_process_status'),entry_exit=proof.get('actual_entry_exit'),
        runner_exit=host.get('runner_exit'),controller_exit=controller.get('returncode'),
        gateway_exit=gateway.get('native_exit'),Hub_exit=host.get('hub_exit'),
        native_exit=proof.get('hub',{}).get('native_exit'),
        coordinator_exit=host.get('controlled_time',{}).get('exits',{}).get('coordinator'),
        network_integrity=integrity.get('network_run_integrity'),evaluator_exit=metric.get('evaluator_exit'),
        first_error=metric.get('first_error'),start_sim=start,end_sim=end,actual_main_sim_s=elapsed,
        autonomous_wall_s=metric.get('autonomous_wall_s'),initial_coverage_raw=metric.get('initial_coverage'),
        initial_curve_coverage_raw=None if initial is None else float(initial['coverage']),
        initial_quality_valid=None if initial is None else truth(initial['map_quality_valid']),
        final_observed_coverage_raw=metric.get('final_coverage'),
        final_sample_elapsed_sim_s=metric.get('final_metrics',{}).get('elapsed_sim_s'),
        final_quality_valid=metric.get('final_metrics',{}).get('map_quality_valid'),
        full180_budget_observed=full,full180_budget_final_observed_coverage=metric.get('final_coverage') if full else None,
        quality_valid_samples=metric.get('quality_valid_samples'),original_samples=metric.get('samples'),
        observed_stop=metric.get('post_task_observed_stop'))
    for level,name_ in (('0.9','T90_quality_sim_s'),('0.95','T95_quality_sim_s')):
        hit=metric.get('quality_valid_thresholds',{}).get(level)
        row[name_]=None if hit is None else hit['elapsed_sim_s']
        if level=='0.95':row['T95_quality_initially_reached']=None if hit is None else hit.get('initially_reached')
    raw=metric.get('raw_thresholds',{}).get('0.95');row['T95_raw_sim_s']=None if raw is None else raw['elapsed_sim_s']
    for robot in ROBOTS:
        r=metric['robot_metrics'][robot]
        for key,source in (('path_m','path_m'),('goals','goals'),('succeeded_main','succeeded'),('aborted_main','aborted'),('canceled_main','canceled')):
            row[robot+'_'+key]=r.get(source)
    row['path_total_m']=sum(row[r+'_path_m'] for r in ROBOTS)
    row['goals_total']=sum(row[r+'_goals'] for r in ROBOTS)
    row['succeeded_main_total']=sum(row[r+'_succeeded_main'] for r in ROBOTS)
    selected=[r for r in trajectory if start<=float(r['sim_s'])<=end]
    return row,dict(curve=curve,trajectory=selected,controller_operations=operations,
        paths={**{k:str(v.relative_to(REPO)) for k,v in paths.items()},'controller_ledger':str(ledger_path.relative_to(REPO))})


def describe(rows):
    output=[]
    for arm in ARMS:
        cases=[r for r in rows if r['arm']==arm]
        for field in METRICS:
            values=[r[field] for r in cases if r[field] is not None]
            output.append(dict(arm=arm,metric=field,expected_cases=3,observed_numeric_n=len(values),
                mean_observed=None if not values else statistics.mean(values),
                median_observed=None if not values else statistics.median(values),
                minimum=None if not values else min(values),maximum=None if not values else max(values),
                not_available_cases=';'.join(r['case'] for r in cases if r[field] is None),
                process_fail_cases=';'.join(r['case'] for r in cases if r['process_status']=='PROCESS_FAIL'),
                scope='All available original numeric values, including process failures; missing/not-reached not imputed. Actual-window final coverage is not common180 comparison.'))
    return output


def paired(rows):
    indexed={(r['round'],r['arm']):r for r in rows};output=[]
    for round_no in (1,2,3):
        for reference,target in PAIRS:
            a=indexed[(round_no,reference)];b=indexed[(round_no,target)]
            for field in METRICS:
                measured=a[field] is not None and b[field] is not None
                output.append(dict(round=round_no,reference_arm=reference,target_arm=target,metric=field,
                    difference_target_minus_reference=None if not measured else b[field]-a[field],
                    reference_value=a[field],target_value=b[field],reference_status=a['process_status'],target_status=b['process_status'],
                    reference_main_sim_s=a['actual_main_sim_s'],target_main_sim_s=b['actual_main_sim_s'],
                    scope='Same RNG parameters/fresh process, not independent RF seeds or causal/inferential test; partial final-window horizons may differ.'))
    return output


def plots(output,rows,bundles):
    # Import/render only during the future separately admitted final invocation.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure,axes=plt.subplots(2,2,figsize=(13,9),sharex=True,sharey=True)
    colors=('tab:blue','tab:orange','tab:green')
    for arm,axis in zip(ARMS,axes.flat):
        for row in [r for r in rows if r['arm']==arm]:
            bundle=bundles.get(row['case']);round_no=row['round']
            if bundle is None:
                axis.plot([],[],label=f'r{round_no} NOT_RUN/incomplete');continue
            curve=bundle['curve']
            threshold='NOT_REACHED' if row['T95_quality_sim_s'] is None else f"{row['T95_quality_sim_s']:.2f}"
            label=f"r{round_no} {row['process_status']} {row['actual_main_sim_s']:.2f}s; T95={threshold}"
            axis.plot([float(r['elapsed_sim_s']) for r in curve],
                [100*float(r['coverage']) if truth(r['map_quality_valid']) else math.nan for r in curve],
                color=colors[round_no-1],label=label,linestyle='--' if row['process_status']=='PROCESS_FAIL' else '-')
        axis.axhline(95,color='grey',linestyle=':',linewidth=.8)
        axis.set(title=arm,xlim=(0,180),ylim=(0,101),xlabel='Elapsed simulation s',ylabel='Original quality-valid coverage %')
        axis.grid(alpha=.25);axis.legend(fontsize=7)
    figure.suptitle('Recorded coverage only; invalid-quality samples are gaps; partial failures are not extended')
    figure.tight_layout();figure.savefig(output/'coverage-12.png',dpi=180);plt.close(figure)
    figure,axes=plt.subplots(3,4,figsize=(17,12))
    points=[(float(p['x']),float(p['y'])) for b in bundles.values() for p in b['trajectory']]
    extent=None if not points else (min(p[0] for p in points)-.2,max(p[0] for p in points)+.2,min(p[1] for p in points)-.2,max(p[1] for p in points)+.2)
    for row in rows:
        axis=axes[row['round']-1,ARMS.index(row['arm'])];bundle=bundles.get(row['case'])
        if bundle is None:axis.text(.5,.5,'NOT_RUN / incomplete',ha='center',transform=axis.transAxes)
        else:
            for robot,color in zip(ROBOTS,colors):
                path=[p for p in bundle['trajectory'] if p['robot']==robot]
                axis.plot([float(p['x']) for p in path],[float(p['y']) for p in path],label=robot,color=color,linewidth=.9)
                if path:axis.scatter([float(path[0]['x'])],[float(path[0]['y'])],s=10,color=color)
        title=f"r{row['round']} {row['arm']} {row['process_status']}"
        if row['actual_main_sim_s'] is not None:title+=f" {row['actual_main_sim_s']:.2f}s"
        axis.set_title(title,fontsize=9);axis.set(xlabel='Evaluation world x / m',ylabel='Evaluation world y / m');axis.set_aspect('equal')
        if extent:axis.set_xlim(extent[:2]);axis.set_ylim(extent[2:])
        axis.grid(alpha=.2)
    axes[0,0].legend(fontsize=7)
    figure.suptitle('Original three-robot trajectories clipped to actual main; ground truth used for evaluation only')
    figure.tight_layout();figure.savefig(output/'trajectories-12.png',dpi=180);plt.close(figure)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    rows=[];bundles={}
    for round_no,arm in itertools.product((1,2,3),ARMS):
        row,bundle=load_case(round_no,arm);rows.append(row)
        if bundle is not None:bundles[row['case']]=bundle
    write_tables(args.output,'cases-12',rows);write_tables(args.output,'arm-descriptive',describe(rows));write_tables(args.output,'round-paired-differences',paired(rows))
    (args.output/'controller-operation-counts.json').write_text(json.dumps({r['case']:
        bundles[r['case']]['controller_operations'] if r['case'] in bundles else dict(status='UNMEASURED')
        for r in rows},indent=2)+'\n')
    plots(args.output,rows,bundles)
    (args.output/'manifest.json').write_text(json.dumps(dict(status='DESCRIPTIVE_EXPORT_ONLY_NO_VERDICT_CHANGE',
        preregistered_cases=[r['case'] for r in rows],original_inputs={k:v['paths'] for k,v in bundles.items()},
        report_input_counts=dict(Counter(r['report_input_status'] for r in rows)),
        process_counts=dict(Counter(r['process_status'] for r in rows)),
        scope='Three fresh process repetitions at identical seed/run, not independent RF seeds. No p-values/CI, success-only mean, metric/coverage/path recomputation, smoothing, bag/native ledger read, NN/ROS/model call or input modification. Old physical A1-p2 excluded.',
        full180_coverage_semantics='Original last observed coverage within a completed180sim budget, not an interpolated exact180sim sample. Partial C1 never assigned180coverage.',
        missing_threshold_semantics='Original quality threshold NOT_REACHED stays null; observed mean reportsn/3 including failed cases, not a population mean with censored values imputed.'),indent=2)+'\n')


if __name__=='__main__':main()
