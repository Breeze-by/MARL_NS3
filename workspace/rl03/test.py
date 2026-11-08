"""One locked36episode comparison: new RL / old weights new contract / traditional."""
import json
import time
import traceback
import torch
from common import HERE,ROOT,PROJECT,dump,sha,configuration,warm_model,Episode,Ledger,ActorCritic,load_checkpoint
from train import validate_checkpoint


def run():
    lock=json.loads((HERE/'TEST_LOCK.json').read_text())
    for path,expected in lock['sha256'].items():
        if sha(ROOT/path)!=expected:raise ValueError('Test source/data changed: '+path)
    selection=json.loads((PROJECT/'runs/selection.json').read_text())['selected']
    if selection is None:raise ValueError('No eligible model')
    path=ROOT/selection['checkpoint']
    if sha(path)!=selection['checkpoint_sha256']:raise ValueError('Selected checkpoint changed')
    if json.loads((path.parent/'process-exit.json').read_text())['exit_code']!=0:raise ValueError('Formal native exit failed')
    validate_checkpoint(path,json.loads((path.parent/'summary.json').read_text()))
    output=PROJECT/'runs/test-01';output.mkdir(exist_ok=False)
    ledger=Ledger(output/'ledger.jsonl','rl03_locked_36test')
    config=configuration();torch.set_num_threads(1)
    model=ActorCritic(ledger,config['hidden']);load_checkpoint(path,model,restore_rng=False);model.eval()
    old=warm_model(ledger,config);old.eval()
    initial=[{k:p.detach().clone() for k,p in m.state_dict().items()} for m in (model,old)]
    maps=json.loads((ROOT/lock['maps_manifest']).read_text())
    output_cases=[];active=None;failure=None;start=time.monotonic()
    dump(output/'binding.json',dict(selection=selection,test_lock_sha256=sha(HERE/'TEST_LOCK.json'),
        arms=['rl','old_reference','traditional'],old_reference_uses_new_contract=True,maximum_episodes=36))
    try:
        for serial,case in enumerate(lock['cases']):
            if time.monotonic()-start>=7200:raise TimeoutError('Test7200wall cap')
            row=next(r for r in maps if r['name']==case['map'])
            pose=next(p for p in row['positions'] if p['seed']==case['seed'])
            arm=case['arm']
            active=Episode(row,pose,400000+serial,config,ledger,output/f'{serial:02d}-{row["name"]}-{pose["seed"]}-{arm}',arm)
            if active.observation['contract']!='rl03-local-reachable-v1':raise ValueError('Test contract mismatch')
            while not active.env.done:
                if time.monotonic()-start>=7200:raise TimeoutError('Test7200wall cap')
                active.step(old if arm=='old_reference' else model,deterministic=True,bootstrap=False)
            closed,active=active,None
            output_cases.append(closed.finish('rl03_test_end'))
            print(json.dumps(output_cases[-1]),flush=True)
        if len(output_cases)!=36:raise ValueError('Incomplete locked test')
        if not all(torch.equal(saved[k],p) for m,saved in zip((model,old),initial) for k,p in m.state_dict().items()):
            raise ValueError('Test changed model weights')
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
        dump(output/'first-failure.json',failure);raise
    finally:
        if active is not None:output_cases.append(active.finish('rl03_test_failure'))
        ledger.flush('rl03_test_end',episodes=len(output_cases))
        dump(output/'summary.json',dict(status='LOCKED TEST COMPLETE' if failure is None else 'FAIL',
            cases=output_cases,counts=dict(ledger.counts),wall_seconds=time.monotonic()-start,
            optimizer_updates=0,weights_unchanged=all(torch.equal(saved[k],p) for m,saved in zip((model,old),initial) for k,p in m.state_dict().items()),
            failure=failure,formally_frozen=False))


if __name__=='__main__':run()
