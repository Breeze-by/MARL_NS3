# NET-01E unified controller activation — source-only proposal

No Gazebo/native/ROS/NN execution or production activation. `GRACEFUL_ADMISSION.json` remains false. Root owns the final source commit and four new controller source bindings; old READY/request/results are unchanged.

## Actual entry and source gates

1. Original `net01/host_run.py` reads both explicit NET/GZ authorizations, exclusive case, actual native ELF/header and13 mapped DSOs, starts original ControlledRuntime/coordinator before Hub, then invokes `/mnt/net01/boot_network.py` inside existing bwrap rootfs. It is not an alternate controller path.
2. `boot_network.py` calls frozen `workspace/gz01/boot.py::validate_ready`: model/scene/world/frozen source hashes, unique admission-used, original mode/arm/130decision and budget checks. It separately validates all `network.adapter_sha256` entries relative to net01, so new `../net01e/controller/...` keys bind these external files without changing frozen path checks.
3. Boot sets the explicit controller adapter enum in the runner environment. Original `run_network_case.popen` is the sole interception of the frozen `python3 -B .../gz01/headquarters.py` command. Under `net01e-graceful-v1` it selects the **same** new bootstrap for A0/A1/B/C. A0 retains actual domain92; A1/B/C retain91. No arm can select a different graceful implementation through this enum.
4. `graceful_controller_bootstrap.py` checks both execution and production activation flags before ROS/controller import. It patches only the spin callable, then invokes original A0 bootstrap or original common bootstrap according to unchanged `NET01_DIRECT_REFERENCE`. Existing exclusive journal, observed_spin, A0 independent UUID safety hook, frozen main, checkpoint and original finally are retained.

Proposed changes: net01/boot_network.py +9lines (explicit known enum, four required external source bindings, env); net01/run_network_case.py +2lines (one common selected path). New `net01e/controller/host_run.py` checks the explicit common enum and four actual controller file hashes and production admission before delegating to original host. The bootstrap now also requires production_activation_allowed=true, preventing bypass via direct old host. No historical request is changed and legacy no-enum path retains original behavior.

All future NET-01E cases must invoke (cwd `/home/zhuyulab/ns3-workspace/net-01d/workspace`):

```bash
rtk proxy python3 -B net01e/controller/host_run.py --ready net01e/requests/CASE.ready.json
```

Those CASE.ready.json files do not exist yet. No new READY was generated. This command is not authorized.

Root's future binding must use the same complete union of45historical adapter paths in every arm (including A0 paths even when unused), update hashes for net01/boot_network.py and run_network_case.py, and add these four entries, for one common49-path external binding:

```
../net01e/controller/host_run.py
../net01e/controller/graceful_controller_bootstrap.py
../net01e/controller/graceful_spin.py
../net01e/controller/GRACEFUL_ADMISSION.json
```

The final admission JSON bytes must be enabled and pinned before their source hash is sealed; no binding to false bytes followed by silent enablement. Same candidate commit, factory, external code, logging switches, installed rootfs, original native0cc/13DSOs, profile and source binding identity apply across all twelve cases. Per-arm topology/RF/capture applicability and exclusive output/session differ explicitly. Replay tools are separate diagnostics and must not enter physical launch.

## Four historical runtimes versus the common candidate

`OLD_RUNTIME_DIFF_AUDIT.json` records exact Git changed-path sets, not inferred names. Old READY files were read only for runtime/budget/scene/profile fields; no old bag/GB rehash.

| Historical arm | Actual runtime | Differences inherited by common candidate |
|---|---|---|
| A0 |aae271f49a8d041285b9a903b3f58d9546985574|197a controller exit-integrity report/gate and bd663 transparent exception observation; then this actual graceful mechanism repair. Old controller1 remains FAIL. |
| A1 |2be7e229492d29817057fa8db166e38f114ca209|AAE changes five net01 files: Gateway close-phase/resource-proof/persist observation; fixed total60wall poststop evidence grace clipped to old cleanup/work/host bounds; boot/host absolute deadline propagation and runner phase gating. Also 197a/bd663 and new graceful repair. |
| B |aae271f49a8d041285b9a903b3f58d9546985574|197a/bd663 plus common graceful repair. |
| C |bd663824d77983cb2b2721e90241ef97bf06461f|Common graceful repair and explicit new routing/binding. |

Actual `git diff --name-only bd663 78bf29c -- net01 workspace` is empty. Before the newly proposed routing edits, bd663→NET-01E HEAD also had zero net01/workspace difference. The two routing edits are the only new tracked net01 changes in this proposal. No frozen workspace edits. Old A0/A1/B/C outcomes are not new common-source repetitions and cannot be pooled into the formal twelve-case table.

## Remaining admission boundary

The five no-motion graceful cases passed their specific expected exits and real accepted cancellation. Pending/lateaccept ownership and physical stop still require the original independent safety chain, not a new lifecycle claim. Current actual-source replay has an A1 TF/correction source/capture gap and is not qualified; therefore **Gazebo remains NO-GO** regardless of this proposed activation wiring. Root/independent review, common identity pin, real-load/replay qualification and one unique explicit READY/START per actual case remain necessary. First blocking software failure stops the planned sequence, retaining failed slot and all unrun slots.
