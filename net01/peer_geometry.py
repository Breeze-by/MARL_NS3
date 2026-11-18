"""Opt-in Nav2 raw peer obstacle; HQ center-space predicates stay unchanged."""
import json
import math
import os
from pathlib import Path
import time
import numpy as np

REVISION = 'peer-body-postfilter-inflation-v3'
CONTRACT_FILE = 'config/NAVIGATION_PEER_BODY_GEOMETRY_V3.json'
REVISION_V5 = 'peer-body-postfilter-circumscribed-v5'
CONTRACT_FILES = {REVISION: CONTRACT_FILE,
                  REVISION_V5: 'config/NAVIGATION_PEER_BODY_GEOMETRY_V5.json'}


def load_contract(revision):
    if revision not in CONTRACT_FILES:
        raise ValueError('Unknown peer geometry revision')
    contract = json.loads((Path(__file__).resolve().parent/CONTRACT_FILES[revision]).read_text())
    if contract['revision'] != revision:
        raise ValueError('Unknown peer geometry revision')
    return contract


def physical_peer_mask(robot, poses, origin):
    # Cell-center raster covers every cell intersecting the .237m body since
    # .30 - .05/sqrt(2) > .237. It does not guarantee the entire .063m margin.
    y = origin[1] + (np.arange(400)[:, None] + .5)*.05
    x = origin[0] + (np.arange(400)[None, :] + .5)*.05
    blocked = np.zeros((400, 400), dtype=bool)
    for name, point in poses.items():
        if name != robot:
            blocked |= (x-point[0])**2 + (y-point[1])**2 <= .30**2
    return np.where(blocked, 100, -1).astype(np.int8)


def install_producer_geometry(node, directory, session_id):
    contract = load_contract(os.environ['NET01_NAVIGATION_PEER_GEOMETRY_REVISION'])
    node.nav2_peer_mask_builder = physical_peer_mask
    node.nav2_peer_geometry_metadata = dict(
        radius_m=contract['nav2_lethal_radius_m'],
        radius_semantics='Nav2 raw lethal obstacle raster radius, not HQ center clearance',
        center_clearance_radius_m=contract['center_clearance_radius_m'],
        nav2_peer_geometry=contract)
    import peer_keepout
    from business_peer import RADIUS
    record = dict(revision=contract['revision'], PID=os.getpid(), session_id=session_id,
                  directory=str(directory), applied_monotonic_ns=time.monotonic_ns(),
                  actual_mask_builder=physical_peer_mask.__module__+'.'+physical_peer_mask.__name__,
                  actual_state_metadata=node.nav2_peer_geometry_metadata,
                  actual_HQ_center_radius_m=peer_keepout.RADIUS,
                  business_peer_center_radius_copy_m=RADIUS,
                  scope='Producer instance only; shared peer_mask and HQ route/endpoint predicates unchanged')
    with (Path(directory)/'peer-geometry-producer.json').open('x') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
    return record
