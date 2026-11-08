import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav_msgs.msg import OccupancyGrid
import numpy as np

def merge_maps(maps, frame_id, map_poses, output_resolution=None):
    """Resample calibrated local grids in a common frame; occupied wins conflicts.

    map_poses contains the measured/declared common<-local-map planar poses.
    It is never obtained from live Gazebo ground truth by this node.
    """
    import copy
    import math

    projected = []
    for grid, (tx, ty, yaw) in zip(maps, map_poses):
        q = grid.info.origin.orientation
        norm = q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w
        if not math.isclose(norm, 1.0, abs_tol=1e-5) or abs(q.x) > 1e-6 or abs(q.y) > 1e-6:
            raise ValueError('OccupancyGrid origin must have a valid planar unit quaternion')
        origin_yaw = math.atan2(2*q.w*q.z, 1-2*q.z*q.z)
        c, sn = math.cos(yaw), math.sin(yaw)
        ox, oy = grid.info.origin.position.x, grid.info.origin.position.y
        gx, gy = tx+c*ox-sn*oy, ty+sn*ox+c*oy
        angle = yaw + origin_yaw
        c, sn = math.cos(angle), math.sin(angle)
        width = grid.info.width * grid.info.resolution
        height = grid.info.height * grid.info.resolution
        corners = [(gx+c*x-sn*y, gy+sn*x+c*y) for x, y in ((0,0), (width,0), (0,height), (width,height))]
        projected.append((grid, gx, gy, c, sn, corners))

    min_x = min(p[0] for item in projected for p in item[5])
    min_y = min(p[1] for item in projected for p in item[5])
    max_x = max(p[0] for item in projected for p in item[5])
    max_y = max(p[1] for item in projected for p in item[5])
    resolution = min(grid.info.resolution for grid in maps) if output_resolution is None else output_resolution
    if output_resolution is not None:
        min_x = math.floor(min_x/resolution)*resolution
        min_y = math.floor(min_y/resolution)*resolution
    merged_map = OccupancyGrid()
    # Do not mutate the first source header, or imply all inputs are newer than
    # the oldest contributing map.
    merged_map.header = copy.deepcopy(min(maps, key=lambda g: (g.header.stamp.sec, g.header.stamp.nanosec)).header)
    merged_map.header.frame_id = frame_id
    merged_map.info.origin.position.x = min_x
    merged_map.info.origin.position.y = min_y
    merged_map.info.origin.orientation.w = 1.0
    merged_map.info.resolution = resolution
    merged_map.info.width = int(np.ceil((max_x-min_x)/resolution - 1e-9))
    merged_map.info.height = int(np.ceil((max_y-min_y)/resolution - 1e-9))
    xs, ys = np.meshgrid(min_x+(np.arange(merged_map.info.width)+0.5)*resolution,
                         min_y+(np.arange(merged_map.info.height)+0.5)*resolution)
    result = np.full(xs.shape, -1, dtype=np.int16)
    for grid, gx, gy, c, sn, _ in projected:
        # Inverse mapping samples source cells at each destination cell centre;
        # it handles rotated origins, calibrated map yaw and unequal resolution.
        local_x = c*(xs-gx) + sn*(ys-gy)
        local_y = -sn*(xs-gx) + c*(ys-gy)
        columns = np.floor(local_x/grid.info.resolution).astype(int)
        rows = np.floor(local_y/grid.info.resolution).astype(int)
        valid = (columns >= 0) & (columns < grid.info.width) & (rows >= 0) & (rows < grid.info.height)
        data = np.asarray(grid.data).reshape(grid.info.height, grid.info.width)
        result[valid] = np.maximum(result[valid], data[rows[valid], columns[valid]])
    merged_map.data = result.ravel().tolist()
    return merged_map

class MergeMapNode(Node):
    def __init__(self):
        super().__init__('merge_map_node')
        self.frame_id = self.declare_parameter('frame_id', 'merge_map').get_parameter_value().string_value
        self.robot_count = self.declare_parameter('robot_count', 3).get_parameter_value().integer_value  # Default to 3 robots

        poses = self.declare_parameter('map_poses', rclpy.Parameter.Type.DOUBLE_ARRAY).value
        if poses is None or len(poses) != 3*self.robot_count:
            raise ValueError('map_poses must explicitly supply common<-local-map [x,y,yaw] for each robot')
        self.map_poses = [poses[i:i+3] for i in range(0, len(poses), 3)]
        self.output_resolution = self.declare_parameter('output_grid_resolution', 0.0).value or None
        self.get_logger().info(f'merge source={__file__} output_grid_resolution={self.output_resolution}')

        # Use a transient_local QoS to ensure the merged map is latched
        qos = QoSProfile(depth=10)
        qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        qos.reliability = ReliabilityPolicy.RELIABLE

        # Publisher for the merged map
        self.publisher = self.create_publisher(OccupancyGrid, '/' + self.frame_id, qos)

        # Store maps dynamically
        self.maps = [None] * self.robot_count

        # Create subscriptions dynamically
        for i in range(self.robot_count):
            topic = f'/tb{i + 1}/map'
            self.create_subscription(
                OccupancyGrid, topic, lambda msg, idx=i: self.map_callback(msg, idx), qos
            )

    def map_callback(self, msg, index):
        self.maps[index] = msg
        self.try_merge_and_publish()

    def try_merge_and_publish(self):
        if all(self.maps):  # Ensure all maps are available
            merged_map = merge_maps(self.maps, self.frame_id, self.map_poses, self.output_resolution)
            self.publisher.publish(merged_map)
            # self.get_logger().info('Merged map published!')

def main(args=None):
    rclpy.init(args=args)
    merge_map_node = MergeMapNode()
    rclpy.spin(merge_map_node)
    merge_map_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
