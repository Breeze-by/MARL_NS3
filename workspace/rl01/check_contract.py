"""Persisted form of contract-restore-01 directed inline check (no env steps)."""
import argparse
import json
from pathlib import Path
import random
import sys
import numpy as np
import torch

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import Allocator
from multi_robot_exploration.ppo import ActorCritic, load_checkpoint, encode
from multi_robot_exploration.rl_ledger import Ledger


def check(case, evidence):
    case.mkdir(exist_ok=False)
    ledger = Ledger(case/'ledger.jsonl', 'gate_contract_restore')
    torch.set_num_threads(1)
    data = np.load(evidence/'gate-03/scene-and-observation.npz')
    poses = json.loads((evidence/'gate-03/trajectory.json').read_text())[-1]['poses']
    config = json.loads((WORKSPACE/'rl01/config.json').read_text())
    with ledger.call('allocator_contract_gate_builds', count=2):
        a, b = Allocator(), Allocator(task_roi=config['task_roi'])
        for target in (a, b):
            target.update_map(data['observed'], .05, tuple(data['origin']), 20.)
            for robot, pose in poses.items():
                target.update_robot(robot, tuple(pose), 20., (0., 0., 0.))
        left, right = a.get_observation(), b.get_observation()
        assert np.array_equal(left['map']['cells'], right['map']['cells'])
        assert left['valid_counts'] == right['valid_counts']
        assert len(left['candidates']) == len(right['candidates'])
        assert np.array_equal(encode(left), encode(right))
        optimizers, draws, actions = [], [], []
        for _ in range(2):
            model = ActorCritic(ledger)
            optimizer = torch.optim.Adam(model.parameters(), lr=.0003)
            load_checkpoint(evidence/'gate-03/gate-clone-updated.pt', model, optimizer, restore_rng=True)
            ledger.add('rng_gate_draws', 3)
            draws.append((random.random(), float(np.random.rand()), float(torch.rand(()))))
            actions.append(model.act(right))
            optimizers.append(optimizer)
        assert draws[0] == draws[1]
        assert actions[0]['action'] == actions[1]['action']
        assert actions[0]['logprob'] == actions[1]['logprob'] and actions[0]['value'] == actions[1]['value']
        first, second = [opt.state_dict()['state'] for opt in optimizers]
        assert first.keys() == second.keys() and first
        for key in first:
            for field in first[key]:
                assert torch.equal(first[key][field], second[key][field])
    ledger.flush('contract_restore_gate_end')
    (case/'result.json').write_text(json.dumps(dict(status='PASS', env_steps=0,
        optimizer_updates=0, ledger_totals=dict(ledger.counts)), indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    check(args.case, args.evidence)
