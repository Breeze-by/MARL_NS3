"""Broadcast raster implementation; selected only by explicit BoundPeer profile."""
import math
import numpy as np
import peer_keepout as frozen


def broadcast_peer_mask(robot,poses,origin):
    y=np.arange(frozen.SIZE,dtype=np.intp)[:,None]
    x=np.arange(frozen.SIZE,dtype=np.intp)[None,:]
    x=origin[0]+(x+.5)*frozen.RESOLUTION;y=origin[1]+(y+.5)*frozen.RESOLUTION
    blocked=np.zeros((frozen.SIZE,frozen.SIZE),dtype=bool)
    r=frozen.RADIUS+frozen.RESOLUTION/math.sqrt(2)
    for name,p in poses.items():
        if name!=robot:blocked |= (x-p[0])**2+(y-p[1])**2<=r*r
    return np.where(blocked,100,-1).astype(np.int8)
