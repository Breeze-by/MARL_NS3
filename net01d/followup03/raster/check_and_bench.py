"""One fixed rootfs equivalence/CDR check and AB/BA raster microbenchmark."""
from array import array
import inspect
import json
import math
from pathlib import Path
import statistics
import sys
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'workspace/gz01'))
import numpy as np
import peer_keepout as frozen
from rclpy.serialization import serialize_message,deserialize_message
from nav_msgs.msg import OccupancyGrid
from broadcast_mask import broadcast_peer_mask

PAIRS=6
BATCHES=5
WARMUP=2


def main():
    output=HERE/'r2';output.mkdir(exist_ok=False)
    oracle=frozen.peer_mask;states=json.loads((HERE/'input-states.json').read_text())['states']
    with (output/'oracle-source.py').open('x') as out:out.write(inspect.getsource(oracle))
    with (output/'helper-at-run.py').open('x') as out:out.write((HERE/'broadcast_mask.py').read_text())
    with (output/'test-at-run.py').open('x') as out:out.write(Path(__file__).read_text())
    result=dict(status='FAIL',runtime=dict(numpy_version=np.__version__,numpy_path=np.__file__,
        python=sys.executable,python_version=sys.version,oracle_module=frozen.__file__,
        index_dtype=str(np.dtype(np.intp))),pairs=PAIRS,batches_per_timing=BATCHES,
        warmup_batches_per_role=WARMUP,ROS_init=0,Node=0,models=0,tests=[])
    try:
        cases=[]
        for state in states:
            for robot in frozen.ROBOTS:
                cases.append((f'actual-seq{state["sequence"]}-{robot}',robot,
                    frozen.mask_poses(robot,state),state['origins'][robot]))
        radius=frozen.RADIUS+frozen.RESOLUTION/math.sqrt(2)
        for direction,(x,y) in dict(x=(radius,0.),y=(0.,radius),diagonal=(radius/math.sqrt(2),radius/math.sqrt(2))).items():
            for side,toward in (('inside',0.),('tangent',None),('outside',math.inf)):
                p=tuple(value if toward is None or value==0 else float(np.nextafter(value,toward)) for value in (x,y))
                cases.append((f'boundary-{direction}-{side}','tb1',
                    dict(tb1=(0.,0.),tb2=p,tb3=(100.,100.)),(-.025,-.025)))
        def cdr(data,origin):
            grid=OccupancyGrid();grid.header.frame_id='odom';grid.header.stamp.sec=3;grid.header.stamp.nanosec=123456789
            grid.info.resolution=frozen.RESOLUTION;grid.info.width=grid.info.height=frozen.SIZE
            grid.info.origin.position.x=float(origin[0]);grid.info.origin.position.y=float(origin[1]);grid.info.origin.orientation.w=1.
            grid.data=array('b',data.tobytes())
            return serialize_message(grid)
        for name,robot,poses,origin in cases:
            old=oracle(robot,poses,origin);new=broadcast_peer_mask(robot,poses,origin)
            equal=old.shape==new.shape==(400,400) and old.dtype==new.dtype==np.dtype('int8') and old.tobytes()==new.tobytes()
            if not equal:
                (output/'first-failure-reference-mask.bin').write_bytes(old.tobytes());(output/'first-failure-candidate-mask.bin').write_bytes(new.tobytes())
                raise AssertionError('Exact mask mismatch: '+name)
            old_cdr,new_cdr=cdr(old,origin),cdr(new,origin)
            assert old_cdr[12:21]==new_cdr[12:21]==b'\x05\x00\x00\x00odom\x00'
            nonpadding_equal=old_cdr[:21]+old_cdr[24:]==new_cdr[:21]+new_cdr[24:]
            decoded_equal=deserialize_message(old_cdr,OccupancyGrid)==deserialize_message(new_cdr,OccupancyGrid)
            if not nonpadding_equal or not decoded_equal:
                (output/'first-failure-reference.cdr').write_bytes(old_cdr);(output/'first-failure-candidate.cdr').write_bytes(new_cdr)
                raise AssertionError('Nonpadding CDR or decoded fields mismatch: '+name)
            if not result['tests']:
                (output/'reference-raw.cdr').write_bytes(old_cdr);(output/'candidate-raw.cdr').write_bytes(new_cdr)
            result['tests'].append(dict(case=name,cells=old.size,exact_int8_bytes=True,
                CDR_all_nonpadding_bytes_equal=nonpadding_equal,decoded_CDR_equal=decoded_equal,raw_CDR_equal=old_cdr==new_cdr,
                excluded_comparison_padding=[21,24],reference_padding_hex=old_cdr[21:24].hex(),candidate_padding_hex=new_cdr[21:24].hex(),
                CDR_bytes=len(old_cdr),oracle_cell00=int(old[0,0])))
        state=states[0]
        def batch(function):
            for robot in frozen.ROBOTS:function(robot,frozen.mask_poses(robot,state),state['origins'][robot])
        functions=dict(reference=oracle,candidate=broadcast_peer_mask)
        for function in functions.values():
            for _ in range(WARMUP):batch(function)
        timings=[]
        for pair in range(PAIRS):
            order=('reference','candidate') if pair%2==0 else ('candidate','reference')
            for role in order:
                wall=time.monotonic_ns();thread=time.thread_time_ns();process=time.process_time_ns()
                for _ in range(BATCHES):batch(functions[role])
                process=time.process_time_ns()-process;thread=time.thread_time_ns()-thread;wall=time.monotonic_ns()-wall
                timings.append(dict(pair=pair,role=role,three_robot_batches=BATCHES,
                    thread_CPU_ns=thread,process_CPU_ns=process,wall_ns=wall,
                    thread_CPU_ns_per_batch=thread/BATCHES,process_CPU_ns_per_batch=process/BATCHES,wall_ns_per_batch=wall/BATCHES))
        means={role:{key:statistics.mean(row[key] for row in timings if row['role']==role)
            for key in ('thread_CPU_ns_per_batch','process_CPU_ns_per_batch','wall_ns_per_batch')} for role in functions}
        result.update(status='PASS_EQUIVALENCE_WITH_MICROBENCH',timings=timings,means=means,
            candidate_reference_ratios={key:means['candidate'][key]/means['reference'][key] for key in means['reference']},
            scope='Actual frozen peer_mask oracle. Two logged states x3 owners plus9 finite nextafter/tangent cases; all160000int8 cells exact; real OccupancyGrid decoded fields and every nonpadding CDR byte equal. RawCDR equality is not claimed: only fixedIDL alignment padding21..23 is excluded in comparison copies; actual serialized bytes unchanged. '
                'Timing is3mask_poses+3peer_mask calls, excluding grid setter/CDR/publication or fullPeer/Gateway/native. No runtime selection/cache/NP configuration changes. '
                'Measured local computation cost is not complete60ms producer span, Full freshness, RTF or all-real-input mathematical proof.')
    except BaseException as error:result['first_error']=repr(error);raise
    finally:
        with (output/'result.json').open('x') as out:json.dump(result,out,indent=2);out.write('\n')
        print(json.dumps(result),flush=True)


if __name__=='__main__':main()
