# Current MARL_NS3 engineering context

Read README.md, PROJECT.md and docs/CURRENT_STATUS.md before work. This is the current trained-PPO/Gazebo/ROS 2/ns-3 project, not the earlier BASE-only stage.

Keep v1.1.0 weights, observation/Frontier/action/goal semantics and existing SLAM/Nav2 behavior fixed for communication comparisons. RL assigns high-level goals, never velocities. Business traffic must actually traverse ns-3 where specified; no truth or ideal-DDS fallback. Do not automatically start training, robot experiments or NET-02.

Some old-numbered source paths remain actual runtime dependencies; see docs/LOCAL_ENVIRONMENT.md. Do not remove frozen/58-bound files or native libraries based on their names. Old output aliases lead to local archives and are not portable inputs. Never write new experiments into them.

Use current results/docs rather than resurrecting outdated no-RL/no-network statements. Preserve failures and exact model provenance. Follow the user's present authorization; normal commits must exclude raw runs/caches. Use RTK for supported commands on this workstation.
