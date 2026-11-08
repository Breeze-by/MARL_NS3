"""Route-only recovery: connect only a blocked seed, never rewrite maps."""
import math
import numpy as np
from multi_robot_exploration.allocation import distances
from multi_robot_exploration import frontier


def seed_bridge(shared,own,shared_inflated,own_inflated,nav,seed,resolution,age_s,origin,pose,peers,peer_clearance=.70,allow_soft_cost=False):
    cost_facts=dict(nav_seed_cost=None if nav is None else int(nav[seed]),allow_soft_cost=allow_soft_cost)
    if nav is None:
        return None,dict(reason='missing_costmap',**cost_facts)
    if age_s>1.:
        return None,dict(reason='stale_costmap',**cost_facts)
    nav_free=((nav>=0)&(nav<99)) if allow_soft_cost else nav==0
    if not nav_free[seed]:
        return None,dict(reason='Nav2_seed_not_below_inscribed' if allow_soft_cost else 'Nav2_seed_not_strict_free',**cost_facts)
    if shared_inflated[seed]==0 and own_inflated[seed]==0:
        return None,dict(reason='normal_seed_unchanged',**cost_facts)
    # Existing .25m robot radius plus the original square inflation extent.
    limit=math.ceil((.25+math.sqrt(2)*frontier.expansion_size*resolution)/resolution)*resolution
    rr,cc=np.indices(shared.shape)
    xx=origin[0]+(cc+.5)*resolution;yy=origin[1]+(rr+.5)*resolution
    peer_grid_margin=peer_clearance+resolution/math.sqrt(2)
    if any(math.hypot(pose[0]-p[0],pose[1]-p[1])<peer_clearance or
           math.hypot(xx[seed]-p[0],yy[seed]-p[1])<peer_grid_margin for p in peers):
        return None,dict(reason='peer_guard_at_seed',**cost_facts)
    trusted=nav_free&(shared==0)&(own==0)&(
        np.hypot(xx-pose[0],yy-pose[1])<=limit)
    for p in peers:
        trusted &= np.hypot(xx-p[0],yy-p[1])>=peer_grid_margin
    # Preserve the original allocator's normalization of its own current cell.
    trusted[seed]=True
    paths,predecessors=distances((~trusted).astype(int),seed,resolution,return_predecessors=True)
    exits=[p for p in paths if shared_inflated[p]==0 and own_inflated[p]==0]
    if not exits:
        return None,dict(reason='no_trusted_connection_to_original_free',limit_m=limit,**cost_facts)
    end=min(exits,key=lambda p:(paths[p],p))
    path=[end];width=shared.shape[1]
    while path[-1]!=seed:
        path.append(divmod(int(predecessors[path[-1][0]*width+path[-1][1]]),width))
    path.reverse();clear=set(path)
    for a,b in zip(path,path[1:]):
        if a[0]!=b[0] and a[1]!=b[1]:
            clear.update(((a[0],b[1]),(b[0],a[1])))
    points=[tuple(pose[:2])]+[(float(xx[p]),float(yy[p])) for p in path]
    minimum_peer=None
    for a,b in zip(points,points[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];squared=dx*dx+dy*dy
        for p in peers:
            u=max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/squared)) if squared else 0.
            distance=math.hypot(p[0]-a[0]-u*dx,p[1]-a[1]-u*dy)
            minimum_peer=distance if minimum_peer is None else min(distance,minimum_peer)
    if minimum_peer is not None and minimum_peer<peer_clearance:
        return None,dict(reason='peer_guard_on_connection',minimum_ROS_peer_distance_m=minimum_peer,**cost_facts)
    return tuple(sorted(clear)),dict(reason='trusted_known_free_seed_connection',
        **cost_facts,
        limit_m=limit,path_length_m=paths[end],exit=list(end),path=[list(p) for p in path],
        cleared_inflation_cells=len(clear),
        minimum_ROS_peer_distance_m=minimum_peer,
        outside_seed_raw_occupied_or_unknown_cleared=int(sum(
            shared[p]!=0 or own[p]!=0 for p in clear if p!=seed)))
