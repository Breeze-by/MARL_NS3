"""BASE-01 Frontier implementation, lifted without algorithm changes."""
import math
import threading
import numpy as np

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

