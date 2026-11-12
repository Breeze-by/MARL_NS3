# Fixed serial / session-RAM pair: SOURCE_READY, not executed

Only the original `run_native_tcp.py --case stream-01` is used: unchanged
18 messages, original bodies/routes/RPCs/source fields, 8 simulation seconds,
10 ms STEP sequence, B profile, seeds and original success conditions. There
are no new cases beyond `ntcp-ram-r1` and `ntcp-ram-c1`. No ROS/Node/Gazebo,
policy, replay, training or radio change is part of this pair. Old ntcp-lto
evidence is untouched.

Reference is the existing 0cc LTO driver at
`/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp`.
Candidate is the separately built r2 driver at
`/home/zhuyulab/ns3-workspace/net-01d/native-session-ram-followup02-r2/driver-out/net01-payload-tcp`,
SHA256 `928290702a71665c01858bed8fa8fd3a173e874e2d1e18f7c845ea6796e5a3e1`.
The earlier516d build01 was never run and is not this pair's candidate.
Both arms use only the existing13 DSOs under
`/home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/build/lib`,
with LD_PRELOAD/LD_AUDIT unset. Build02 identity is already recorded in
`native/session-ram-build-02/BUILD_IDENTITY.json`; no new hash scan is planned.

## Exact separately admitted commands

Working directory: `/home/zhuyulab/ns3-workspace/net-01d/workspace`.

Reference, once Root admits it:

```sh
rtk proxy python3 -B net01d/followup02/native/observe_session_ram_pair.py --arm reference
```

Only after reference succeeds and Root separately admits candidate:

```sh
rtk proxy python3 -B net01d/followup02/native/observe_session_ram_pair.py --arm candidate --candidate-native /home/zhuyulab/ns3-workspace/net-01d/native-session-ram-followup02-r2/driver-out/net01-payload-tcp
```

The observer additionally requires the reference wrapper's actual PASS before
it can launch candidate. Outputs are `native/session-ram-pair-01/{reference,candidate}`,
`runs/ntcp-ram-{r1,c1}` and distinct `/dev/shm/net01d-f02-ntcp-ram-{r1,c1}`.
Existing identities refuse reuse. `/usr/bin/time -v`, actual native executable,
all13 mapped library names/roots, original runner/Hub/time ancestry and exit/
remaining-owned proofs are saved by the thin observer, using the old observer's
`proc`/`owned_tree` helpers. Discovery stops after one actual READY/maps capture.

## Explicit deadline change and inert defaults

The runner adds just two test options, defaults `--native-ledger-mode serial`
and absent `--finalize-hard-deadline-ns`. Without the new deadline argument its
original active20, END flush≤1/start22, Hub wait≤5/start27 and success rules
remain unchanged. No other runner protocol was copied or replaced.

For both new arms the observer creates one absolute monotonic deadline at
observer start+60 seconds and logs its actual integer. It wraps the original
runner with `/usr/bin/time -v ... timeout --signal=TERM --kill-after=2s 60s ...`
and passes that **same** absolute deadline to the runner. This is an explicit,
Root-authorized test-only replacement of the runner's post-END Hub wait by
remaining absolute60; it is not a claim that all old internal bounds remain.
Original active20, END flush≤1/start22 and Hub active25 remain. Cleanup after
timeout is failure accounting, not an extension of the success deadline.

Reference remains serial: the Hub's original native post-END wait10 remains.
Candidate alone adds Hub `--native-ledger-mode session-ram-v1` and that same
`--finalize-hard-deadline-ns <logged absolute60>`, which the Hub converts to
native `--ledgerMode=session-ram-v1`. Candidate native finalization/copy/result
acceptance is bounded by `min(actual END+90s, absolute whole60s)`, so the90
allowance cannot add90 (or another60) to this test. Both arms fail if they miss
the common whole bound; original prefix, exit and forced-cleanup records remain.
Synchronous filesystem deadline checks are boundary acceptance checks, not a
guarantee that every filesystem call returns at an exact hard-real-time instant.

## Fixed comparison after both admitted executions

Require the original byte/resource PASS in each arm before claiming pair PASS.
Compare all18 original received `.bin` bodies byte-for-byte and retain original
route/RPC/source checks. Stream both original ledgers once in order, remove only
their actual wall-monotonic field for semantic comparison, and require the
original115,895 rows with identical remaining values/order/ns3 times and counts.
Compare all four PCAPs byte-for-byte. Do not filter new mismatches away; a
monotonic capture-point difference is disclosed, not called a model change.

Report native Run wall/CPU as sums of original `control-step-trace.jsonl`
begin/end wall and owning-thread CPU differences; these exclude END formatting.
Report `/usr/bin/time -v` user+system CPU, wall and peak RSS for the runner and
waited subtree, including native END persistence, Hub copy and runner analysis.
Do not confuse this subtree figure with pure native CPU or hide END cost behind
the Run saving. Preserve original Hub storage/copy durations and poststop
finalize marker/deadline/result; explicitly check full copied evidence and
`attempted == captured == written`/failedfalse/one transport_end.

For RAM, report actual `peak_pending_including_inflight`, corrected
`pending_capacity_records`32M, reserved vector capacity, record_size136,
`owned_capacity_bytes`/8GiB accounting limit, writer/model CPU and actual RSS.
The8GiB value is conservative ledger-owned capacity accounting, not a process
RSS bound. Serial's pending peak does not measure the lifetime RAM vector.
No performance or300ms conclusion is granted by source readiness or process0.
