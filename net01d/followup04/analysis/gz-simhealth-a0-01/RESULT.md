# A0 direct reference — business complete, controller exit FAIL

The unique A0 completed180sim with real direct R92 DDS, physical stopping and UUID closure. Original host/runner/network integrity returned0/true, **but the exploration controller actually exited1 after the budget SIGINT and printed a complete rclpy RuntimeError traceback**. A0 is therefore NOT ACCEPTED pending the independent failure review; its high coverage and host0 do not conceal controller exit failure. No retry/source repair/C start followed.

Runtime `aae271f49a8d041285b9a903b3f58d9546985574`, activation67c5713, session2026111152. Frozen Policy/checkpoint6d, scene/spawns/SLAM/Nav2/source/safety/profile budgets are unchanged. Actual old0cc ELF/all13 DSOs passed the original exe/parent/maps gates. Existing45adapter paths had empty Git diff against aae after exit; no new hash sweep or production edit.

| Actual fact | Result |
|---|---|
| Original autonomy | G22.83→202.83,180sim/284.228446wall s; phase RTF0.6332934 |
| Host / native / sidecars | Host356.149177wall/exit0; runner/Hub/native/Gateway/coordinator/R-C witnesses0; controller **1** |
| Policy / actual Goals | NN35;14accepted7/3/4;13actual successes6/3/4 and one tb1 rawCANCELED5 |
| Original safety/ownership | observed_stop/PAUSE/authority/closed true;14requests,0unresolved/unterminated; error/hazard null in original Observer |
| A0 placement | direct_reference=true, business_wires_installed=false; original directDDS Policy transport; native business ingress/delivery0 |
| Registry / evidence | saved true, owned_unknown_or_active0/connections0; nativeEND/exit0/4PCAP/fullcopy14,283,606B |
| Cleanup |16registered/observed owned gone; exactcase R92daemon860416 standardstop0/finalgone;91/92clear,69untouched |

`active_cancel_pass=false` remains the original harness result. Final Observer status contains the exact canceled UUID `cb4c8515cce94742ab5791aab79fa4b1` (tb1 token7), with actual status3→5 and final ownership closed. The canonical task window reports13successes and no task-phase cancellation; the final raw5 is retained separately. Selected caches do not identify the actual cancel request issuer, response or GetResult5 timestamp, so those are **UNRESOLVED**, not fabricated from a status message or stop success.

## Controller failure evidence

Original events: budget SIGINT-request event for exploration PID860524 at Unix1794394908.4831517 /G202.83 (sampled before original killpg, not signal-send completion); allocator_halted at1794394908.483686571, rl_halt_requested at1794394908.4842977 (original live append cache); actual process exit1 observed at1794394910.1910439 /G203.89. Original physical stopping and14UUID closure followed, separately retained in the final stop attempt. Bag/Gateway/launch each received their original SIGINT and exited0; no TERM/KILL appears in the selected process events.

[Full traceback tail](small-raw/control-tail35.txt) contains the entire Traceback through the final exception: `net01/a0_controller_bootstrap.py:64 main` →`:52 frozen.main` →`workspace/gz01/headquarters.py:245 rclpy.spin(node)` →rclpy executors handler →`executors.py:400 sub.handle.take_message(sub.msg_type, sub.raw)`, raising `RuntimeError: Unable to convert call argument to Python object (compile in debug mode for details)`. The traceback itself has no timestamp and does not identify the subscription/message type. Actual exception onset relative to SIGINT and its unique cause remain unresolved. The frozen main always calls close_controller in finally; A0 bootstrap restores wrappers/closes its journal in finally. Neither source was modified here.

[Halt/cancel/stop selected timeline](halt-and-cancel-selected.json), [process event selection](small-raw/process-stop-events.json), [small result](small-result.json), source-held/owned/daemon/launch records under `../../evidence/gz-simhealth-a0-01-*` retain the distinctions. Use [registry selection](a0-registry-selected.json) for review: the retained `small-raw/a0-direct-safety.json` is actually16.85MB because it includes health/mask records; it is not a small review input. The initial small-file classification was incorrect and the read manifest now discloses its size. No extra original scan was performed to fill missing cancel times.

## Original R primary — valid business metrics, not acceptance

After every writer/owned process and the exact-owned daemon exited, the unchanged canonical analyzer ran once, exit0/12.029943wall s, complete original metadata/allshards, ROI15558/quality gate/original phase. No active bag open/SQLite/PRAGMA occurred, no metadata/shard fabrication or post-stop map substitution.

Initial R coverage11.126109%; final **99.884304%**,163/172quality-valid samples. QualityT50/80/90/95/98 were **12.06/33.46/37.47/37.47/46.51sim s**. Canonical paths10.091713/6.904875/19.156169m, distinct from whole-Observer10.091864/6.904988/19.156278m. Original budget end is not a natural task completion. [R small metrics](metrics.small-result.json), complete `metrics/result.json`, argv/exit/stdout/stderr and [read manifest](read-manifest.json) are retained. No Gateway JSON/native ledger/PCAP/C89 parse or new model was used for these metrics. A0 removes reader/topology/adaptation costs together; it is not a zero-latency reference or a pure serialization/RF experiment.
