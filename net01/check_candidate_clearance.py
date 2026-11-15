"""Geometry and original-NPZ qualification; no NN, ROS init or simulator."""
import argparse
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

HERE=Path(__file__).resolve().parent
REPO=HERE.parent
sys.path.insert(0,str(REPO/'workspace/src/multi_robot_exploration'))
from multi_robot_exploration import frontier
from multi_robot_exploration.allocation import distances
from candidate_clearance import VERSION,circular_costmap,install_candidate_clearance

CONTRACT=dict(id=VERSION,nav2_robot_radius_m=dict(tb1=.25,tb2=.25,tb3=.25),map_resolution_m=.05)


def geometry():
    source=np.zeros((41,41),dtype=np.int16)
    source[20,20]=100;source[0,40]=-1;source[40,0]=50
    before=source.copy();original=frontier.costmap
    result=circular_costmap(source,41,41,.05,.25)
    assert np.array_equal(source,before)
    assert result[0,40]<0 and result[40,0]>0
    # Distance to an occupied square, rather than only its centre.
    for row,column in np.argwhere(result==0):
        x=max(abs(int(column)-20)*.05-.025,0.)
        y=max(abs(int(row)-20)*.05-.025,0.)
        assert math.hypot(x,y)>.25
    corridor=np.full((41,41),-1,dtype=np.int16)
    corridor[13:26,:]=0;corridor[[12,26],:]=100
    start,target=(19,2),(19,38)
    old=original(corridor,41,41,.05);old[start]=0
    new=circular_costmap(corridor,41,41,.05,.25);new[start]=0
    assert target not in distances(old,start,.05)
    assert target in distances(new,start,.05)
    narrow=np.full((41,41),-1,dtype=np.int16)
    narrow[15:24,:]=0;narrow[[14,24],:]=100
    blocked=circular_costmap(narrow,41,41,.05,.25);blocked[start]=0
    assert target not in distances(blocked,start,.05)
    diagonal=np.zeros((41,41),dtype=np.int16)
    np.fill_diagonal(diagonal,100)
    blocked=circular_costmap(diagonal,41,41,.05,.25)
    assert (30,10) not in distances(blocked,(10,30),.05)
    boundary=np.zeros((20,20),dtype=np.int16);boundary[0,0]=100;boundary[0,19]=-1
    bounded=circular_costmap(boundary,20,20,.05,.25)
    assert bounded[19,19]==0 and bounded[0,19]<0 and bounded[0,0]>0
    calls=[];sentinel=object()
    def observe():
        calls.append(frontier.costmap)
        return sentinel
    allocator=SimpleNamespace(map={'resolution':.05},get_observation=observe)
    node=SimpleNamespace(allocator=allocator)
    install_candidate_clearance(node,CONTRACT)
    assert allocator.get_observation() is sentinel
    assert len(calls)==1 and calls[0] is not original and frontier.costmap is original
    def fail():
        raise RuntimeError('original-observation-failure')
    failing=SimpleNamespace(allocator=SimpleNamespace(map={'resolution':.05},get_observation=fail))
    install_candidate_clearance(failing,CONTRACT)
    try:failing.allocator.get_observation()
    except RuntimeError as error:assert str(error)=='original-observation-failure'
    else:raise AssertionError('Original exception was swallowed')
    assert frontier.costmap is original
    return dict(status='PASS',checks=dict(source_grid_not_modified=True,
        free_centres_have_configured_disk_clearance_from_occupied_squares=True,
        physically_wide_channel_connected=True,undersized_channel_stays_blocked=True,
        diagonal_wall_not_crossed=True,boundary_no_wrap=True,unknown_and_soft_nonzero_never_cleared=True,
        original_observation_object_and_single_call_preserved=True,
        costmap_override_scoped_and_restored_after_success_and_failure=True),
        formula='R + resolution/sqrt(2)',radius_m=.25,resolution_m=.05,
        conservative_occupied_centre_clearance_m=.25+.05/math.sqrt(2),
        limit='Only grid-centre footprint clearance; inherited grid routing has no corner cutting. Continuous/dynamic path validation remains Nav2.')


def original_replays(output):
    sys.path.insert(0,str(REPO/'local-runs/exploration-repair-20261113/candidate'))
    from replay_filters import replay
    rows=[]
    case=REPO/'local-runs/causal-followup-20261113/j'
    for sequence in (8,9,10,11):
        result=replay(case,sequence,'tb2',clearance_contract=CONTRACT)
        assert result['original_valid_counts'][1]==0
        assert result['replayed_valid_counts'][1]>0
        assert result['source_shared_grid_unchanged'] and result['global_costmap_restored']
        assert all(candidate['valid'] and candidate['local_map_valid'] for candidate in result['candidates'])
        rows.append(result)
    with (output/'j-clearance-replay.json').open('x') as stream:
        json.dump(rows,stream,indent=2,default=lambda value:value.item());stream.write('\n')
    return dict(status='PASS',original_zero_candidate_slots=4,
        repaired_valid_counts=[row['replayed_valid_counts'] for row in rows],
        source_grids_and_original_observation_pipeline_preserved=True,
        original_seed_output_replayed_not_regenerated=True,
        scope='Original received grids/state/peer sequences; no truth, extra encoding, NN or physical navigation test')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    result=dict(contract=CONTRACT,geometry=geometry(),original_npz=original_replays(args.output))
    with (args.output/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,default=lambda value:value.item());stream.write('\n')
    print(json.dumps(result,default=lambda value:value.item()))


if __name__=='__main__':main()
