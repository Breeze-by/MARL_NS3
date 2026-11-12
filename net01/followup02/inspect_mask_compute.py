"""One no-Node timing observation of frozen functions using sealed A04 state."""
import json,os,sys,time
from pathlib import Path
from array import array
import numpy as np
import peer_keepout as frozen
from nav_msgs.msg import OccupancyGrid
root=Path('/mnt');out=root/'net01/followup02'
rows=[json.loads(l) for l in (root/'runs/net01-a-corridor-6201-04/peer-keepout.jsonl').read_text().splitlines()]
state=next(r for r in rows if r['sequence']==383)
spans=[]
for repeat in range(5):
    for robot in frozen.ROBOTS:
        last=time.monotonic_ns();cpu=time.thread_time_ns();stages={}
        def mark(name):
            global last,cpu
            now=time.monotonic_ns();c=time.thread_time_ns();stages[name]=dict(wall_ns=now-last,thread_cpu_ns=c-cpu);last=now;cpu=c
        grid=OccupancyGrid();grid.header.frame_id='odom';grid.info.resolution=frozen.RESOLUTION;grid.info.width=grid.info.height=frozen.SIZE
        grid.info.origin.position.x,grid.info.origin.position.y=state['origins'][robot];grid.info.origin.orientation.w=1.;mark('grid_metadata')
        poses=frozen.mask_poses(robot,state);mark('mask_poses')
        data=frozen.peer_mask(robot,poses,state['origins'][robot]);mark('peer_mask')
        grid.data=array('b',data.tobytes());mark('grid_data')
        spans.append(dict(repeat=repeat,robot=robot,stages=stages,shape=list(data.shape),occupied_cells=int(np.count_nonzero(data==100))))
(out/'MASK_COMPUTE_OBSERVATION.json').write_text(json.dumps(dict(scope='No ROS init/Node/Publish/GZ/NN; current isolated frozen computation, not historical CPU profiling',python=sys.executable,python_version=sys.version,numpy_version=np.__version__,numpy_file=np.__file__,peer_module=frozen.__file__,environment={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','PYTHONPATH')},source_case='net01-a-corridor-6201-04',source_sequence=383,spans=spans,calls=dict(Node=0,Gazebo=0,NN=0,publish=0)),indent=2)+'\n')
