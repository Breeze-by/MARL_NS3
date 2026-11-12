"""Audit saved grids only; do not rerun the admitted ROS fixture.

Whole-cell containment is a sufficient geometric interior certificate, not a
reimplementation of Nav2 polygon rasterization. All remaining cells are UNKNOWN.
"""
import json
from pathlib import Path
import numpy as np

OUT=Path(__file__).resolve().parent/'static-footprint-fixture-01'

def inside(point,polygon):
    x,y=point;result=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:result=not result
    return result

with np.load(OUT/'fixed-input.npz',allow_pickle=False) as z:
    raw=z['cells'].copy();origin=z['origin'].tolist();res=float(z['resolution'])
first=json.loads((OUT/'true/original-pose.json').read_text())['actual_published_footprint']
result=[]
for enabled in ('false','true'):
    for phase in ('original-pose','moved-no-map','moved-new-map'):
        meta=json.loads((OUT/enabled/(phase+'.json')).read_text())
        with np.load(OUT/enabled/(phase+'.npz'),allow_pickle=False) as z:grid=z['raw_uint8_grid'].copy()
        current=meta['actual_published_footprint']
        cells=[]
        for kind,mask in [('raw_occupied_not_lethal',(raw==100)&(grid!=254)),
                          ('raw_unknown_free',(raw==-1)&(grid==0))]:
            for row,col in np.argwhere(mask):
                x=origin[0]+int(col)*res;y=origin[1]+int(row)*res
                corners=[(x,y),(x+res,y),(x+res,y+res),(x,y+res)]
                now=all(inside(p,current) for p in corners)
                old=all(inside(p,first) for p in corners)
                cells.append(dict(kind=kind,row=int(row),col=int(col),value=int(grid[row,col]),
                    cell_corners=corners,whole_cell_inside_current_polygon=now,
                    whole_cell_inside_first_polygon=old,
                    classification='CURRENT_INTERIOR' if now else 'PREVIOUS_INTERIOR' if old else 'BOUNDARY_OR_OUTSIDE_UNKNOWN'))
        result.append(dict(enabled=enabled,phase=phase,shape_matches=grid.shape==raw.shape,
            geometry_matches=meta['origin']==origin and meta['resolution']==res,
            altered_raw_occupied_or_unknown_cells=cells,
            uncertified_cells=sum(c['classification']=='BOUNDARY_OR_OUTSIDE_UNKNOWN' for c in cells),
            peer_sentinel_nonlethal=meta['peer_sentinel_nonlethal']))

halo=[]
for phase in ('original-pose','moved-no-map','moved-new-map'):
    with np.load(OUT/'false'/(phase+'.npz'),allow_pickle=False) as z:a=z['raw_uint8_grid'].copy()
    with np.load(OUT/'true'/(phase+'.npz'),allow_pickle=False) as z:b=z['raw_uint8_grid'].copy()
    halo.append(dict(phase=phase,master_changed_cells=int(np.count_nonzero(a!=b)),
                     changed_raw_occupied=int(np.count_nonzero((a!=b)&(raw==100))),
                     changed_raw_unknown=int(np.count_nonzero((a!=b)&(raw==-1))),
                     changed_raw_free=int(np.count_nonzero((a!=b)&(raw==0)))))
report=dict(status='SAVED_GRID_GEOMETRY_AUDIT',no_ROS=True,no_Gazebo=True,results=result,master_differences=halo,
    limits=['The fixture original approximate .27m old-body exemption is superseded by this per-cell evidence.',
            'Whole-cell interior certificates do not reproduce Nav2 raster coverage or expose internal StaticLayer footprint.',
            'Any altered raw occupied/unknown cell not certified whole inside the actual current/first polygon is UNKNOWN, never exempted.',
            'Fixture yaw=0 is controlled, not a full original yaw/TF replay.',
            'A nonzero nonlethal ghost master value alone would not disprove static clearing; the original fixture equality check was over-strict.'])
(OUT/'saved-grid-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(phases=len(result),uncertified=sum(r['uncertified_cells'] for r in result),
                     altered_cells=[(r['enabled'],r['phase'],len(r['altered_raw_occupied_or_unknown_cells'])) for r in result],halo=halo)))
