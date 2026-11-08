"""Task-event timing fixtures without importing ROS or any model."""
import ast
from pathlib import Path
import unittest

source=Path(__file__).with_name('analyze_recorded.py')
functions=[node for node in ast.parse(source.read_text()).body
           if isinstance(node,ast.FunctionDef) and node.name in ('interval_duration','task_timeline')]
namespace={}
exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),'exec'),namespace)


class TaskEvents(unittest.TestCase):
    def test_overlapping_intervals_are_not_double_counted(self):
        self.assertEqual(namespace['interval_duration']([(2,5),(3,4),(4,8),(10,11)]),7)

    def test_rejection_and_timeout_keep_actual_response_times(self):
        request=dict(kind='rl_actual_nav2_goal_request',robot='tb1',sim=10.,request_uuid='owned')
        response=dict(kind='rl_actual_nav2_goal_response',robot='tb1',sim=11.,request_uuid='owned',accepted=False)
        rejected=namespace['task_timeline']([request,response],'tb1',0.,20.)
        self.assertEqual(rejected['waiting_no_dispatched_task_s'],19.)
        self.assertEqual(rejected['pending_response_s'],1.)
        self.assertEqual(rejected['accepted_active_s'],0.)
        self.assertEqual(rejected['rejected_actual_responses'],1)
        response=dict(response,accepted=True)
        events=[request,response,
            dict(kind='goal_accepted',robot='tb1',sim=10.),
            dict(kind='timeout_cancel_dispatched',robot='tb1',sim=14.),
            dict(kind='rl_actual_nav2_goal_result',robot='tb1',sim=15.,request_uuid='owned',raw_status=5),
            dict(kind='nav2_terminal_classified',robot='tb1',sim=15.,reason='navigation_timeout',high_level_status='aborted'),
            dict(kind='goal_terminal',robot='tb1',sim=15.,status='aborted')]
        timedout=namespace['task_timeline'](events,'tb1',0.,20.)
        self.assertEqual(timedout['waiting_no_dispatched_task_s'],15.)
        self.assertEqual(timedout['pending_response_s'],1.)
        self.assertEqual(timedout['accepted_active_s'],4.)
        self.assertEqual(timedout['high_level_failure_count'],1)
        self.assertEqual(timedout['timeout_terminal_failures'],1)


if __name__=='__main__':unittest.main()
