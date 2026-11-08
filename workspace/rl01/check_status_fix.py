"""Run only after post-run status patch; no real policy/env/optimizer actions."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent/'src/multi_robot_exploration'))
from multi_robot_exploration.rl_ledger import Ledger
from completion import validate_development_checkpoint


def check(directory):
    directory.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(directory/'ledger.jsonl', 'controlled_status_classification')
    config = json.loads((HERE/'config.json').read_text())
    complete = dict(metadata=dict(config=config, joint_decisions=1024, failure=None),
                    optimizer=dict(state={0: dict(step=32)}))
    outcomes = {}
    with ledger.call('completion_dictionary_fixture'):
        assert validate_development_checkpoint(complete, config)['optimizer_updates'] == 32
        for name, change in [('partial', 100), ('zero_update', 0), ('failure', 'KeyboardInterrupt')]:
            invalid = copy.deepcopy(complete)
            if name == 'partial':
                invalid['metadata']['joint_decisions'] = change
            elif name == 'zero_update':
                invalid['optimizer']['state'][0]['step'] = change
            else:
                invalid['metadata']['failure'] = change
            try:
                validate_development_checkpoint(invalid, config)
            except ValueError as error:
                outcomes[name] = str(error)
            else:
                raise AssertionError('Incomplete checkpoint was accepted')
    spec = importlib.util.spec_from_file_location('rl01_controlled_driver', HERE/'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captures = []

    class FakeModel:
        def __init__(self, ignored_ledger, hidden=128):
            self.actor = SimpleNamespace(weight=torch.zeros((1, 1)))

        def parameters(self):
            return []

        def act(self, observation):
            ledger.add('fake_policy_interrupt_calls')
            raise KeyboardInterrupt('controlled zero-interaction interrupt')

    class FakeBackend:
        goals = {}
        trajectory = []
        event_log = []

        def stop(self, reason):
            ledger.add('fake_backend_stop_calls')
            return True

    class FakeEnv:
        allocator = SimpleNamespace(stop=lambda reason: None)
        backend = FakeBackend()

        def reset(self):
            ledger.add('fake_env_reset_calls')
            return {}, {}

    def fake_save(path, model, optimizer, **metadata):
        captures.append(dict(path=str(path), metadata=metadata))
        Path(path).write_text(json.dumps(dict(controlled_fixture=True, metadata=metadata), indent=2)+'\n')

    module.ActorCritic = FakeModel
    module.load_checkpoint = lambda *args, **kwargs: {}
    module.save_checkpoint = fake_save
    module.make_env = lambda *args: FakeEnv()
    module.Ledger = lambda path, phase: Ledger(path, 'controlled_interrupt_fixture')
    original_adam = module.torch.optim.Adam
    module.torch.optim.Adam = lambda *args, **kwargs: SimpleNamespace()
    initial = directory/'initial-stub.bin'
    initial.write_bytes(b'controlled fixture; not a model checkpoint')
    propagated = False
    try:
        module.train(directory/'fixture-case', initial)
    except KeyboardInterrupt:
        propagated = True
    finally:
        module.torch.optim.Adam = original_adam
    assert propagated and len(captures) == 1
    assert captures[0]['path'].endswith('failed.pt')
    assert captures[0]['metadata']['failure']['type'] == 'KeyboardInterrupt'
    assert not (directory/'fixture-case/final.pt').exists()
    summary = json.loads((directory/'fixture-case/summary.json').read_text())
    assert summary['status'] == 'FAIL' and summary['actual_joint_decisions'] == 0
    ledger.flush('status_fixture_end')
    result = dict(status='PASS', rejected_checkpoints=outcomes, keyboard_interrupt_propagated=True,
                  incomplete_run_not_pass=True, real_policy_forwards=0, real_environment_steps=0,
                  real_optimizer_updates=0, ledger_totals=dict(ledger.counts))
    (directory/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path, required=True)
    args = parser.parse_args()
    check(args.case)
