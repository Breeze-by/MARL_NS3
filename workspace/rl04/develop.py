"""Admitted fixed6public cases, original46e8079 weights/new explicit contract, no learning."""
import json
import argparse
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent;WS=HERE.parent;PROJECT=WS.parent;ROOT=PROJECT.parent
sys.path.insert(0,str(WS/'rl02'));sys.path.insert(0,str(WS/'src/multi_robot_exploration'))
import torch
from execution import Episode
from maps import dump,sha
from multi_robot_exploration.ppo import ActorCritic,load_checkpoint
from multi_robot_exploration.rl_ledger import Ledger

CASES=[('loop_chambers-4102',502),('branching_corridors-4201',502),('branching_corridors-4202',502),
       ('branching_corridors-4203',501),('central_hub_chambers-2101',201),('central_hub_chambers-2102',201)]
MODEL_SHA='46e8079f3f9fa035b896be534f2acd70b94bd44e11d7b6ad2568e4b35732a7b7'


def run(case_number=1):
    started=time.monotonic();output=PROJECT/f'evidence/development-{case_number:02d}';output.mkdir(exist_ok=False)
    config=json.loads((HERE/('config.json' if case_number==1 else 'config-v2.json')).read_text())
    ledger=Ledger(output/'ledger.jsonl','rl04_fixed_public_development')
    torch.set_num_threads(1)
    checkpoint=ROOT/'rl-03/runs/formal-01/checkpoint-02048.pt'
    if sha(checkpoint)!=MODEL_SHA:raise ValueError('Admitted old weights changed')
    model=ActorCritic(ledger,config['hidden']);load_checkpoint(checkpoint,model,restore_rng=False);model.eval()
    initial={k:p.detach().clone() for k,p in model.state_dict().items()}
    maps=json.loads((ROOT/'rl-03/evidence/new-test-qualification-01/maps.json').read_text())
    maps+=json.loads((ROOT/'rl-02/evidence/map-qualification-01/maps.json').read_text())
    baseline={}
    for p in (ROOT/'rl-03/runs/test-01').glob('*/summary.json'):
        s=json.loads(p.read_text())
        if s['policy']=='rl':baseline[(s['map'],s['seed'])]=p
    for p in (ROOT/'rl-03/runs/formal-01/validation/02048').glob('*/summary.json'):
        s=json.loads(p.read_text());baseline[(s['map'],s['seed'])]=p
    plan=[]
    for name,seed in CASES:
        row=next(r for r in maps if r['name']==name);pose=next(p for p in row['positions'] if p['seed']==seed)
        old_case=json.loads((baseline[(name,seed)].parent/'case.json').read_text())
        if old_case['positions']!=pose['positions']:raise ValueError('Baseline physical positions changed')
        plan.append(dict(map=name,seed=seed,baseline=str(baseline[(name,seed)].relative_to(ROOT))))
    dump(output/'plan.json',dict(cases=plan,max_joint_per_case=40,max_total_joint=240,wall_seconds=900,
        source_commit=subprocess.check_output(['git','-C',str(WS),'rev-parse','HEAD'],text=True).strip(),
        config=config,model_sha256=MODEL_SHA,weights_only_reference_new_contract=True,optimizer_updates=0))
    results=[];active=None;failure=None
    def timeout(signum,frame):raise TimeoutError('Registered900wall DEV cap (30reserved for finalization)')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,max(.001,870-(time.monotonic()-started)))
    try:
        for index,(name,seed) in enumerate(CASES):
            original=next(r for r in maps if r['name']==name);row=dict(original,split='PUBLIC_DEV')
            pose=next(p for p in row['positions'] if p['seed']==seed)
            active=Episode(row,pose,600000+index,config,ledger,output/f'{index:02d}-{name}-{seed}','rl',fatal_idle=True)
            if active.observation['contract']!=config['observation_contract']:raise ValueError('Wrong candidate contract')
            while not active.env.done and len(active.records)<40:active.step(model,deterministic=True,bootstrap=False)
            closed,active=active,None
            results.append(closed.finish('rl04_development_cap_40' if not closed.env.done else 'rl04_development_end'))
            print(json.dumps(results[-1]),flush=True)
        if not all(torch.equal(initial[k],p) for k,p in model.state_dict().items()):raise ValueError('DEV changed model weights')
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
        dump(output/'first-failure.json',failure);raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        if active is not None:results.append(active.finish('rl04_development_failure'))
        ledger.flush('rl04_development_end',cases=len(results))
        result=dict(status='FIXED PUBLIC DEVELOPMENT COMPLETE' if failure is None else 'FAIL',cases=results,
            counts=dict(ledger.counts),wall_seconds=time.monotonic()-started,optimizer_updates=0,
            weights_unchanged=all(torch.equal(initial[k],p) for k,p in model.state_dict().items()),failure=failure)
        dump(output/'summary.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case-number',type=int,choices=(1,2),default=1)
    run(parser.parse_args().case_number)
