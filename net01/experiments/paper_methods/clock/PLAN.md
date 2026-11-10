# Synthetic clock IPC matched trial plan

Status: ROOT REVIEWED / ADMITTED for one fixed-01 execution of the three fixed cases; metric static review accepted. No additional case, retry or parameter change authorized.
Scope: Python standard library, controlled synthetic clock, true local processes.
No ROS init/Node, ns-3, Gazebo, Nav2, training, dependency installation or host network changes.
This reimplements a MUNILS-inspired single-value idea; it is not its unpublished scheduler patch or a Gazebo reproduction. The 1000Hz microbenchmark borrows the paper frequency, not the current production 100Hz simulated / approximately 50Hz wall profile or a full ROS workload qualification. It cannot certify SHM age<=1ms or the original 300ms safety gate.

## Fixed cases and limits

One preregistered execution, no seed/parameter scan or automatic rerun.
Three paired cases; each source active interval 3.0 wall seconds, each case hard limit 15 wall seconds.
1. baseline: 1000Hz synthetic clock; both receivers poll at nominal 1000Hz.
2. reader_pause: same input/polls; both readers intentionally skip all IPC reads for 140ms starting at source epoch+1.0s.
3. source_pause: same input/polls; source generates no new clock from epoch+1.0s through epoch+1.35s (350ms).
No catch-up generation burst after a pause; simulation clock/sequence advances only on actual generated samples.
Schedules use absolute monotonic deadlines; OS scheduling misses are recorded, not hidden by catch-up loops.

## Real processes and IPC

A small host driver owns one source process and two receiver processes per case.
All processes are started before the source epoch; a pipe readiness barrier precedes the fixed epoch. Receivers observe for 3.1wall seconds, including 100ms after the 3.0wall source interval for explicit source-exit/EOF evidence.
The source assigns one common sequence/synthetic clock value and one generation monotonic timestamp to each update.
It exposes that update through (a) an aligned eight-byte mmap latest clock value and (b) newline JSON over AF_UNIX SOCK_STREAM.
The source alternates transport write order by sequence parity and records both publish boundaries.
The eight-byte value identifies the source-log entry; generation timestamps are joined offline by exact clock value/sequence.
No extra timestamp metadata is inferred from the shared value, and atomic visibility does not imply a freshness bound.
The mmap file lives in an exclusive owned temporary directory; UDS uses an unnamed AF_UNIX SOCK_STREAM socketpair, without filesystem socket cleanup or any IP interfaces/routes.

## Matching and observable limits

Both receivers use the same nominal 1ms poll schedule and retain only the newest complete update observed per poll.
The UDS reader drains all currently available complete frames nonblocking before selecting newest; it does not replay FIFO updates to consumers.
SHM reads one latest value per poll. Transport-specific drain/JSON cost is measured as real cost, not treated as an equal amount of work.
Intermediate overwritten/drained updates and socket backlog are explicitly counted.
Source socket writes are nonblocking with the actual pending-byte queue and publish completion recorded; overflow/errors fail visibly.
The small fixed workload should normally fit the socket buffer, but the experiment will report source backpressure rather than fake identical publication times.
This is a matched latest-value application-policy comparison, not a claim that stream IPC and SHM have identical buffering semantics.
The JSON payload carries sequence and integer clock value; this is a synthetic reduction of the existing JSON/Unix IPC pattern, not the production protocol/Hub/ACK path.
The old production adapter, native backend and CORNET code are not executed or modified.

## Evidence and metrics

During source operation each process keeps primitive evidence rows in RAM; it persists after its active loop ends.
Generation, publish/read boundaries and receipt use same-host monotonic_ns; each artifact identifies case, PID, transport and sequence.
Capture process/thread CPU and actual poll interval; do not mix system time and monotonic intervals.
Report common source generation to first consumer receipt age, publish-to-receipt age, observed source-age per poll, missed generations and read/drain CPU.
For each deliberate pause retain the surrounding polls, maximum stale age and the first newest sample consumed after recovery.
A repeated SHM value or repeated UDS last value is not a new source update; a missing/exited source cannot be replaced by wall-clock progression.
The 350ms source pause must be visible as aging of the last real generation across 300ms; this is diagnostic observation, not a new safety gate.
The 140ms reader pause must remain visible in receipt gaps for both transports; SHM cannot retrospectively remove a period in which no reader ran.
Actual exit codes, bounded owned cleanup and all failures are preserved. No statistical significance or end-to-end robot capacity claim.

## Coordination

Clock trials run before the producer's native trials; no simultaneous CPU measurement.
Only the files in this clock directory and its small results directory are owned here.
Static source inspection/AST preparation is allowed now; no trial process starts until root grants the concrete command.
