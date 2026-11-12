# NET-01E controller conversion audit and bounded no-motion proposal

Status: SOURCE/PLAN ONLY. `ADMISSION.json.execution_authorized=false`. No ROS test, replay, signal, Gazebo, Nav2, model, ns-3 or robot command has run for NET-01E. No production/system source has been changed. Root owns pinning and START.

## Evidence and installed source boundary

Read original `net01d/followup04/analysis/gz-simhealth-a0-01/{INDEPENDENT_REVIEW.md,RESULT.md,small-raw/control-tail35.txt}`, current `net01/{controller_bootstrap.py,a0_controller_bootstrap.py}`, frozen `workspace/gz01/headquarters.py` main and `workspace/rl04/ros_headquarters.py:154` close. A0 actual exit1 is process-integrity FAIL even though physical stop/ownership closure succeeded. The traceback identifies `_take_subscription -> sub.handle.take_message`; it does **not** name its topic/type or timestamp the throw. Supervisor's SIGINT request precedes observed process exit, and finally's halt follows SIGINT, but neither proves the original exception was caused by SIGINT. Current `observed_spin` records only a future exception and re-raises; bd663 was not a conversion repair.

Historical `sigint-dds/run-01` had a ready-file race, 0publish/0SIGINT. `sigint-dds/run-02/RESULT.md` has 240publish/12wall then source STOP then SIGINT; no handler-entry/exception/cleanup evidence, 5s timeout and actual SIGTERM -15. It remains INCONCLUSIVE. Successful kill does not prove Python handler execution. NET-01E will keep real DDS supply alive through actual receiver exit or the bounded failure deadline.

The wrapper is `net01/ros-python.sh`, using bwrap and `base-01-econ/isolation/rootfs`, not Docker. Static dpkg status reports rclpy **3.3.22-1jammy.20260907.213431**, rosidl-generator-py **0.14.6-1jammy.20260907.200655**, nav-msgs **4.9.2**, pybind11-dev **2.9.1-2**, pybind11-vendor **2.4.2**, rmw-fastrtps-cpp **6.2.10**, Python **3.10.12-1~22.04.18**. No package import or Node was needed to read these facts. Installed executor line400 matches the historical stack. The shared object's dynamic symbols are stripped for `take_message`/`convert_to_py`; no claim of byte-identical compiler/source mapping follows from the package version.

Specific source mechanism:

