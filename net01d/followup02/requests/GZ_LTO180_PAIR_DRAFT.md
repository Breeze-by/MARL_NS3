# Corr6201 A1/B LTO controlled180 pair — SOURCE_READY, inert

No Gazebo/native/ROS process has been started for these requests. `gz-a3-01.draft.json` and `gz-b3-01.draft.json` keep all three authorization flags false. Root must review source, fix the final Git commit and actual adapter binding, and issue a separate immutable READY admission for each case. Old `gz-a1-01` and unused a2/b2 drafts remain unchanged. The accepted native fixed pair and `tcp-lto-01` full ROS result are prerequisites with limited scope; they do not qualify this Gazebo pair.

| Arm | Case/session | Business delivery | Native evidence RAM |
|---|---|---|---|
| A1 first | `gz-a3-01` / `2026111131` | Existing ordered local Gateway, all original adapters; native clock/model control retained | `/dev/shm/net01d-f02-gz-a3-01` |
| B, separate admission after A1 review | `gz-b3-01` / `2026111132` | Complete original CDR through actual ns-3 Wi-Fi TCP | `/dev/shm/net01d-f02-gz-b3-01` |

Both reuse Corr6201/commoncompact's three starting poses, scene/world/driver, frozen v1.1.0 checkpoint `6d4c51...`, 130 decisions, original SLAM and DWB/footprint, source cadence, actual data QoS, wireless/header/TTL settings, ownership and safety checks. The primary ROI remains 15558 cells, with the original coverage/T95 threshold. No training, goal-allocation change, source-rate change, physical parameter change or RF fault injection is proposed.

The common native ELF is `0cc771a18a3eb63ebbc4eb09ee942aaba27ea93211e07a7a0805d993dcc7c4f3`, 524432 bytes, with 13 libraries only from `/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/build/lib`. New artifact identity is recorded at `fbe269dd9f98f869b289ec81361b7fc20886642b` in repository-relative `net01d/followup02/native/lto-build-01/BUILD_IDENTITY.json`; the original external record is the explicitly absolute `/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/evidence/BUILD_IDENTITY.json`. The existing parser permits absolute artifact paths. Historical d552 is not used as the identity of the new13DSO. The actual build script invocation requires `rtk proxy bash net01d/followup02/native/build_lto_only.sh run`; omitting `run` does not build. Model sources, header and radio remain the original ca9/C3 versions; `tcp-mtu-v2` preserves MSS1448 and initial cwnd10/14480 bytes. New compilation uses LTO and explicit FP contraction off. Prior strict equality of 115895 native event rows, four PCAPs and 18 received bodies is one fixed pair's result, not a general 300ms guarantee. Actual full ROS maximum health gap around290.4ms leaves little margin; any real freshness failure must be preserved.

The common Gateway uses the reviewed terminalquiet behavior plus explicit `warning-free-v1`. This removes only unspecified SDK default QoS warning event callbacks; data QoS and explicit callbacks remain. Warning visibility and entity-cap batch boundaries change as already disclosed in the accepted source/SDK review. Original dispatch/control/main-thread observations are on; cProfile/native CPU profile/async ledger and DDS take trace are off. New passive C89 map capture is on in both arms and has nonzero RAM/observer cost.

`--capture-central-map` retains the existing C89 serialization's CDR and current metadata in RAM, then saves `central-map-capture/*.cdr` and `index.json` after the original stop. It creates no new source subscription or network input, does not refresh source stamps, and does not feed results into the policy or robots. It diagnoses the C source view only. R bag `/merge_map` is still the original delivered flow89 view and can affect reported R coverage/T95. Flow95 remains the real supervisor halt input; neither flow89 nor95 is bypassed or reclassified as pure diagnosis. An A0 has no C89 business wire and must not fabricate captured C samples.

## Budget and stop semantics

The admitted candidate bounds are **180 simulated seconds, startup180wall, autonomy420wall, outer600wall work, cleanup90wall**. Frozen runner `outer_wall` is the independent whole-work bound; startup/autonomy do not grant extra work beyond it. Original safety stopping/seal is given its separate90-second cleanup bound. New controlled180 host code starts a700wall exact-owned force-escalation deadline before sidecar startup (600+90+10), using remaining time for runner/Hub waits and omitting the old extra100wall host SIGINT wait in this path. Original120/legacy defaults remain unchanged.

