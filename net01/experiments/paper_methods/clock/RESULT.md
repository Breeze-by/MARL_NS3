# fixed-01 synthetic clock IPC result

One root-admitted execution of the three preregistered paired cases; no retry or parameter change.
Outer actual exit0, elapsed10.879234364wall. All nine child exits0; no forced child cleanup.
Raw evidence: [fixed-01](results/fixed-01/), [command](results/fixed-01-command.json), [outer exit](results/fixed-01-process-exit.json).
The source is controlled synthetic clock, not Gazebo. 1000Hz generation/poll borrows MUNILS's frequency;
it is not the production 100Hzsim / approximately50Hzwall profile or a full ROS/ns3 workload qualification.

## Baseline

Freshness below is generation monotonic time to first receipt of a newly selected value, joined by exact clock/sequence.
Both receivers use latest-value consumption; UDS drains all complete available JSON frames before selecting newest.

| Metric | SHM eight-byte mmap | JSON / AF_UNIX stream |
| --- | ---: | ---: |
| Freshness median / p95 ms | 1.003491 / 1.010720 | 1.044947 / 1.062984 |
| Read CPU median / p95 us | 4.410 / 7.010 | 45.333 / 62.538 |
| Read CPU total ms | 15.103962 | 141.978390 |
| Measured receiver process CPU ms | 96.670173 | 221.105202 |
| Polls / observed new values | 3095 / 2976 | 3098 / 2963 |
| Latest-policy unobserved generations | 18 | 31 |

Source generated2994 values; UDS parsed all2994 complete frames. Unobserved generations are not IPC/UDP loss.
SHM had lower read CPU and a small freshness difference in this single development case; no statistical significance or production capacity claim.
The receiver process CPU includes its initialization/control-wait/loop work; read CPU measures only the read/drain/parse span.

## Deliberate reader pause

Both readers were scheduled to skip reads from epoch+1.0s through+1.14s while the source continued.

| Observed fact | SHM | UDS |
| --- | ---: | ---: |
| Largest read-entry gap ms | 141.117572 | 141.113904 |
| Age of consumer-held source value at pause end ms | 142.111467 | 142.112937 |

SHM did not remove the period without consumer reads. A fresh latest value after recovery does not erase that held-value interval.
UDS parsed all2988 source frames, including the buffered batch; it selected only latest values for consumers.

## Deliberate source pause / exit

The source generated no new clock during epoch+1.0s through+1.35s; it did not catch up missing ticks or fall back to wall time.

| Observed fact | SHM | UDS |
| --- | ---: | ---: |
| Maximum age of last real generation ms | 351.018236 | 351.034537 |
| Polls with source age >300ms | 52 | 52 |
| Real EOF observed after source exit | No | Yes |

SHM remained readable while its value aged. Its slot alone supplies no writer-exit/EOF indication.
UDS has a real EOF indication, but repeated last values also aged; neither channel fabricated new source generations.
All three cases reached the same final source clock on both readers. Socket backpressure events were zero in each case.
Receivers deliberately observed100ms beyond source termination; repeated-value tail age is not new-message delivery latency.

## Interpretation limits

Publication-return to receipt differences are retained exactly, without clipping: a receiver can observe bytes before the source is scheduled to record send-return.
Such a negative difference would describe cross-process observation boundaries, not physical negative transport delay.
The common generation-to-receipt metric uses the source's prepublication timestamp.
This small paired trial supports lower SHM read/parse overhead here and explicitly reproduces stale held values under reader/source pauses.
It does not establish SHM staleness<=1ms, the original300ms safety-gate PASS, full simulator synchronization, Action reliability, or a NET01 qualification.
No ROS init/Node, ns3, Gazebo, Nav2, training, dependency installation, IP/network configuration or Git operation occurred.
