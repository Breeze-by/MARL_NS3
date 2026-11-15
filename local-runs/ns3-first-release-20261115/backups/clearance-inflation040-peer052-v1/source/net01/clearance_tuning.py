"""Explicit task-only navigation clearance; old processes keep original values."""
import json
import os

REVISION='inflation040-peer052-v1'
ENV='NET01_NAVIGATION_CLEARANCE'
ADAPTER_FILES=('clearance_tuning.py','clearance_tuning_launch.py')
CONTRACT=dict(revision=REVISION,inflation_radius_m=.40,peer_radius_m=.52)


def validate_contract(contract,profile_id,direct):
    if contract is None:return None
    from execution_profile import ROS_DELAY_V3_PROFILE_ID
    if contract!=CONTRACT or profile_id!=ROS_DELAY_V3_PROFILE_ID or not direct:
        raise ValueError('Clearance tuning requires its explicit V3 A0 task contract')
    return contract


def install_peer_clearance(profile,owner):
    encoded=os.environ.get(ENV)
    if encoded is None:return None
    contract=validate_contract(json.loads(encoded),profile['id'],os.environ.get('NET01_DIRECT_REFERENCE')=='1')
    import peer_keepout
    import business_peer
    before={module.__name__:module.RADIUS for module in (peer_keepout,business_peer)}
    peer_keepout.RADIUS=business_peer.RADIUS=contract['peer_radius_m']
    return dict(revision=REVISION,owner=owner,pid=os.getpid(),contract=contract,before=before,
        actual_module_radius_m={module.__name__:module.RADIUS for module in (peer_keepout,business_peer)},
        producer_state_radius_binding_m=business_peer.BusinessPeer.publish_masks.__globals__['RADIUS'],
        target_allowed_uses_peer_globals=peer_keepout.target_allowed.__globals__ is peer_keepout.__dict__,
        route_blocked_uses_peer_globals=peer_keepout.route_blocked.__globals__ is peer_keepout.__dict__,
        resolution_m=peer_keepout.RESOLUTION,
        scope='Same original peer disk/raster/target/route methods, .05 grid cell guard unchanged; source freshness and all safety gates retained')


def set_inflation_parameters(parameters):
    changes=[]
    for side in ('global_costmap','local_costmap'):
        values=parameters[side][side]['ros__parameters']
        inflation=values['inflation_layer']
        if values['robot_radius']!=.25 or inflation['cost_scaling_factor']!=3.0 or inflation['inflation_radius']!=.55:
            raise ValueError('Clearance revision requires the reviewed .25/.55/scale3 baseline')
        inflation['inflation_radius']=.40
        changes.append(dict(parameter=side+'.'+side+'.ros__parameters.inflation_layer.inflation_radius',
            previous=.55,value=.40,robot_radius_m=values['robot_radius'],cost_scaling_factor=inflation['cost_scaling_factor']))
    return changes
