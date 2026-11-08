import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid, Odometry
from geometry_msgs.msg import PointStamped, Twist
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient

import numpy as np
import math, time, threading
import datetime
from action_msgs.msg import GoalStatus
from rclpy.duration import Duration
from rclpy.time import Time
from rclpy.qos import QoSProfile, DurabilityPolicy
from rclpy.executors import ExternalShutdownException
from tf2_ros import Buffer, TransformException
from tf2_msgs.msg import TFMessage
from tf2_geometry_msgs import do_transform_point

lookahead_distance = 0.5  # forward looking distance
speed = 0.4  # maximum speed
expansion_size = 7  # wall expansion coefficient
target_error = 0.15  # margin of error to target
max_distance = 150.0

VISITED = []
ASSIGNED = {}
FAILED = {}
STATE_LOCK = threading.RLock()


def frontierB(matrix):
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            if matrix[i][j] == 0.0:
                if i > 0 and matrix[i-1][j] < 0:
                    matrix[i][j] = 2
                elif i < len(matrix)-1 and matrix[i+1][j] < 0:
                    matrix[i][j] = 2
                elif j > 0 and matrix[i][j-1] < 0:
                    matrix[i][j] = 2
                elif j < len(matrix[i])-1 and matrix[i][j+1] < 0:
                    matrix[i][j] = 2
    return matrix

def assign_groups(matrix):
    group = 1
    groups = {}
    for i in range(len(matrix)):
        for j in range(len(matrix[0])):
            if matrix[i][j] == 2:
                group = dfs(matrix, i, j, group, groups)
    return matrix, groups

def dfs(matrix, i, j, group, groups):
    # Preserve the original eight-neighbour DFS order without Python recursion.
    stack = [(i, j)]
    neighbours = ((1,0), (-1,0), (0,1), (0,-1), (1,1), (-1,-1), (-1,1), (1,-1))
    while stack:
        row, column = stack.pop()
        if row < 0 or row >= len(matrix) or column < 0 or column >= len(matrix[0]):
            continue
        if matrix[row][column] != 2:
            continue
        groups.setdefault(group, []).append((row, column))
        matrix[row][column] = 0
        stack.extend((row+dr, column+dc) for dr, dc in reversed(neighbours))
    return group + 1

def fGroups(groups):
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
    top_five_groups = [g for g in sorted_groups[:5] if len(g[1]) > 2]
    return top_five_groups

def calculate_centroid(x_coords, y_coords):
    n = len(x_coords)
    sum_x = sum(x_coords)
    sum_y = sum(y_coords)
    mean_x = sum_x / n
    mean_y = sum_y / n
    centroid = (mean_x, mean_y)
    return centroid

def visitedControl(targetP, robot_name=None):
    global VISITED
    for k in [*VISITED, *ASSIGNED.values(), *FAILED.get(robot_name, ())]:
        d = math.sqrt((k[0] - targetP[0])**2 + (k[1] - targetP[1])**2)
        if d < 0.2:
            return True
    return False

def costmap(data, width, height, resolution):
    data = np.array(data).reshape(height, width)
    wall = np.where(data == 100)
    for i in range(-expansion_size, expansion_size + 1):
        for j in range(-expansion_size, expansion_size + 1):
            if i == 0 and j == 0:
                continue
            x = wall[0] + i
            y = wall[1] + j
            x = np.clip(x, 0, height - 1)
            y = np.clip(y, 0, width - 1)
            data[x, y] = 100
    data = data * resolution
    return data

def reachable_free_cells(matrix, current):
    """Grid connectivity in the already-inflated map, without corner cutting."""
    pending = [current]
    reached = set()
    height, width = matrix.shape
    while pending:
        row, column = pending.pop()
        if (row, column) in reached or not (0 <= row < height and 0 <= column < width) or matrix[row, column] != 0:
            continue
        reached.add((row, column))
        for dr, dc in ((1,0), (-1,0), (0,1), (0,-1), (1,1), (-1,-1), (-1,1), (1,-1)):
            nr, nc = row+dr, column+dc
            if 0 <= nr < height and 0 <= nc < width:
                if dr and dc and (matrix[row,nc] != 0 or matrix[nr,column] != 0):
                    continue
                pending.append((nr, nc))
    return reached


