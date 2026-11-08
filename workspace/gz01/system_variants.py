"""GZ-01 shared system variants; weights and Nav2 settings are unchanged."""
GOAL_SEPARATION_M = {
    "reference-v1": .70,
    "goal-margin-v1": .70 + 2 * .25,
    "seed-connection-v1": .70 + 2 * .25,
    "idle-body-guard-v1": .70 + 2 * .25,
    "peer-compact-v1": .30 + 2 * .25,
}
