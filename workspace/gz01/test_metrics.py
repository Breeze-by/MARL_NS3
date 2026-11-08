"""Direct metric checks only; no ROS, policy, environment or robot commands."""
import unittest
from types import SimpleNamespace
import numpy as np
from metrics import measure, sample_received, thresholds


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.reference = SimpleNamespace(shape=(4, 4), origin=(0., 0.), resolution=1.,
            obstacles=np.zeros((4, 4), dtype=bool), reference_free=np.ones((4, 4), dtype=bool))
        self.reference.obstacles[:, 0] = True
        self.reference.reference_free[:, 0] = False

    def test_unknown_does_not_count(self):
        result=measure(np.full((4,4), -1), self.reference)
        self.assertEqual(result['coverage'], 0)
        self.assertIsNone(result['free_precision_physical'])

    def test_known_occupied_is_not_free_coverage(self):
        self.assertEqual(measure(np.full((4,4), 100), self.reference)['coverage'], 0)

    def test_false_free_is_excluded_and_quality_reported(self):
        result=measure(np.zeros((4,4)), self.reference)
        self.assertEqual(result['correct_free_cells'], 12)
        self.assertEqual(result['false_free_physical_area_m2'], 4)
        self.assertIn('free_precision_below_0.95', result['map_quality_warnings'])

    def test_inflation_is_not_physical_truth(self):
        self.reference.reference_free[:, 1] = False
        result=measure(np.zeros((4,4)), self.reference)
        self.assertEqual(result['false_free_physical_area_m2'], 4)
        self.assertEqual(result['reference_free_cells'], 8)

    def test_received_origin_and_unknown_outside(self):
        grid=np.array([[0, 100], [-1, 0]])
        sampled=sample_received(grid, 1., (1.,1.,0.), self.reference)
        self.assertEqual(sampled[1:3,1:3].tolist(), grid.tolist())
        self.assertTrue(np.all(sampled[0] == -1))

    def test_received_rotation(self):
        grid=np.array([[0, 100], [-1, 0]])
        sampled=sample_received(grid, 1., (3.,1.,np.pi/2), self.reference)
        self.assertEqual(sampled[1:3,1:3].tolist(), np.rot90(grid,-1).tolist())

    def test_perfect_truth_quality_and_all_free_painting(self):
        obstacles=np.zeros((100,100), dtype=bool)
        obstacles[[0,-1],:] = True
        obstacles[:,[0,-1]] = True
        reference=SimpleNamespace(shape=obstacles.shape,origin=(0.,0.),resolution=.05,
            obstacles=obstacles,reference_free=~obstacles)
        perfect=np.where(obstacles,100,0)
        self.assertEqual(measure(perfect,reference)['coverage'],1.)
        self.assertTrue(measure(perfect,reference)['map_quality_valid'])
        painted=perfect.copy();painted[:]=0;painted[0,:20]=100
        result=measure(painted,reference)
        self.assertEqual(result['coverage'],1.)
        self.assertGreater(result['free_precision_physical'],.95)
        self.assertFalse(result['map_quality_valid'])
        self.assertIn('known_obstacle_recall_0.10m_below_0.80',result['map_quality_warnings'])

    def test_same_physical_grid_with_padding_is_identical(self):
        cells=np.arange(16).reshape(4,4)
        padded=np.pad(cells,((2,3),(4,1)),constant_values=-1)
        original=sample_received(cells,1.,(0.,0.,0.),self.reference)
        shifted=sample_received(padded,1.,(-4.,-2.,0.),self.reference)
        self.assertTrue(np.array_equal(original,shifted))

    def test_shifted_map_loses_quality_and_regression_is_visible(self):
        obstacles=np.zeros((40,40),dtype=bool);obstacles[:,3:6]=True
        reference=SimpleNamespace(shape=obstacles.shape,origin=(0.,0.),resolution=.05,
            obstacles=obstacles,reference_free=~obstacles)
        perfect=np.where(obstacles,100,0)
        shifted=sample_received(perfect,.05,(.5,0.,0.),reference)
        before=measure(perfect,reference);after=measure(shifted,reference)
        self.assertTrue(before['map_quality_valid'])
        self.assertFalse(after['map_quality_valid'])
        self.assertLess(after['coverage'],before['coverage'])

    def test_receipt_threshold_not_source_header(self):
        curve=[dict(receipt_sim=30.,source_stamp=10.,coverage=.6),
               dict(receipt_sim=40.,source_stamp=15.,coverage=.96)]
        result=thresholds(curve, 30.)
        self.assertEqual(result['0.95']['elapsed_sim_s'], 10.)
        self.assertEqual(result['0.5']['elapsed_sim_s'], 0.)
        self.assertTrue(result['0.5']['initially_reached'])
        self.assertIsNone(result['0.98'])
        curve[1]['map_quality_valid']=False;curve[0]['map_quality_valid']=True
        self.assertIsNone(thresholds(curve,30.,require_quality=True)['0.95'])


if __name__ == '__main__':
    unittest.main()