def findClosestGroup(matrix, groups, current, resolution, originX, originY, robot_name=None):
    reachable = reachable_free_cells(matrix, current)
    best_centroid = None
    best_score = float('-inf')  # A large negative number to ensure proper comparison
    for i in range(len(groups)):
        middle = calculate_centroid([p[0] for p in groups[i][1]], [p[1] for p in groups[i][1]])
        # Keep the original group-size/distance ranking, but represent the group
        # by an actual free frontier cell, not a possibly occupied concave centroid.
        free_cells = [cell for cell in groups[i][1] if cell in reachable]
        if not free_cells:
            continue
        row, column = min(free_cells, key=lambda p: ((p[0]-middle[0])**2+(p[1]-middle[1])**2, p))
        centroid_world = ((column+0.5)*resolution + originX, (row+0.5)*resolution + originY)
        distance = math.sqrt((current[0] - middle[0])**2 + (current[1] - middle[1])**2)
        if distance > max_distance:
            continue
        if visitedControl(centroid_world, robot_name) == False:
            group_size = len(groups[i][1])
            score = group_size / (distance + 1e-6)
            if score > best_score:
                best_score = score
                best_centroid = centroid_world
    return best_centroid

def exploration(data, width, height, resolution, column, row, originX, originY, choice, last_target=None):
    global VISITED
    f = 1
    data = costmap(data, width, height, resolution)
    data[row][column] = 0  # Robot Current Location
    data[data > 5] = 1
    data = frontierB(data)
    data, groups = assign_groups(data)
    groups = fGroups(groups)

    if len(groups) == 0:
        f = -1
    else:
        data[data < 0] = 1
        coordinate = findClosestGroup(data, groups, (row, column), resolution, originX, originY, choice)
        if coordinate is None or (last_target and math.sqrt((coordinate[0] - last_target[0]) ** 2 + (coordinate[1] - last_target[1]) ** 2) < 0.5):
            f = -1
        else:
            ASSIGNED[choice] = coordinate
    if f == -1:
        return None
    else:
        return coordinate

def get(choice):
    now = datetime.datetime.now()
    time_string = now.strftime("%H:%M:%S")
    print(f"[BILGI] {time_string}: {choice+1}. ROAD REQUEST RECEIVED BY THE ROBOT")

def response(choice):
    now = datetime.datetime.now()
    time_string = now.strftime("%H:%M:%S")
    print(f"[BILGI] {time_string}: {choice+1}. ROAD REQUEST ANSWER SENT TO THE ROBOT")

