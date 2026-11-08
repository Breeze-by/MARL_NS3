"""Audit checkpoint completion, without policy/environment/optimizer execution."""
import math


def expected_optimizer_updates(config):
    return sum(config['epochs']*math.ceil(min(config['rollout'], config['formal_joint_decisions']-start)/config['minibatch'])
               for start in range(0, config['formal_joint_decisions'], config['rollout']))


def validate_development_checkpoint(checkpoint, config):
    metadata = checkpoint['metadata']
    if metadata.get('failure') is not None or metadata.get('joint_decisions') != config['formal_joint_decisions']:
        raise ValueError('Incomplete or failed formal checkpoint is not a trained development policy')
    if metadata.get('config') != config:
        raise ValueError('Checkpoint differs from the fixed development configuration')
    optimizer = checkpoint.get('optimizer')
    if optimizer is None or not optimizer.get('state'):
        raise ValueError('Checkpoint has no actual optimizer update state')
    expected = expected_optimizer_updates(config)
    if any(float(state['step']) != expected for state in optimizer['state'].values()):
        raise ValueError('Checkpoint optimizer updates do not match the completed fixed budget')
    return dict(joint_decisions=metadata['joint_decisions'], optimizer_updates=expected,
                optimizer_parameter_states=len(optimizer['state']))
