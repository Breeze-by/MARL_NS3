from array import array
import json,statistics,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.serialization import serialize_message,deserialize_message
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import Header
calls=[]
def forbidden(*args,**kwargs):
 calls.append('forbidden ROS initialization or Node construction')
 raise RuntimeError(calls[-1])
rclpy.init=forbidden
Node.__init__=forbidden
N=10

def fields(header):
 return dict(sec=header.stamp.sec,nanosec=header.stamp.nanosec,frame_id=header.frame_id)

def measure(function):
 function()  # One untimed warmup, fixed before all10 measured calls.
 wall=[];cpu=[]
 for _ in range(N):
  w=time.perf_counter_ns();c=time.thread_time_ns()
  function()
  cpu.append(time.thread_time_ns()-c);wall.append(time.perf_counter_ns()-w)
 return dict(samples=N,warmups=1,wall_ns=wall,thread_cpu_ns=cpu,
  median_wall_ns=statistics.median(wall),median_thread_cpu_ns=statistics.median(cpu),
  max_wall_ns=max(wall))

result=dict(scope='0init/0Node serialization only; no DDS publisher, transport, Native, Gazebo or physical validation',
 fixed_iterations=N,sizes=[],forbidden_calls=calls)
try:
 for side in (200,400):
  grid=OccupancyGrid();grid.header.stamp.sec=12;grid.header.stamp.nanosec=345678901
  grid.header.frame_id='tb2/odom';grid.info.map_load_time.sec=5;grid.info.map_load_time.nanosec=567
  grid.info.resolution=.125  # Exactly representable synthetic float32, no tolerance oracle.
  grid.info.width=side;grid.info.height=side
  grid.info.origin.position.x=-9.;grid.info.origin.position.y=1.5;grid.info.origin.position.z=.125
  grid.info.origin.orientation.w=1.
  pattern=array('b',range(-1,101));count=side*side
  grid.data=pattern*(count//len(pattern))+pattern[:count%len(pattern)]
  body=serialize_message(grid)
  full=deserialize_message(body,OccupancyGrid)
  row=dict(side=side,cells=count,cdr_bytes=len(body),header=fields(grid.header),
   full_grid_all_typed_fields_exact=(full==grid),data_bytes_exact=(full.data.tobytes()==grid.data.tobytes()))
  if not row['full_grid_all_typed_fields_exact'] or not row['data_bytes_exact']:raise AssertionError(row)
  row['serialize_full']=measure(lambda:serialize_message(grid))
  row['deserialize_full']=measure(lambda:deserialize_message(body,OccupancyGrid))
  row['full_decode_then_header']=measure(lambda:fields(deserialize_message(body,OccupancyGrid).header))
  try:
   prefix=deserialize_message(body,Header)
   row['header_prefix_supported']=True
   row['prefix_all_header_fields_exact']=prefix==grid.header and fields(prefix)==fields(full.header)
   if not row['prefix_all_header_fields_exact']:raise AssertionError('Header prefix field mismatch')
   row['prefix_decode_then_header']=measure(lambda:fields(deserialize_message(body,Header)))
  except Exception as error:
   row['header_prefix_supported']=False;row['prefix_error']=repr(error)
  result['sizes'].append(row)
 result['status']='PASS' if all(r.get('header_prefix_supported') and r.get('prefix_all_header_fields_exact') for r in result['sizes']) else 'PREFIX_UNSUPPORTED_OR_MISMATCH'
 result['Node']=0;result['rclpy_init']=0;result['Gazebo']=0
except BaseException as error:
 result['status']='FAIL';result['error']=repr(error);raise
finally:
 Path(__file__).with_name('result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2),flush=True)
