# Inert simhealth Gazebo pair

SOURCE_READY metadata only. Runtime `c4ad853e7e5e8707a0e5a0be1426bc84b4bd2e1e`; all three execution flags are false. Matching new Full A1/B and actual ROS safety gate must pass independent acceptance before Root separately STARTs each unique Gazebo case. A1 first; B only after separate actual GZ A1 review. No automatic run/retry/second arm.

Requests are `gz-simhealth-a1-01.draft.json` and `gz-simhealth-b1-01.draft.json`, with joint `GZ_SIMHEALTH_PAIR_ADAPTER_BINDING.draft.json`. Only9changed small sources/config (7simhealth Python sources,selectednewprofile,authorizedbootbudgetvalidator) were newly SHA-bound once;34unchanged f03identities reused by manifest-scoped Git diff. No world/model/bag/checkpoint/history/project/artifact hash sweep. Root post-budget pin replaces EDF as actual runnable source; no EDF-only runtime claim.

Predeclared budget: startup180wall,autonomy720wall,outer900work,cleanup90,original host1000 force escalation.180sim/130decision and stop12wall remain. boot_network only adds this exact budget for the new simhealth profile; old tuples/profiles stay. No result-driven extension.

Frozen Corr6201 world/map,compact3spawn/yaw/footprint,.3mcentre monitor,6d4c51(v1.1.0)weights/observation/Policy/Frontier/Nav2DWB/SLAM and physical/model/QoS/source/radio rules remain. New profile `controlled1000-clock100-q10ms-pace10-raster-simhealth` keeps pace10/raster/no-clocklane and actual10sim-ms/10iterations/singleinflight/20sim-ms credit. Only health/mask receipt300ms uses actualRROSsim; old mono logs stay. Peerodom.2wall/source.4/.55sim/future thresholds/Gatewayprocessstatus.3wall remain, with independent2wall admin/clock/native/physical protection and realLocalStop. Permission revocation/UUID/PAUSE/physicalstop/seal evidence must be actual. If any retained gate fails, preserve firstfailure; never adapt stamps/rates/safety.

A1 is original modeA ordered local business (native business0, actual native still clock owner), not a modeB-equivalent CPU load. B original business CDR traverses actual ns3WiFi. Reuse old0ccserial/same13LTO/full4PCAP/fullledger; native tmpfs only moves original evidence files, no sessionRAM or nativecopy/CPU-shim/sampler variant. Actual original rootfs/controlledplugin/witness/realGazebo/SLAM/Nav2 path is retained, not no-motion Full or CPUreplay as a GZ substitute.

Original bags/ownedprocess/END/copy/stop/seal requirements remain. Delivered R merge_map/bag and original ROI15558cells/T90/T95/R receivedflow95 remain primary; passive C89 is diagnostic only. New timing condition can alter achievedwallrate/inputavailability/trajectories; historical f03 profiles are not matched scientific baselines.

Unique sessions2026111143/44, case/network/socket/tmpfs paths are distinct; source-only static check found them absent, host sockets93bytes. Immediate exclusive/resource/source/ROS91/92/Gazebo/loader preflight is NOT performed by these drafts and remains required after a Root START. Missing original environment means STOP; no reinstall/build or new runtime framework.

Exact proposed commands from `/home/zhuyulab/ns3-workspace`, only after Root creates the separately authorized READY:

```sh
rtk proxy python3 -B net-01d/workspace/net01/host_run.py --ready net-01d/workspace/net01d/followup04/requests/gz-simhealth-a1-01.ready.json
rtk proxy python3 -B net-01d/workspace/net01/host_run.py --ready net-01d/workspace/net01d/followup04/requests/gz-simhealth-b1-01.ready.json
```
