"""Fixed RL04 paths and reused metered episode implementation."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent;WORKSPACE=HERE.parent;PROJECT=WORKSPACE.parent;ROOT=PROJECT.parent
sys.path.insert(0,str(WORKSPACE/'rl02'));sys.path.insert(0,str(WORKSPACE/'src/multi_robot_exploration'))
from maps import dump,sha
from execution import Episode
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.ppo import ActorCritic,load_checkpoint
sys.path.insert(0,str(HERE))

WARM=ROOT/'rl-03/runs/formal-01/checkpoint-02048.pt'
WARM_SHA='46e8079f3f9fa035b896be534f2acd70b94bd44e11d7b6ad2568e4b35732a7b7'


def configuration():return json.loads((HERE/'train-config.json').read_text())


def training_maps():
    return [r for r in json.loads((PROJECT/'evidence/corpus-01/maps.json').read_text()) if r['split'] in ('TRAIN','VAL')]
