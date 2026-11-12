def peer_mask(robot, poses, origin):
    y,x=np.indices((SIZE,SIZE))
    x=origin[0]+(x+.5)*RESOLUTION;y=origin[1]+(y+.5)*RESOLUTION
    blocked=np.zeros((SIZE,SIZE),dtype=bool)
    # Include any mask cell intersecting the continuous exclusion disk.
    r=RADIUS+RESOLUTION/math.sqrt(2)
    for name,p in poses.items():
        if name!=robot:blocked |= (x-p[0])**2+(y-p[1])**2<=r*r
    # Outside peers is NO_INFORMATION, not free: Keepout otherwise overwrites
    # primary unknown(255) with background0. Primary-layer copy clears old disks.
    return np.where(blocked,100,-1).astype(np.int8)
