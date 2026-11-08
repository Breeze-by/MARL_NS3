"""Fixed category/identity selection and static geometry only; no rollout or NN."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
PHASE=ROOT/'gz-01'
sys.path.insert(0,str(PHASE/'workspace/rl02'))
sys.path.insert(0,str(PHASE/'workspace/src/multi_robot_exploration'))
from maps import write_sdf,LEFT,RIGHT,BOTTOM,TOP,THICKNESS
from metrics import load_reference


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:stream.write(json.dumps(data,indent=2)+'\n')


def main():
    catalog=json.loads((ROOT/'rl-04/evidence/corpus-01/maps.json').read_text())
    older=json.loads((ROOT/'rl-02/evidence/map-qualification-01/maps.json').read_text())
    specs=[('dev-open','DEV','Open',None,0),
        ('dev-rooms','DEV','Rooms','partition_grid-1101',101),
        ('dev-hard-corridor','DEV','Corridors','branching_corridors-4202',502),
        ('dev-unequal-corridor','DEV','Corridors','branching_corridors-4203',501),
        ('final-open-ring','FINAL','Open/ring','loop_chambers-5102',601),
        ('final-rooms','FINAL','Rooms','central_hub_chambers-2101',201),
        ('final-corridor','FINAL','Corridors','branching_corridors-5202',602)]
    records=[]
    for identity,split,category,name,pose_seed in specs:
        world_path=PHASE/f'inputs/worlds/{identity}.sdf';world_path.parent.mkdir(parents=True,exist_ok=True)
        if world_path.exists():raise FileExistsError(world_path)
        if name is None:
            boxes=[(LEFT,BOTTOM,RIGHT,BOTTOM+THICKNESS),(LEFT,TOP-THICKNESS,RIGHT,TOP),
                (LEFT,BOTTOM,LEFT+THICKNESS,TOP),(RIGHT-THICKNESS,BOTTOM,RIGHT,TOP)]
            write_sdf(world_path,'gz01_open_boundary',0,boxes)
            positions=[[-4.,4.],[4.,4.],[0.,-4.]]
            provenance=dict(kind='new predeclared open benchmark, not a changed historical world',
                generator='workspace/rl02/maps.py::write_sdf',rule='Only same existing four boundary-wall rectangles; no inner obstacles',
                map_seed=0,positions_rule='Fixed category layout before first policy/sensor outcome; no performance selection')
        else:
            row=next(r for r in catalog+older if r['name']==name)
            source=ROOT/row['source'];shutil.copyfile(source,world_path)
            pose=next(p for p in row['positions'] if p['seed']==pose_seed)
            positions=pose['positions']
            provenance=dict(kind='existing unchanged generated SDF and original declared positions',
                path=row['source'],sha256=row['source_sha256'],map_seed=row['map_seed'],
                previous_split=row['split'],geometry_name=name)
            if sha(world_path)!=row['source_sha256']:raise ValueError('Original source identity differs: '+name)
        reference,touched=load_reference(world_path,ROOT/'base-01-econ/assets/gazebo_models',positions,require_closed=True)
        clearances=[float(reference.clearance[reference.cell(p)]) for p in positions]
        pair=min(math.dist(a,b) for index,a in enumerate(positions) for b in positions[index+1:])
        if min(clearances)<.40 or pair<1.:raise ValueError('Fixed scene physically unqualified; no silent replacement')
        scene=dict(id=identity,split=split,category=category,world_relative_phase=str(world_path.relative_to(PHASE)),
            world_sha256=sha(world_path),source_provenance=provenance,position_seed=pose_seed,
            physics_seed=2026110601,
            robots=[dict(name=f'tb{i+1}',x=p[0],y=p[1],yaw=0.) for i,p in enumerate(positions)],
            reference_bounds=reference.bounds,reference_area_m2=float(reference.reference_free.sum())*.05**2,
            spawn_clearance_m=clearances,minimum_spawn_pair_m=pair,reference_boundary_connections=touched,
            qualification='Static collision/component/spawn only; not actual Gazebo or policy performance',
            maximum_autonomy_sim_s=600,maximum_decisions=130)
        write(PHASE/f'inputs/scenes/{identity}.json',scene);records.append(scene)
    model_source=ROOT/'rl-04/runs/formal-01/checkpoint-00512.pt'
    model=PHASE/'references/current.pt';model.parent.mkdir(exist_ok=True)
    with model_source.open('rb') as source,model.open('xb') as destination:shutil.copyfileobj(source,destination)
    expected='6d4c51ba6f96737ccd89393c9738a888acb82606770483f97dd562051ee01d5d'
    if sha(model)!=expected:raise ValueError('Reference checkpoint identity mismatch')
    for relative in ('runs/selection.json','runs/formal-01/summary.json','runs/formal-01/process-exit.json'):
        target=PHASE/relative;target.parent.mkdir(parents=True,exist_ok=True)
        with (ROOT/'rl-04'/relative).open('rb') as source,target.open('xb') as destination:shutil.copyfileobj(source,destination)
    (PHASE/'runs/formal-01/checkpoint-00512.pt').symlink_to('../../references/current.pt')
    write(PHASE/'inputs/SCENE_LOCK.json',dict(status='PREDECLARED STATIC PHYSICAL QUALIFICATION ONLY',
        scenes=records,selection='By requested category and known diagnostic identity before new policy results; no replacement based on scores',
        final_scope='Withheld from GZ-01 tuning only; earlier2D familiarity disclosed, not unseen-domain claim',
        calls=dict(Node=0,NN=0,Gazebo=0,environment_step=0,sensor_scan=0,optimizer=0)))
    print(json.dumps(dict(status='PASS',scenes=len(records),dev=4,final=3,
        all_closed=True,minimum_spawn_clearance_m=min(min(r['spawn_clearance_m']) for r in records),
        minimum_pair_m=min(r['minimum_spawn_pair_m'] for r in records),NN=0,Node=0,Gazebo=0),indent=2))


if __name__=='__main__':main()