* [rclpy tag3.3.22 subscription.cpp:108–127](https://github.com/ros2/rclpy/blob/3.3.22/rclpy/src/rclpy/subscription.cpp#L108) performs C `rcl_take`, then typed `convert_to_py`, then a Python tuple. Raw subscriptions take a distinct path. An ordinary callback error would occur after this frame.
* [tag3.3.22 utils.cpp:117–129](https://github.com/ros2/rclpy/blob/3.3.22/rclpy/src/rclpy/utils.cpp#L117) wraps converter return without a NULL/PyErr result check. This is **tag source**, not installed C++ source (not shipped in the rootfs).
* Installed `rootfs/opt/ros/humble/share/rosidl_generator_py/resource/_msg_support.c.em:512–530` returns NULL when `PyObject_CallObject` for the generated Python message constructor fails; nested converters and array methods also return NULL. Installed `nav_msgs/msg/_occupancy_grid.py:91` builds Header, MapMetaData and the array in Python. This creates a real location where a Python signal handler can raise during C→Python construction, and also permits non-signal Python construction failures.
* Static disassembly of the installed `libnav_msgs__rosidl_generator_py.so` confirms OccupancyGrid constructor call at `0x55b8`, return-pointer test at `0x55cb`, zero branch to `0x57a0` and returning that zero pointer. Bounded exact output is `installed-converter-excerpt.txt`; no executable/library was loaded. This confirms the constructor-NULL branch in the installed converter, while the original A0's failing message type remains unknown.
* Installed `rootfs/usr/include/pybind11/cast.h:1000–1024` throws the exact generic text when any tuple argument object is null. Its header version matches installed package metadata; the generic string alone does not establish which argument was null in A0.
* [joint_state_publisher issue117](https://github.com/ros/joint_state_publisher/issues/117) has a similar Humble shutdown stack on CycloneDDS. It is a hypothesis lead, not this FastRTPS episode's proof.

Frozen HQ subscribes to merge/local/costmap OccupancyGrid, Odometry, Twist, TFMessage, String and ROS time (plus action waitables). No historical failing subscription is identified. No original bag or GB file has been opened in this audit.

## Hypotheses and disconfirming observations

| Hypothesis | Support now | Observation that would weaken/disconfirm it |
|---|---|---|
| H1: SIGINT raises KeyboardInterrupt inside generated construction; NULL becomes generic cast_error | Source mechanism, after-budget signal/exit ordering | Matching error before any SIGINT with unchanged valid payload; a target error whose handler has not executed; another captured converter exception |
| H2: legal DDS payload/type-support construction fails without signals | Error location is conversion, topic/message absent | Same fixed payload repeatedly received successfully before one signal; if signal is observed in its generated constructor at matching failure, that sample needs no illegal-payload cause (historical payload still unknown) |
| H3: malformed/nonfinite data or runtime type mismatch | No positive evidence | Fixture has one exact public typed publisher/subscriber, same installed class, finite metadata, int8 values -1/0/100, exact width×height and public serialize→deserialize equality. This rules these causes out **for the fixture**, not for unexamined historical messages |
| H4: subscription/node destruction races with take | No entity lifetime trace in A0 | Fixture creates once, destroys only after outer exception observation; matching error before any destruction weakens a required-destruction explanation. Does not eliminate other original threads |
| H5: allocation/resource/converter error unrelated to SIGINT | NULL has several real causes | Captured exception context and handler-frame timing distinguish some cases. Missing context is UNRESOLVED, not evidence of KeyboardInterrupt |

## First proposed bounded exposure: continuous DDS and one observed SIGINT

One unique run `net01e/controller/run-01`; no automatic retry. Two Python processes only, same installed rootfs/FastRTPS, `ROS_LOCALHOST_ONLY=1`, **domain97** passed explicitly into both rclpy.init calls (the wrapper's env default92 must be overridden in both child and parent before init). One exact topic `/net01e/controller/grid`, nav_msgs/msg/OccupancyGrid, typed rawFalse. RELIABLE/TRANSIENT_LOCAL/KEEP_LAST1; 400×400 int8 array with repeating -1/0/100, .05m resolution, odom frame, identity quaternion, finite zero origin; only header timestamp changes. Fixed **20Hz** wall schedule, 12wall to a single SIGINT measured from first successful publish. Check subscription count1, atomic ready publication, and actual first callback before admitting the signal. Do not wait for publication to stop before sending it. Publish at the same rate until child actually exits or 5wall after SIGINT. Maximum **340 publishes** (12+5s); no catch-up burst. Startup≤8wall, inner≤27wall, outer32wall +2s kill grace. Source stops only after exit observation or failure deadline, with first/last publication and pre/post-signal counters retained.

Receiver uses actual `rclpy.spin(node)` with `SignalHandlerOptions.NO`. Capture original Python default_int_handler, install one public `signal.signal` observer that records in memory handler-entry mono and the interrupted frame chain, then **immediately delegates to that saved original handler**. No event trigger, C API hook, private take, msg-type monkeypatch, sleeps in constructor or second SIGINT. This handler wrapper is an explicit timing observation intervention and may change the timing; do not label the sample uninstrumented historical reproduction. The interrupted Python frame may identify a generated constructor; it cannot locate every C instruction or expose the C thread's PyErr after it was overwritten. Persist handler record from exception/finally, keeping signal-path work small. Preserve original exception type/repr/cause/context/full stack and `_take_subscription` topic/type/raw/identity before cleanup, plus subscription-created/destroy-start/end, first/last callback/count, ROS-context state, signal request before/after, process-exit mono/code. Full payload is known deterministic; no hot-path JSON per message.

Receiver exception observer bare re-raises **every** BaseException, including KeyboardInterrupt. Parent propagates actual child nonzero (negative signal exits mapped to 128+signal for parent CLI while retaining raw value); generic RuntimeError remains exit1. Cleanup failures must be recorded without replacing the primary failure. Parent must not return success on marker presence or simply because process disappeared. Driver exceptions retain their own full traceback and fail. If no exit at5s, record TIMEOUT/INCONCLUSIVE, capture one public `faulthandler` stack via SIGUSR1 (registered as a diagnostic only), then owned SIGTERM/1s, SIGKILL/1s if needed; every cleanup signal recorded. Timeout is not NOT_REPRODUCED.

Proposed exact command after source review and Root START (currently forbidden by false admission):

```bash
rtk proxy timeout --signal=TERM --kill-after=2s 32s bash net01/ros-python.sh /mnt/net01e/controller/continuous_dds.py --output /mnt/net01e/controller/run-01
```

Preconditions at actual START: Root pins reviewed script/ADMISSION; unique output absent; no timed/heavy job, source/writer, owned leftover or UDP participant in domain97's range (31650–31899); public process/port inventory first. Do not start ROS CLI discovery/daemon just to inspect. Scoped cleanup only for exact children; domain69 and all unrelated processes stay untouched.

## Interpretation and next admission boundary

* Matching RuntimeError + subscription metadata is **real installed conversion failure reproduction in the synthetic fixture**, not sufficient historical attribution. If handler-entry stack identifies generated constructor and error is after that handler, classify H1 strongly supported for that sample; preserve missing PyErr limitation.
* Normal KeyboardInterrupt is NOT_REPRODUCED in this one exposure. Any pre-signal error is first failure and cancels scheduled SIGINT. Silence/timeout/missing first callback is diagnostic INCONCLUSIVE and no automatic repeat.
* Do not automatically escalate to deterministic constructor interruption. If needed, propose separately a public profile/trace event coordinating one SIGINT at generated `__init__` entry, with exact altered timing declared as a **test intervention**. That only proves mechanism susceptibility, never reconstructs historical signal hit or illegal historical data. No such intervention source/execution is admitted here.
* An original-message follow-up requires the newly identified topic/type, all writers gone, and separate bounded bag selection (topic metadata and narrow end-of-autonomy window first). Do not initially full-scan or deserialize GB bags. Check actual endpoint/type/lifetime and selected payload semantics before claiming original NaN/type mismatch excluded.

## Minimum possible repair boundary (not yet chosen or implemented)

No catch-ignore RuntimeError, reinterpret-all-after-SIGINT, private take patch, replacement type support or system library change. If H1 is supported, the candidate is an **external bootstrap graceful stop handler**: SIGINT records a stop request, a public guard condition wakes spin, original executor leaves at a controlled boundary, and original HQ finally/close_controller performs ROS-alive halt/cancel. It must not shut context before cancellation, run ROS operations from the signal handler, continue submitting goals after stop request, or alter frozen decisions. The final concrete public-executor/guard implementation and stop-order proof need separate source review/admission. If non-signal conversion/type/lifetime defect is observed, repair its actual external owner instead; do not apply the graceful-stop candidate as an unrelated mask. Frozen v1.1.0 weights/701 encoding/Frontier/SLAM/Nav2 and all safety deadlines/thresholds remain untouched.

Source audit performed; runtime verification deliberately **NOT EXECUTED** pending Root+independent review and explicit START.

## Run-01 fixture failure and run-02 proposal

Root admitted pin5d7cc's unique run-01. It failed before ROS init or child creation: full typed CDR equality compared original Python `.05` double with wire float32. Actual exit1/0publish/0SIGINT/0child/0Node and original evidence stay under `run-01/`; this is NOT TESTED for the target error. Root and independent reviewer confirmed IDL float32/setter/equality semantics. Authorized source-only correction: `grid.info.resolution=struct.unpack('<f',struct.pack('<f',.05))[0]`; entire message roundtrip equality stays strict. No rate/payload-wire/signal/runtime budget changed.

Active `ADMISSION.json` is false again; `ADMISSION-run02.json` is the proposed bound. New command changes only output to `/mnt/net01e/controller/run-02` with the same32s outer bound. This permits one effective DDS exposure only after a fresh Root pin+START, with no retry following mechanism nonreproduction.

## Controlled mechanism proposal after run-02

Run-02 completed with actual ordinary KeyboardInterrupt at executor wait_set.wait, not the target conversion error. Root requested one controlled mechanism probe in independent `mechanism_probe.py`; `MECHANISM_ADMISSION.json` is false. It imports only existing save/exception observation helpers from continuous_dds, whose main is not executed. No production changes.

Two sequential child cases, one no-signal control then one artificial SIGINT intervention. Same installed type, topic `/net01e/controller/mechanism_grid`, domain97, legal160104B typed grid and20Hz supply. Each case gets a fresh writer (no stale transient control message), one typed rawFalse subscription, public SingleThreadedExecutor.spin_once. sys.setprofile matches the **exact** installed `OccupancyGrid.__init__.__code__` and confirms this subscription object in active `_take_subscription` ancestry. No setup constructor can trigger it. At the first match it saves in-memory mono/constructor/frame ancestry/sub metadata and removes the profile in both cases. Control continues to three actual callbacks and exit0. Intervention invokes exactly one `signal.raise_signal(SIGINT)` at that matched entry with the unchanged original Python default handler and NO ROS handler; no wrapper/type change/private take/library modification. The throw originates in the profile hook: that is the intentional test intervention, not proof the historical signal hit this constructor. Original full exception/cause/context/_take_subscription and lifecycle are persisted before actual nonzero is re-raised. Parent returns actual intervention nonzero, even for a supported mechanism.

One pair only; abort on any control failure. Each startup≤5wall, supply≤3wall/60publications, total inner20wall, outer24wall+2s grace. Supply remains live until actual child exit/deadline. Owned failure cleanup only TERM/1s then KILL/1s, recorded. No automatic repeat or third case. Constructor hook/real callback mono, original handler identity, exact subscription metadata and destroy/context order are preserved. Target string plus actual real-take hook strongly supports installed conversion mechanism susceptibility; it cannot name original A0 topic, recover missing historical PyErr or prove unique historical cause.

Exact command after a separate Root pin+START:

```bash
rtk proxy timeout --signal=TERM --kill-after=2s 24s bash net01/ros-python.sh /mnt/net01e/controller/mechanism_probe.py --output /mnt/net01e/controller/mechanism-01
```

Domain97 port check/unique output/exact-owned cleanup as before. No probe/ROS execution has occurred while preparing this source.

## Proposed external graceful candidate and minimal regression

The controlled mechanism was observed once (`mechanism-01/RESULT.md`): same-hook control3callback/exit0, constructor-entry SIGINT caused the actual installed target RuntimeError/exit1, destruction followed the error. This supports repairing this installed SIGINT conversion defect without claiming A0's unknown historical topic/unique cause.

Root selected the simpler scheduling adaptation: public `spin_once(timeout_sec=.05)`, handler sets a stop flag only and performs small in-memory observation. There is no guard/wakeup thread, signal mask, private take or arbitrary KeyboardInterrupt injection in the candidate. The finite idle wait bounds opportunity for Python signal processing when no DDS arrives; ready entities do not wait for the timeout. The same `graceful_spin.py` factory is mandatory for all four arms. `graceful_controller_bootstrap.py` is an inert common external entry point over the unchanged original A0/other bootstrap. GRACEFUL_ADMISSION=false and no runtime routes have been activated.

One external `node.send_goal` gate checks stop state at entry. A call already admitted is explicitly in-flight (not proof of DDS send/acceptance); it may finish while the current callback returns. A call entering after handler receipt is not submitted and is truthfully recorded, without fabricated Action rejection/success/result. The adapter exits after the current `spin_once` boundary, restores its wrappers and leaves ROS alive for unchanged frozen main/finally/close_controller. Genuine non-SIGINT RuntimeError always propagates. Original close cancels existing accepted goal_handles but does not drain pending acceptance; this candidate does not claim pending/lateaccept ownership closure, which remains the independent safety chain's responsibility and must be checked before any later Gazebo admission.

Inert `check_graceful.py` proposes exactly five short real-ROS child cases in domain97, once each:

1. Same exact installed OccupancyGrid constructor/take identity profile triggers one real SIGINT; now the constructor completes, its callback returns, and a callback's post-handler send_goal is blocked by the single gate. Expected actual exit0, one callback and no original submit.
2. Normal typed DDS receives three messages, then one SIGINT at callback boundary, expected0; no input/model changes.
3. No DDS/publisher at all; parent sends one SIGINT200ms after atomic ready. Expected0, actual request/handler/boundary latency recorded, no infinite native wait.
4. Real typed subscription callback deliberately raises `RuntimeError('NET01E_NON_SIGNAL_CALLBACK_FAILURE')`. Expected actual child1/full exception; adapter never turns it into success. Parent's final exit remains1 even when every case has its expected raw exit.
5. Reuse existing `check_action_wire.ControlledServer`, one real accepted NavigateToPose UUID, then callback SIGINT and a gated new submission attempt. Bind the original `CheckpointHeadquarters.halt` and call original `ros_headquarters.close_controller`; fixture allocator/ledger only record their hooks, with no model or inference. A separate live server context witnesses the original cancel request, status5 and public generated GetResult response5 for the exact UUID after the controller context closes. No Nav2/robot is started. Original Cancel response client receipt is not claimed if destruction precedes it. This covers an already accepted handle only, not pending/lateaccept.

Each child wait≤12wall, accepted-action segment≤7wall, total inner55wall/outer60wall+2s grace. Abort at first unexpected exit; no retries. Exact-owned TERM/1s then KILL/1s only on failed child deadline, recorded; no production activation or Gazebo. GRACEFUL_TEST_ADMISSION=false. Source-only AST parse passed; no regression has executed.

```bash
rtk proxy timeout --signal=TERM --kill-after=2s 60s bash net01/ros-python.sh /mnt/net01e/controller/check_graceful.py --output /mnt/net01e/controller/graceful-01
```

This is a proposal for Root/independent source review and a separate unique START, after the other agent's exclusive ROS collection finishes.