700 is the force-escalation/stop boundary, not a claim that OS process joins and all evidence writes finish in the same millisecond. Original sidecar close/seal can take up to5 more seconds, and actual exit/save wall time is recorded. No cleanup time permits further autonomous exploration. Host or boot timeout, forced KILL, missing seal, resource destruction, physical stop, Action ownership or saved marker is failure/incomplete evidence, never a normal qualified result.

At original first fatal fault, retain the original authority halt, exact-owned UUID cancellation, local zero/PAUSE, original physical stop observation and owned cleanup. Keep the 300ms health limit, all original source/TF ages, physical thresholds and seal ordering. No retry follows a failed case and no second arm starts automatically. A1 must finish, be physically stopped and sealed, and receive independent evidence review before a separate B admission.

## Admission and ownership gates

Before each unique READY starts, root must verify:

1. Final reviewed Git snapshot and identical A1/B adapter maps, including new `adapter_node.py` and the updated Gateway/TopicWire/host/boot/runner/time-control/hub-client bindings. Draft `PENDING_ROOT_REVIEW_COMMIT` labels must be replaced explicitly. All frozen identity fields must still match the original trusted request. No broad `git add`, old evidence rewrite or remote push is authorized.
2. Case directory and all sibling host/native/Hub/boot/runner/admission/Xvfb/map outputs, `.sock`, `.network`, `.time-control`, unique READY use marker and direct RAM child must be absent. A preexisting attempt cannot be overwritten. Mode/session/case/socket paths must match the particular admission.
3. There is no conflicting current91/92 ROS experiment, Gazebo master11692, Xvfb92 lock/socket, NET Hub/native/controlled sidecar or concurrent expensive experiment. Root retains experiment exclusivity. Unrelated processes in other domains are not touched. The known old PID3132625 has ROS_DOMAIN_ID69 and is outside this case's ownership.
4. Existing native RAM precheck still requires at least16GiB free tmpfs and24GiB MemAvailable before native startup. Disk must accommodate retained native and ROS evidence; temporary RAM data is retained after copying. Preparation showed57,446,297,600 bytes tmpfs and1,662,415,142,912 bytes filesystem free; these are not admission-time measurements.
5. Host sets `LD_LIBRARY_PATH` only for its Hub/native to the new library directory and unsets `LD_PRELOAD`/`LD_AUDIT`. Original rootfs ROS `env -i` remains unchanged. After actual native READY/Hub IPC_LISTENING and before ROS/Gazebo, the host reads only its direct Hub child once, saving real executable/argv/parent/startticks/maps and requiring the exact13 ns3 DSO names in the new root. Missing/mixed maps stop the case before Gazebo; `ldd` is not a substitute.

Preparation checked the named paths absent, port11692 bind available and X92 lock/socket absent; it launched no model. Repeat only these relevant admission checks at execution. PID/domain observations and free resource values must remain clearly timestamped preparation facts.

## Run and seal records

After independent source acceptance, root may write the separately admitted READY. From `/home/zhuyulab/ns3-workspace`, the proposed A1 command is:

```bash
rtk proxy python3 -B net-01d/workspace/net01/host_run.py \
  --ready net-01d/workspace/net01d/followup02/requests/gz-a3-01.ready.json
```

B uses the corresponding `gz-b3-01.ready.json` only after its own admission. These commands are prospective and must not run against drafts.

Retain original case journals/events, ROS bag/launch/controller/Gateway logs, Action UUID/results, health/mask and physical trajectory/stop evidence; Hub/native original ledger/RX/PCAP/control artifacts; one-time actual native maps/load proof; controlled clock witness/coordinator/seal/exit; saved markers and host/boot/native/Gateway process exits. Add passive C89 CDR/index and report its actual samples, absence or save failure honestly. Retain first-fault/raw partial outputs and RAM even on failure. Record actual phase sim/wall bounds, complete host exit wall, forced/remaining owned resources and all incomplete evidence. No outcome can be inferred solely from a process0 or a created CSV.

Minimum validation completed before SOURCE_READY: four changed external Python files compile without importing ROS; old120/new180 scope behavior and unknown scope rejection; simulated owned-native13-library parser positive and wrong-root rejection; extracted real launcher default SDK/captureoff argv, explicit warning/capture argv and original `--noninteractive` preservation. Draft checks confirm frozen identity fields copied unchanged, both authorizations false and only ten intended paired identity/mode paths differ. No new permanent test framework or experiment was added.