class HeadquartersControl(Node):
    def __init__(self, num_robots):
        super().__init__("headquarters_control")
        self.shutdown_initiated = False
        self.worker_error = None
        self.last_successful_targets = {}
        self.tf = {}
        self.tf_subscriptions = []
        self.robots = {}  # Dictionary to hold robot data

        # Subscribers for multiple robots dynamically
        self.map_sub = self.create_subscription(
            OccupancyGrid, "merge_map", self.map_callback, 10
        )
        self.robot_odom_subs = {}
        self.robot_nav_clients = {}
        self.robot_positions = {}
        self.local_maps = {}
        self.subscription_cmd_vel = {}

        # Action clients and odometry subscribers for dynamic robots
        self.num_robots = num_robots  # Change this to the number of robots dynamically
        for i in range(self.num_robots):
            robot_name = f"tb{i + 1}"
            self.robot_odom_subs[robot_name] = self.create_subscription(
                Odometry, f"{robot_name}/odom", lambda msg, r=robot_name: self.robot_odom_callback(msg, r), 10
            )
            self.robot_nav_clients[robot_name] = ActionClient(self, NavigateToPose, f"{robot_name}/navigate_to_pose")
            self.subscription_cmd_vel[robot_name] = self.create_subscription(
                Twist, f"{robot_name}/cmd_vel", lambda msg, r=robot_name: self.robot_status_control(msg, r), 4
            )
            self.create_subscription(OccupancyGrid, f"/{robot_name}/map",
                lambda msg, r=robot_name: self.local_map_callback(msg, r),
                QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
            self.tf[robot_name] = Buffer(cache_time=Duration(seconds=15), node=self)
            latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
            self.tf_subscriptions += [
                self.create_subscription(TFMessage, f"/{robot_name}/tf", lambda m, r=robot_name: self.tf_callback(m, r, False), 100),
                self.create_subscription(TFMessage, f"/{robot_name}/tf_static", lambda m, r=robot_name: self.tf_callback(m, r, True), latched)]
            
            self.robot_states = {f"tb{i+1}": "idle" for i in range(self.num_robots)}  # Track robot states


        # State variables
        self.map_data = None
        self.resolution = None
        self.origin = None
        self.map_width = None
        self.map_height = None

        # Threads for goal navigation
        for i in range(self.num_robots):
            threading.Thread(target=self.exploration_worker, args=(i + 1,), daemon=True).start()

        self.get_logger().info("Navigation to map center initialized.")

    def tf_callback(self, msg, robot_name, static):
        for transform in msg.transforms:
            if static:
                self.tf[robot_name].set_transform_static(transform, robot_name)
            else:
                self.tf[robot_name].set_transform(transform, robot_name)

    def map_callback(self, msg):
        if msg.header.frame_id != "merge_map":
            raise ValueError('Central map must be expressed in merge_map')
        with STATE_LOCK:
            self.map_data = np.array(msg.data).reshape(msg.info.height, msg.info.width)
            self.resolution = msg.info.resolution
            self.origin = (msg.info.origin.position.x, msg.info.origin.position.y)
            self.map_width, self.map_height = msg.info.width, msg.info.height

    def local_map_callback(self, msg, robot_name):
        if msg.header.frame_id != 'map':
            raise ValueError('Expected a namespaced local map frame')
        with STATE_LOCK:
            self.local_maps[robot_name] = msg

    def nav_goal_in_local_map(self, robot_name, x, y):
        with STATE_LOCK:
            grid = self.local_maps.get(robot_name)
        if grid is None:
            return False
        origin = grid.info.origin
        q = origin.orientation
        if not math.isclose(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w, 1.0, abs_tol=1e-5):
            return False
        yaw = math.atan2(2*q.w*q.z, 1-2*q.z*q.z)
        dx, dy = x-origin.position.x, y-origin.position.y
        column = math.floor((math.cos(yaw)*dx+math.sin(yaw)*dy)/grid.info.resolution)
        row = math.floor((-math.sin(yaw)*dx+math.cos(yaw)*dy)/grid.info.resolution)
        return (0 <= column < grid.info.width and 0 <= row < grid.info.height
                and grid.data[row*grid.info.width+column] == 0)

    def robot_odom_callback(self, msg, robot_name):
        point = PointStamped()
        point.header = msg.header
        point.point = msg.pose.pose.position
        try:
            transform = self.tf[robot_name].lookup_transform('merge_map', msg.header.frame_id, Time.from_msg(msg.header.stamp))
            position = do_transform_point(point, transform).point
        except TransformException:
            # Never substitute untransformed odom or a default (0, 0) position.
            with STATE_LOCK:
                self.robot_positions.pop(robot_name, None)
            return
        with STATE_LOCK:
            self.robot_positions[robot_name] = (position.x, position.y)

    def exploration_worker(self, robot_number):
        try:
            self.start_exploration(robot_number)
        except Exception as error:
            self.worker_error = f'tb{robot_number}: {type(error).__name__}: {error}'
            self.get_logger().fatal('Exploration worker failed: ' + self.worker_error)
            # A failed daemon worker must terminate the ROS process, so the
            # existing supervisor sees a failed controller rather than a live shell.
            self.context.try_shutdown()

    def robot_status_control(self, msg, robot_name):
        """Command velocity control for individual robots."""
        pass

    def start_exploration(self, robot_number):
        robot_name = f"tb{robot_number}"
        while rclpy.ok():
            target = None
            # One map/metadata/position version and one reservation decision.
            with STATE_LOCK:
                if self.map_data is not None and robot_name in self.robot_positions and self.robot_states[robot_name] == "idle":
                    position = self.robot_positions[robot_name]
                    column = math.floor((position[0]-self.origin[0])/self.resolution)
                    row = math.floor((position[1]-self.origin[1])/self.resolution)
                    if 0 <= column < self.map_width and 0 <= row < self.map_height:
                        target = exploration(self.map_data, self.map_width, self.map_height,
                            self.resolution, column, row, *self.origin, robot_name,
                            last_target=self.last_successful_targets.get(robot_name))
                        if target:
                            self.robot_states[robot_name] = "active"
            if target:
                self.get_logger().info(f"Target for {robot_name} in merge_map is {target}")
                self.send_goal(robot_name, target)
            time.sleep(8)

    def release_target(self, robot_name, succeeded=False, failed=False):
        with STATE_LOCK:
            target = ASSIGNED.pop(robot_name, None)
            if succeeded and target is not None:
                VISITED.append(target)
                self.last_successful_targets[robot_name] = target
            if failed and target is not None:
                FAILED.setdefault(robot_name, []).append(target)
                self.get_logger().warning(f'{robot_name} target {target} failed; excluded for this robot in this run')
            self.robot_states[robot_name] = "idle"

    def send_goal(self, robot_name, target):
        """Send a navigation goal to the robot."""
        if robot_name in self.robot_nav_clients and self.robot_nav_clients[robot_name].wait_for_server(timeout_sec=2.0):
            goal = NavigateToPose.Goal()
            point = PointStamped()
            point.header.frame_id = 'merge_map'
            point.point.x, point.point.y = target
            try:
                transform = self.tf[robot_name].lookup_transform('map', 'merge_map', Time())
                local = do_transform_point(point, transform).point
            except TransformException:
                self.release_target(robot_name)
                self.get_logger().warning(f'{robot_name} goal not sent: map alignment unavailable')
                return
            if not self.nav_goal_in_local_map(robot_name, local.x, local.y):
                self.get_logger().warning(f'{robot_name} goal outside known local free map: {(local.x, local.y)}')
                self.release_target(robot_name, failed=robot_name in self.local_maps)
                return
            goal.pose.pose.position.x, goal.pose.pose.position.y = local.x, local.y
            goal.pose.pose.orientation = transform.transform.rotation
            goal.pose.header.frame_id = "map"
            goal.pose.header.stamp = self.get_clock().now().to_msg()

            # Send goal and set up callbacks
            future = self.robot_nav_clients[robot_name].send_goal_async(goal, feedback_callback=self.feedback_callback)
            future.add_done_callback(lambda f: self.goal_response_callback(robot_name, f))
        else:
            self.release_target(robot_name)

    def goal_response_callback(self, robot_name, future):
        try:
            goal_handle = future.result()
        except Exception:
            self.release_target(robot_name)
            raise
        if not goal_handle.accepted:
            self.get_logger().warning(f"{robot_name} navigation goal rejected")
            self.release_target(robot_name, failed=True)
            return
        self.get_logger().info(f"{robot_name} navigation goal accepted uuid={bytes(goal_handle.goal_id.uuid).hex()}")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda f: self.goal_result_callback(robot_name, f.result()))

    def feedback_callback(self, feedback_msg):
        """Handle feedback from the action server."""
        # Optionally process feedback, e.g., log progress
        pass

    def goal_result_callback(self, robot_name, result):
        self.get_logger().info(f"{robot_name} navigation result status={result.status}")
        self.release_target(robot_name, result.status == GoalStatus.STATUS_SUCCEEDED,
                            result.status == GoalStatus.STATUS_ABORTED)
        # Idle means no active assignment, not frontier exhaustion. The run
        # observer saves uniquely named snapshots; no source-directory writes.


def main(args=None):
    rclpy.init(args=args)

    node = Node("control_node")
    node.declare_parameter('robot_count', 2)  # Default value if not passed

    # Get the 'num_robots' parameter value correctly
    robot_count = node.get_parameter('robot_count').get_parameter_value().integer_value
    print(f"Number of robots: {robot_count}")  
    control = HeadquartersControl(robot_count)  

    try:
        rclpy.spin(control)
        if control.worker_error:
            raise RuntimeError(control.worker_error)
    except ExternalShutdownException:
        if control.worker_error:
            raise RuntimeError(control.worker_error)
    except KeyboardInterrupt:
        control.get_logger().info("Shutting down exploration.")
    finally:
        # Goal cancellation and observed motion stop are handled by the run
        # supervisor before stopping this process; node exit alone is not a stop.
        control.destroy_node()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
