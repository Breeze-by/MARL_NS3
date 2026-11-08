"""RL03 paths and reuse of the accepted metered episode implementation."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
WORKSPACE=HERE.parent
PROJECT=WORKSPACE.parent
ROOT=PROJECT.parent
sys.path.insert(0,str(WORKSPACE/'rl02'))
sys.path.insert(0,str(WORKSPACE/'src/multi_robot_exploration'))
from maps import dump,sha
from execution import Episode
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.ppo import ActorCritic, load_checkpoint
sys.path.insert(0,str(HERE))

WARM=ROOT/'rl-02/runs/formal-01/checkpoint-01024.pt'
WARM_SHA='a746c56bfd71b57ea8fe2fc94b196aee5db4a7396913cfd0d534b137a1b0182c'


def configuration():
    return json.loads((HERE/'config.json').read_text())


def training_maps():
    return [r for r in json.loads((ROOT/'rl-02/evidence/map-qualification-01/maps.json').read_text()) if r['split'] in ('TRAIN','VAL')]


def warm_model(ledger,config):
    if sha(WARM)!=WARM_SHA:raise ValueError('Old selected weights identity mismatch')
    model=ActorCritic(ledger,config['hidden'])
    load_checkpoint(WARM,model,restore_rng=False)
    return model
