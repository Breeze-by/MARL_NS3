# B02 poststop regression — actual result

The sole real WiFi B02 completed the original 180sim episode and exited cleanly: host/runner/Gateway/Hub/native leaf/coordinator/both witnesses all exit0, original network integrity true. This is a bounded poststop regression result, not a new radio/Policy optimization or full project completion. B1's earlier Gateway -9/host1/network FAIL remains preserved.

Runtime `aae271f49a8d041285b9a903b3f58d9546985574`, activation `15a5af764d19c3520444d135ee239c6898cfdd3c`, session2026111147. Frozen source76, checkpoint6d, actual old0cc serial ELF and all13 original LTO DSOs are unchanged; the host's actual exe/parent/maps gates passed. Existing43adapter-path Git diff against aae was empty after exit; no artifact rehash or production edit during this run. [Actual command](../../evidence/gz-simhealth-b1-02-launch.json) and [prestart](../../evidence/gz-simhealth-b1-02-prestart.json) are retained.

| Actual observation | Result |
|---|---|
| Autonomy | G15.53→195.53, 180sim /425.149891wall s; phase RTF0.4233801 |
| Whole controlled ACK span | RTF0.4213556; first token→latest actual ACK, distinct from autonomy |
| Policy / real Nav2 | NN36; accepted/successful5/2/4, all11 exact-owned UUIDs terminal4; no abort/cancel/unresolved |
| Movement, original Observer | 19.61927 /5.81841 /14.28309m; minimum pair distance0.73541m |
| Original safety/closure | Error/hazard null, observed_stop/PAUSE/authority/ownership/engineering/run integrity true; active_cancel=false because all Goals naturally ended |
| Host / original budgets | 516.929946wall s; no outer/cleanup timeout; original180sim/130decision/720autonomy/900outer/90cleanup/1000host/stop12 unchanged |
| Native evidence | Native leaf0/END and full copy complete8,254,091,428B, all4PCAPs retained; no packet ledger/PCAP read for this report |

## Actual poststop evidence exit

Supervisor began at mono610837015915084 with initial20s, total60s, cleanup deadline610921091891784 and effective existing hard deadline611260723944594. Actual samePID/sameSession resource-closure proof arrived at610839117674858, **2.101759774s after supervision began**, before the original20s gate. It recorded both executors stopped, all resources destroyed, END flushed, no C/R/local cleanup RPCs or confirmations outstanding. The eligible evidence grace deadline was begin+50s, retaining the remaining escalation allowance inside the60s total and original outer cleanup/host bounds.

Actual Gateway phases: close_begin610837023156665; resources_closed610839117674858; persist_begin610839119048040; persist_end610860334752869; close_return610860335062661; main_return610860335246703 (exit_code0). Close-begin→main-return was23.312090s; measured persist marker span21.215705s (saved marker reports21.214580s using its own bracket). Gateway poll exit0 was observed about27.904s after supervision begin. Its only signal was the original SIGINT: **no TERM/KILL**. `network-gateway-exit.json.native_exit` is the ROS Gateway process field; the native leaf has its own independent exit0 record.

These observed phases validate this one eligible poststop episode; they do not prove B1's entire former teardown cost or guarantee every future shutdown. [Original phase/proof/exit and process-signal evidence](small-raw/) and [small structured result](small-result.json) preserve actual timestamps and deadlines. Physical stopping occurred before evidence completion; evidence grace added no autonomy or motion.

## Original R primary, one canonical all-shard analysis

After every recorder/registered process exited and exact-owned R92 daemon820180 was stopped by the standard daemon command (exit0/finalgone), the unchanged canonical tool ran **once**, exit0/14.409370wall s. No active bag/SQLite/PRAGMA access occurred during runtime. Domain69 was untouched. No metadata reconstruction, shard omission, threshold/ROI/alignment change or C-map substitution was used.

Original ROI15558cells/38.895m². Initial raw R coverage10.9718473%; final **99.9164417%**,15545 correct-free cells/38.8625m². Final quality valid;242/256 valid samples. Last R map receipt195.29/source194.78 is inside autonomy, with0unknown reachable area and0.0325m² false occupied reachable area.

| Threshold | Original quality-valid elapsed simulation time |
|---|---:|
| T50 | 11.82s |
| T80 | 37.85s |
| T90 | 61.73s |
| T95 | 65.84s |
| T98 | 92.47s |

Raw T50 was8.15sim and is retained separately; it is not substituted for quality-valid T50. Canonical task-phase path lengths were19.619200/5.818328/14.283004m; they use the original phase window and differ slightly from whole-Observer distances. Natural completion remains false: reaching a retrospective map threshold is not a natural policy terminal. All11 successes are actual recorded results, not a moving-cancel demonstration.

[Metrics small result](metrics.small-result.json), [complete canonical result](metrics/result.json), [argv](metrics.argv.json), [exit](metrics.exit.json), stdout/stderr and [read manifest](read-manifest.json) are retained. Gateway/native large JSON/ledger, PCAP and C89 analysis remain unperformed here; sim300 receipt/source-margin distributions are UNMEASURED, not inferred from wall gaps. A1/B/B02 have different actual trajectories/workloads; their coverage/RTF differences are not a pure-RF causal partition. No additional model, repeat, source change, A0/C or NET02 followed this result.
