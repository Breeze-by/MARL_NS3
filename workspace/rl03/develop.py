"""Exactly six preregistered TRAIN/VAL cases, old weights/new candidates, no learning."""
import json
import signal
import time
import traceback
import torch
from common import HERE,PROJECT,dump,configuration,training_maps,warm_model,Episode,Ledger

CASES=[('econ-A',101),('partition_grid-1101',101),('alternating_baffles-1201',101),
       ('central_hub_chambers-2101',201),('central_hub_chambers-2102',201),('central_hub_chambers-2103',201)]


def run():
    start=time.monotonic()
    output=PROJECT/'evidence/development-01';output.mkdir(exist_ok=False)
    config=configuration();maps=training_maps()
    ledger=Ledger(output/'ledger.jsonl','rl03_six_fixed_development')
    torch.set_num_threads(1)
    model=warm_model(ledger,config)
    initial={k:p.detach().clone() for k,p in model.state_dict().items()}
    dump(output/'plan.json',dict(cases=CASES,max_joint_per_case=40,max_total_joint=240,
        wall_seconds=900,source_commit=__import__('subprocess').check_output(
            ['git','-C',str(HERE.parent),'rev-parse','HEAD'],text=True).strip(),
        config=config,model_sha256=__import__('common').WARM_SHA,optimizer_updates=0))
    results=[];active=None;failure=None
    def timeout(signum,frame):raise TimeoutError('900 wall development cap')
    # Reserve30wall for final actual stop and evidence within the900wall budget.
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,max(.001,870-(time.monotonic()-start)))
    try:
        for index,(name,seed) in enumerate(CASES):
            row=next(r for r in maps if r['name']==name)
            pose=next(p for p in row['positions'] if p['seed']==seed)
            active=Episode(row,pose,300000+index,config,ledger,output/f'{index:02d}-{name}-{seed}','rl',fatal_idle=True)
            if active.observation['contract']!='rl03-local-reachable-v1':raise ValueError('Wrong observation contract')
            while not active.env.done and len(active.records)<40:
                active.step(model,deterministic=True,bootstrap=False)
            closed,active=active,None
            results.append(closed.finish('rl03_development_cap_40' if not closed.env.done else 'rl03_development_end'))
            print(json.dumps(results[-1]),flush=True)
        if not all(torch.equal(initial[k],p) for k,p in model.state_dict().items()):
            raise ValueError('Development changed model weights')
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
        dump(output/'first-failure.json',failure)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        if active is not None:results.append(active.finish('rl03_development_failure'))
        ledger.flush('rl03_development_end',cases=len(results))
        result=dict(status='SIX-CASE DEVELOPMENT COMPLETE' if failure is None else 'FAIL',cases=results,
            counts=dict(ledger.counts),wall_seconds=time.monotonic()-start,optimizer_updates=0,
            weights_unchanged=all(torch.equal(initial[k],p) for k,p in model.state_dict().items()),failure=failure)
        dump(output/'summary.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True)


if __name__=='__main__':run()
