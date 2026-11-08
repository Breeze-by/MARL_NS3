"""Zero-node fault injection for known RPC/stop-ownership regressions."""
import json
from types import SimpleNamespace, MethodType
from unittest.mock import patch
from maps import PROJECT, dump
import run_gazebo as module


class Clock:
    def __init__(self):
        self.value = 0.

    def now(self):
        return self.value

    def spin(self, node, timeout_sec):
        self.value += timeout_sec
        if hasattr(node, 'sim'):
            node.sim = self.value
            node.counts['model_states'] += 1
            for robot in module.ROBOTS:
                node.latest[robot+'/model_state'] = self.value
                node.latest[robot+'/drive'] = self.value
                node.drive[robot][1] = node.sent[robot]


def fixture(clock):
    node = SimpleNamespace(phase='stop', next_stop_zero=0., service_clients={},
                           sent=dict.fromkeys(module.ROBOTS, 0), events=[], controller_directory=None)
    node.event = lambda kind, **values: node.events.append(dict(kind=kind, fake_wall=clock.value, **values))
    def send(robot):
        node.sent[robot] += 1
    node.zero_publishers = {r:SimpleNamespace(publish=lambda msg, r=r:send(r)) for r in module.ROBOTS}
    node.stop_zeros = MethodType(module.Observer.stop_zeros, node)
    return node


def stuck_rpc(available):
    clock = Clock()
    node = fixture(clock)
    future = SimpleNamespace(done=lambda:False, canceled=False)
    def cancel():
        future.canceled = True
    future.cancel = cancel
    node.service_clients['/controlled'] = SimpleNamespace(
        service_is_ready=lambda:available, call_async=lambda request:future)
    with patch.object(module.time, 'monotonic', clock.now), patch.object(module.rclpy, 'spin_once', clock.spin):
        try:
            module.Observer.call(node, object, '/controlled', object(), timeout=.2)
        except RuntimeError as error:
            message = str(error)
        else:
            raise AssertionError('Controlled unavailable RPC unexpectedly returned')
    assert all(n>=4 for n in node.sent.values())
    assert future.canceled==available
    return dict(service_available=available, error=message,
                per_robot_zero_publications=node.sent, fake_elapsed=clock.value,
                pending_future_canceled=future.canceled)


def ownership_case(terminal, authority):
    clock = Clock()
    node = fixture(clock)
    node.sim = 0.
    node.authority_stopped = authority
    node.paused_robots = set()
    node.cancelled_goals = {}
    node.statuses = {r:{(r+'-goal', 5 if terminal else 2)} for r in module.ROBOTS}
    node.active_goals = {r:set() if terminal else {r+'-goal'} for r in module.ROBOTS}
    node.positions = {r:(0., 0., 0., 0., 0.) for r in module.ROBOTS}
    node.current_models = set(module.ROBOTS)
    node.latest = {r+'/'+key:0. for r in module.ROBOTS for key in ('model_state', 'drive')}
    node.counts = {'model_states':1}
    node.drive = {r:[0., 0, 0., 0., 0.] for r in module.ROBOTS}
    node.hazard = None
    node.call = lambda *args, **kwargs: SimpleNamespace(return_code=0, goals_canceling=[], success=True)
    with patch.object(module.time, 'monotonic', clock.now), patch.object(module.rclpy, 'spin_once', clock.spin):
        stopped = module.Observer.stop_motion(node)
    assert stopped==(terminal and authority)
    certificates = [e for e in node.events if e['kind']=='observed_stop']
    assert bool(certificates)==stopped
    return dict(all_owned_UUIDs_terminal=terminal, authority_stopped=authority,
        returned_stop=stopped, fake_elapsed=clock.value, stop_certificates=len(certificates))


def run():
    output = PROJECT/'evidence/stop-fixture-03'
    output.mkdir(parents=True, exist_ok=False)
    result = dict(status='PASS', rpc_cases=[stuck_rpc(False), stuck_rpc(True)],
        ownership_cases=[ownership_case(False, True), ownership_case(True, False), ownership_case(True, True)],
        actual_ros_node_init=0, actual_service_requests=0, nn_forward=0, env_reset=0,
        env_step=0, optimizer_step=0, gazebo_start=0,
        caveat='Fake-clock/publisher/service fixtures prove control flow only, never physical stopping.')
    dump(output/'result.json', result)
    print(json.dumps(result, indent=2))


if __name__=='__main__':
    run()
