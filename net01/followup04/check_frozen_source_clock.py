"""One actual-scheduler/typed-message check, no rclpy.init or Node."""
import argparse
import ast
from array import array
import importlib.util
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
import sys

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from followup04.frozen_source_clock import FrozenSourceClock,wheel_message
from nav_msgs.msg import OccupancyGrid
from rclpy.serialization import serialize_message


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output;output.mkdir(exist_ok=False);checks={}
    clock=FrozenSourceClock();clock.advance(0);counts=dict(odom=0,wheel=0,scan=0)
    for sim_ns in range(10_000_000,1_000_000_001,10_000_000):
        for kind in clock.advance(sim_ns):counts[kind]+=1
    checks['configured_sim_ceiling_30_10_5_under100Hzclock']=counts==dict(odom=30,wheel=10,scan=5)
    clock.costmap_due(1,1_000_000_000);held=clock.scan_header_ns
    checks['wall_progress_with_paused_sim_does_not_emit_or_refresh']=all(
        not clock.advance(1_000_000_000) and not clock.costmap_due(1,1_000_000_000)
        and clock.scan_header_ns==held for _ in range(200))
    cost=FrozenSourceClock()
    checks['strict_costmap_500million_integer_ns']=cost.costmap_due(1,600_000_000) and not cost.costmap_due(1,1_100_000_000) and cost.costmap_due(1,1_100_000_001)
    wheel=wheel_message(1_234_567_890);body=serialize_message(wheel)
    checks['both_wheels_one_complete212byte_packet_same_header']=(len(body)==212 and
        [t.child_frame_id for t in wheel.transforms]==['wheel_left_link','wheel_right_link'] and
        all(t.header.frame_id=='base_link' and t.header.stamp.sec==1 and
            t.header.stamp.nanosec==234_567_890 for t in wheel.transforms))
    # Execute the actual source's inner grid/stamp functions without its Node.
    path=HERE/'followup01/continuous_dds.py';tree=ast.parse(path.read_text())
    source=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='source')
    functions=[n for n in ast.walk(source) if isinstance(n,ast.FunctionDef) and n.name in ('stamp','grid')]
    captured=[];env=dict(robot=1,clock_ns=1_010_000_000,clock_increment=10_000_000,
        frozen_source=True,source_clock=clock,OccupancyGrid=OccupancyGrid,array=array,
        node=SimpleNamespace(get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=1_234_567_890))),
        emit=lambda pub,message,robot,kind,header:captured.append((message,header)))
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[])),str(path),'exec'),env)
    env['grid'](None,200,200,'synthetic_costmap',1);grid,header=captured[-1]
    checks['actual_grid_odom_frame_200square_integer_Nodeclock']=(grid.header.frame_id=='odom' and
        header==1_234_567_890 and grid.info.width==200 and grid.info.height==200 and len(grid.data)==40000)
    env['grid'](None,250,220,'synthetic_map',1)
    checks['actual_map_uses_held_scan_header']=captured[-1][1]==held
    env['frozen_source']=False;env['grid'](None,200,200,'synthetic_costmap',1)
    checks['legacy_actual_grid_header_and_frame_unchanged']=(captured[-1][0].header.frame_id=='map' and captured[-1][1]==1_000_000_000)
    spec=importlib.util.spec_from_file_location('actual_continuous_fixture',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    checks['legacy_default_and_original_steady_branches_retained']=(inspect.signature(module.source).parameters['source_clock_contract'].default=='legacy-steady' and
        'node.create_timer(1/30,odom,clock=steady)' in path.read_text() and
        "transform(p,'base_link','wheel_left_link',r),clock=steady)" in path.read_text())
    result=dict(status='PASS' if len(checks)==8 and all(checks.values()) else 'FAIL',checks=checks,
        counts_per_one_sim_s=counts,wheel_CDR_bytes=len(body),costmap_CDR_bytes=len(serialize_message(grid)),
        scope='Actual pure scheduler, actual generated messages and actual AST grid function. No rclpy.init/Node/ROSclock scheduling/Gazebo/native/NN/Policy. Legacy branch/default check is static, not a rerun of old timing qualifications.')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    return int(result['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())
