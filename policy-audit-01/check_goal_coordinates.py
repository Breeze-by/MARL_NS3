"""Check recorded shared goals against the recorded local-from-shared TF."""
import json
import math
from audit import ROOT, OUT, dump

rows = json.loads((OUT/'GOAL_CHAIN.json').read_text())
cache = {}
checks = []
for row in rows:
    case = row['case']
    if case not in cache:
        records = json.loads((ROOT/f'net01e/followup04/event-cache/{case}.json').read_text())
        cache[case] = {r['decision_id']:r for r in records['inferences']}
    inference = cache[case][row['decision_id']]
    grid = inference['latest_costmap_by_robot'][row['robot']]
    tx, ty, yaw = grid['local_from_shared']
    x, y = row['merge_map_target']
    expected = [tx+math.cos(yaw)*x-math.sin(yaw)*y,
                ty+math.sin(yaw)*x+math.cos(yaw)*y]
    error = math.dist(expected, row['actual_goal_position'][:2])
    checks.append(dict(case=case,decision_id=row['decision_id'],robot=row['robot'],
        uuid=row['uuid'],shared_target=[x,y],recorded_local_from_shared=[tx,ty,yaw],
        tf_stamp=grid['tf_stamp'],expected_local_xy=expected,
        actual_local_xy=row['actual_goal_position'][:2],error_m=error,
        matches=error<1e-9 and row['actual_goal_frame']=='map'))
dump('GOAL_COORDINATE_CHECK.json', dict(goals=len(checks),passed=sum(r['matches'] for r in checks),
    max_error_m=max(r['error_m'] for r in checks),rows=checks,
    scope='Recorded navigation-grid TF at this decision; compares actual request XY, not simulator truth.'))
assert all(row['matches'] for row in checks)
print(f"{len(checks)}/{len(checks)} actual local Nav2 coordinates match recorded TF; max {max(r['error_m'] for r in checks)}m")
