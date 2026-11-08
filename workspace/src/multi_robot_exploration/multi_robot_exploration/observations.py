"""Received occupancy data projected onto a public, fixed task coordinate grid."""
import math
import numpy as np

TASK_ROI = (-5.8, -5.6, 7.25, 5.3)


def project_local_navigation(cells, resolution, origin, frame_transform, shared):
    """Sample a received local grid at shared centres, using local <- shared TF.

    origin and frame_transform are planar (x,y,yaw). Unknown stays -1.
    No simulator geometry or true pose is used.
    """
    rows, columns = np.indices(shared['cells'].shape)
    x=shared['origin'][0]+(columns+.5)*shared['resolution']
    y=shared['origin'][1]+(rows+.5)*shared['resolution']
    tx,ty,yaw=frame_transform
    local_x=math.cos(yaw)*x-math.sin(yaw)*y+tx-origin[0]
    local_y=math.sin(yaw)*x+math.cos(yaw)*y+ty-origin[1]
    c=np.floor((math.cos(origin[2])*local_x+math.sin(origin[2])*local_y)/resolution).astype(int)
    r=np.floor((-math.sin(origin[2])*local_x+math.cos(origin[2])*local_y)/resolution).astype(int)
    source=np.asarray(cells)
    valid=(r>=0)&(r<source.shape[0])&(c>=0)&(c<source.shape[1])
    result=np.full(shared['cells'].shape,-1,dtype=np.int16)
    result[valid]=source[r[valid],c[valid]]
    return result


def project_observed(cells, resolution, origin, roi=TASK_ROI):
    """Sample received cells at .05m centres; unavailable cells remain unknown."""
    source = np.asarray(cells)
    width, height = int(round((roi[2]-roi[0])/.05)), int(round((roi[3]-roi[1])/.05))
    columns = np.floor((roi[0]+(np.arange(width)+.5)*.05-origin[0])/resolution).astype(int)
    rows = np.floor((roi[1]+(np.arange(height)+.5)*.05-origin[1])/resolution).astype(int)
    valid_r = (rows >= 0) & (rows < source.shape[0])
    valid_c = (columns >= 0) & (columns < source.shape[1])
    result = np.full((height, width), -1, dtype=np.int16)
    result[np.ix_(valid_r, valid_c)] = source[np.ix_(rows[valid_r], columns[valid_c])]
    return result
