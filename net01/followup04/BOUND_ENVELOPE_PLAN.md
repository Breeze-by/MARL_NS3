# Bound-envelope candidate: one preregistered23, no Gazebo admission

Runtime source d231ac66544c81de0c7b286e9030a4ba5b9a36f2 removes central full OccupancyGrid construction that was immediately discarded. C still checks original envelope version/session/robot/length/hash and forwards the complete original packet. R retains full ROS/body hash/header validation. The original received RAM row now brackets the actual accept_bound callback with monotonic_ns; no extra topic/timer/output IO. This is certain redundant-work removal, not a claim that C decode caused22.

22 remains NOT QUALIFIED for180sim/420wall: within-business same-phase ACK span6.79sim/15.994440337wall =.424523; all-token/light-start-inclusive .435249 is not its replacement. Existing680Run records sum8.141105wall/8.051855CPU seconds and196.601ms output. Inter-Run gaps sum7.885392s, including intended pacing, ROS/control/IPC, not exclusively scheduling waste. In the identified mask25→26 region,20NativeSteps H2.41..2.60 consume167.196wall/166.206CPUms in391.972ms span. Source publication metadata→Hub admission is10.24–11.90ms forbatch25 and17.60–21.14ms for26, mixing DDS/typedtake/decode/IPC. No22 per-C-handler timing exists; its CPU share is NOT MEASURED.

## Fixed future real engineering window (root decision before23)

All future A/B/C use120sim /420autonomywall, startup180/outer900/cleanup90wall, decision cap130. This is the original NET task's explicitly permitted prospective smaller bounded engineering scope. Required averageRTF is120/420=.285714; report the original180/420=.428571 reference as well. Original90/95/98 coverage definitions, maps/ROI/denominator/geometry/checkpoint/SLAM/Nav2/physics dt/V3 and all time/safety/stop limits remain unchanged. No historical180sim/600sim result is rewritten or pooled. No180sim capability or scientific network advantage is claimed.

## Unique23 request; pending root admission

```
rtk proxy python3 -B net-01/workspace/net01/followup04/check_controlled_wifi.py --name continuous-dds-23-controlled-wifi --native /home/zhuyulab/ns3-workspace/net-01/build/followup03-release-portable-native/net01-payload
```

Same controlled1000-clock100-q10ms profile, physical10ms token/nominal20mswall commonpacer, maximum20ms real-native credit, Release82bc, serial/CPUprofileoff/controlTraceon, originalGateway boundedGC. Exactly original16wall business source /30wall total including cleanup; TF50/30/20Hz, odom30Hz and feedback100Hz perrobot perwall are not lowered; actual200x200costmaps every.5wall, original maps, peer10Hzsim. Source follows actual MOCK_PHYSICS clock, never originates a replacementclock; actual nativeSTEP only follows Gateway-observed clock, not physicalend. C91/R92, no current owned NET actors, 0Gazebo/Nav2/Policy/Goal/NN/arm. Mergedmap89 andjournal95 remain ungenerated, not claimed covered.

Acceptance requires original time contract: observed-clock/native lag <=.12sim, source ages <=.4/.55sim, originalPeer odom receipt <=.2wall and health/mask wall limits. For each pair of successive accepted masks, actual receipt lies inside [accept_bound_before,accept_bound_after]; report worst-case gap upperbound = next.after - previous.before, which must stay below.3wall throughout active ready supply. Unarmed zeroevents/accepted counts alone do not certify this. Report healthysource/receipt/health intervals, startupqualification and post-source-stop tail separately, with original END/resource cleanup and all exits. Report measuredRTF against both old and prospective references; process0 is not PASS.

The existing NoNode check_bound_peer (only3 C-envelope-vs-full-R assertions added) passed20 checks/native0, preserving exact CDR/body and original batch ordering/rejections. Evidence followup04/evidence/bound-envelope-01. No new tests or runtime were used to select these values. One23 only after concrete root admission; any originalcontract failure is retained and stops this candidate, no gate/rate/token/queue retry. No real physical/stop/Gazebo claim follows from this MOCK qualification.
