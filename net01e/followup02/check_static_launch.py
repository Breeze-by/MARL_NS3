"""Pure YAML/action-handoff check; no Node, LaunchService or Gazebo."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import yaml

ROOT=Path('/mnt');OUT=Path('/tmp/analysis');directory=OUT/'derived';directory.mkdir(exist_ok=False)
CASE=ROOT/'net01e/followup01/gz-runs/corr6201-v2-r03-b'
before={}
for robot in ('tb1','tb2','tb3'):
    text=(CASE/f'peer_nav2_{robot}.yaml').read_text();(directory/f'peer_nav2_{robot}.yaml').write_text(text)
    before[robot]=yaml.safe_load(text)
path=ROOT/'net01e/followup02/static_footprint_launch.py'
spec=importlib.util.spec_from_file_location('candidate_static_launch',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
# Isolate parameter generation from Gazebo launch setup. This checks identity
# of the adapter handoff, not execution of original launch actions or domains.
sentinel=[object(),object()];module.base.launch_setup=lambda context:sentinel
returned=module.launch_setup(SimpleNamespace(environment={'BASE01_RUN_DIR':str(directory)}))
rows=[]
for robot in ('tb1','tb2','tb3'):
    after=yaml.safe_load((directory/f'peer_nav2_{robot}.yaml').read_text())
    static=after['global_costmap']['global_costmap']['ros__parameters']['static_layer']
    flag=static.pop('footprint_clearing_enabled')
    original=before[robot]['global_costmap']['global_costmap']['ros__parameters']['static_layer']
    if 'footprint_clearing_enabled' in original:static['footprint_clearing_enabled']=original['footprint_clearing_enabled']
    row=dict(robot=robot,true_bool=flag is True,other_yaml_semantics_equal=after==before[robot],
             original_copy_exact=(directory/f'peer_nav2_{robot}.before-static-footprint.yaml').read_bytes()==(CASE/f'peer_nav2_{robot}.yaml').read_bytes())
    rows.append(row)
passed=returned is sentinel and all(all(row[k] for k in ('true_bool','other_yaml_semantics_equal','original_copy_exact')) for row in rows)
result=dict(pass_=passed,no_Node=True,no_LaunchService=True,no_Gazebo=True,same_action_list_identity=returned is sentinel,robots=rows,
            limit='Pure generated-config/handoff check, not runtime parameter or launch execution proof.')
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if not passed:raise SystemExit(1)
