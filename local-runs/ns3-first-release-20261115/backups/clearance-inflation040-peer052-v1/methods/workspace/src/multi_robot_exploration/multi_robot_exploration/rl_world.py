"""Evaluator/sensor-only SDF projection. Never passed to a policy or encoder."""
from pathlib import Path
import math
import xml.etree.ElementTree as ET
import numpy as np
from scipy.ndimage import distance_transform_edt, label


def transform(text='0 0 0 0 0 0'):
    x, y, z, roll, pitch, yaw = map(float, text.split())
    cr, sr, cp, sp, cy, sy = (math.cos(roll), math.sin(roll), math.cos(pitch),
                             math.sin(pitch), math.cos(yaw), math.sin(yaw))
    matrix = np.eye(4)
    matrix[:3, :3] = [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                      [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]]
    matrix[:3, 3] = [x, y, z]
    return matrix


class ProjectedWorld:
    def __init__(self, source, assets, variant, resolution=.05, reference_positions=None):
        if variant not in ('A', 'B'):
            raise ValueError('Only predeclared A/B maps exist')
        self.resolution = resolution
        world = ET.parse(source).getroot().find('world')
        state = {m.attrib['name']: m for m in world.find('state').findall('model')}
        boxes, meshes = [], []
        for model in world.findall('model'):
            name = model.attrib['name']
            actual = state.get(name)
            model_t = transform(actual.findtext('pose') if actual is not None else
                                model.findtext('pose', '0 0 0 0 0 0'))
            links = {} if actual is None else {l.attrib['name']: l for l in actual.findall('link')}
            for link in model.findall('link'):
                link_t = (transform(links[link.attrib['name']].findtext('pose'))
                          if link.attrib['name'] in links else
                          model_t @ transform(link.findtext('pose', '0 0 0 0 0 0')))
                for collision in link.findall('collision'):
                    t = link_t @ transform(collision.findtext('pose', '0 0 0 0 0 0'))
                    geometry = collision.find('geometry')[0]
                    if geometry.tag == 'plane' and name == 'ground_plane':
                        continue
                    if geometry.tag == 'box':
                        if not np.allclose(t[2, :2], 0, atol=1e-8):
                            raise ValueError('Projection requires upright source boxes')
                        boxes.append((name, t, np.fromstring(geometry.findtext('size'), sep=' ')))
                    elif geometry.tag == 'mesh':
                        uri = geometry.findtext('uri')
                        if uri != 'model://suv/meshes/suv.obj':
                            raise ValueError('Unvalidated collision mesh: ' + uri)
                        mesh = Path(assets) / 'suv/meshes/suv.obj'
                        vertices = np.array([[float(v) for v in line.split()[1:4]]
                                             for line in mesh.open() if line.startswith('v ')])
                        scale = np.fromstring(geometry.findtext('scale'), sep=' ')
                        points = (vertices*scale) @ t[:3, :3].T + t[:3, 3]
                        meshes.append((name, points.min(0), points.max(0)))
                    else:
                        raise ValueError('Unsupported source collision: ' + geometry.tag)
        corners = []
        for name, t, size in boxes:
            if name == 'my_floor':
                corners.extend((t[:2, 3] + np.array([x, y]) @ t[:2, :2].T)
                               for x in (-size[0]/2, size[0]/2)
                               for y in (-size[1]/2, size[1]/2))
        corners = np.array(corners)
        lower = np.floor(corners.min(0)/resolution)*resolution
        upper = np.ceil(corners.max(0)/resolution)*resolution
        self.origin = tuple(lower)
        self.shape = tuple(int(v) for v in np.rint((upper-lower)/resolution)[::-1])
        self.bounds = [*lower.tolist(), *upper.tolist()]
        self.excluded_meshes = []
        for name, low, high in meshes:
            if np.any(high[:2] < lower) or np.any(low[:2] > upper):
                self.excluded_meshes.append(dict(name=name, low=low.tolist(), high=high.tolist(),
                                                reason='entire mesh outside fixed task ROI'))
            else:
                raise ValueError('Relevant mesh needs faithful rasterization before training')
        yy, xx = np.indices(self.shape)
        x = lower[0] + (xx+.5)*resolution
        y = lower[1] + (yy+.5)*resolution
        self.obstacles = np.zeros(self.shape, dtype=bool)
        self.lidar_obstacles = np.zeros(self.shape, dtype=bool)
        self.source_boxes = len(boxes)
        for name, t, size in boxes:
            local_x = (x-t[0, 3])*t[0, 0]+(y-t[1, 3])*t[1, 0]
            local_y = (x-t[0, 3])*t[0, 1]+(y-t[1, 3])*t[1, 1]
            # Conservative cell/rectangle intersection (not thin-wall centre loss).
            pad = resolution/2*np.abs(t[:2, :2]).sum(axis=0)
            footprint = (np.abs(local_x) <= size[0]/2+pad[0]) & (np.abs(local_y) <= size[1]/2+pad[1])
            bottom, top = t[2, 3]-size[2]/2, t[2, 3]+size[2]/2
            if bottom < .30 and top > .03:
                self.obstacles |= footprint
            if bottom <= .131 <= top:
                self.lidar_obstacles |= footprint
        if variant == 'B':
            for cx, cy in ((-3., -3.), (4., 0.)):
                block = (np.abs(x-cx) <= .3+resolution/2) & (np.abs(y-cy) <= .3+resolution/2)
                self.obstacles |= block
                self.lidar_obstacles |= block
        self.clearance = distance_transform_edt(~self.obstacles)*resolution-resolution/math.sqrt(2)
        components, _ = label(self.clearance >= .25)
        if reference_positions is None:
            reference_positions = ((5., 4.), (-4.5, 4.), (6., -1.5))
        spawn_cells = [self.cell(p) for p in reference_positions]
        spawn_labels = {int(components[p]) for p in spawn_cells}
        if 0 in spawn_labels:
            raise ValueError('Source spawn is not physically clear')
        # Fixed independently defined robot-centre-reachable free task region.
        # This reference stays private; neither candidate masks nor route search use it.
        self.reference_free = np.isin(components, list(spawn_labels)) & ~self.obstacles

    def cell(self, position):
        return (math.floor((position[1]-self.origin[1])/self.resolution),
                math.floor((position[0]-self.origin[0])/self.resolution))

    def inside(self, cell):
        return 0 <= cell[0] < self.shape[0] and 0 <= cell[1] < self.shape[1]

    def position(self, cell):
        return np.array([self.origin[0]+(cell[1]+.5)*self.resolution,
                         self.origin[1]+(cell[0]+.5)*self.resolution])

    def clear(self, position, radius=.25):
        p = self.cell(position)
        return self.inside(p) and self.clearance[p] >= radius
