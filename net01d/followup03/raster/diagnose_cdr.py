"""One separately authorized same-object CDR self-consistency diagnosis only."""
from array import array
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'workspace/gz01'))
import peer_keepout as frozen
from broadcast_mask import broadcast_peer_mask
from nav_msgs.msg import OccupancyGrid
from rclpy.serialization import serialize_message,deserialize_message

state=json.loads((HERE/'input-states.json').read_text())['states'][0];robot='tb1'
poses=frozen.mask_poses(robot,state);origin=state['origins'][robot]
old=frozen.peer_mask(robot,poses,origin);new=broadcast_peer_mask(robot,poses,origin)
assert old.tobytes()==new.tobytes()
grid=OccupancyGrid();grid.header.frame_id='odom';grid.header.stamp.sec=3;grid.header.stamp.nanosec=123456789
grid.info.resolution=frozen.RESOLUTION;grid.info.width=grid.info.height=frozen.SIZE
grid.info.origin.position.x=float(origin[0]);grid.info.origin.position.y=float(origin[1]);grid.info.origin.orientation.w=1.
grid.data=array('b',old.tobytes())
first=serialize_message(grid);same=serialize_message(grid)
grid.data=array('b',new.tobytes());replacement=serialize_message(grid)
encoded=dict(first_original=first,same_object_original_data=same,same_object_candidate_data=replacement)
decoded={name:deserialize_message(body,OccupancyGrid)==grid for name,body in encoded.items()}
comparisons={name:dict(exact=first==body,differing_offsets=[i for i,(a,b) in enumerate(zip(first,body)) if a!=b])
    for name,body in encoded.items() if name!='first_original'}
for name,body in encoded.items():
    with (HERE/('CDR-diagnostic-'+name+'.cdr')).open('xb') as out:out.write(body)
result=dict(status='DIAGNOSTIC_ONLY',mask_exact=True,decoded_all_fields_equal_to_fixed_grid=decoded,
    comparisons=comparisons,layout=dict(encapsulation=[0,3],stamp=[4,11],frame_id_length=[12,15],
        frame_id_odom_nul=[16,20],alignment_padding=[21,23],map_load_time_sec_begins=24),
    sizes={name:len(body) for name,body in encoded.items()},prefixes={name:body[:32].hex() for name,body in encoded.items()},
    benchmark_executed=False,Node=0,ROS_init=0,scope='Same OccupancyGrid object, same fixed fields, original array serialized twice then only data replaced by identical candidate raster')
with (HERE/'CDR-self-consistency.json').open('x') as out:json.dump(result,out,indent=2);out.write('\n')
print(json.dumps(result))
