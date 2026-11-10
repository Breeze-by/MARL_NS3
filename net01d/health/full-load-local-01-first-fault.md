# P5 A1 first failure: stale tb1 correction before R callback capture

Original case `net01d/runs/full-load-local-01`, checkpoint502ba02. Read-only
producer-side audit, no source change/retry, no ledger/bag scan. Derived narrow
records: [first-fault.json](full-load-local-01-first-fault.json) and
[tf-chain.json](full-load-local-01-tf-chain.json). Metric owns independent Action
and89/95 review; host resource judgement belongs to the producer.

## What actually tripped

The original guard event is earlier than the host FIRST_FAILURE file:
tb1 trip mono515752.091970897, actual R ROS clock1.22; tb2.095217565,
tb3.096491737. Host file mono515752.165523767 is detection, not the first trip.
The guard event itself supplies R simulation time; intake rows do not separately
record their evaluation ROS time, which remains unavailable for those calls.

All three had last accepted health seq11: ready=true, generated_sim1.1,
odom stamps all1.06; correction stamps tb1=.66, tb2/tb3=1.26.
At actual R1.22, tb1 correction age=.56sim exceeds unchanged.55sim.
Odom age=.16sim is below.4; correction future tests and other robots' correction
ages pass. The shared three-robot health predicate therefore fails for all
three guardians. This is not a heartbeat breach, false alarm or changed gate.
Seq12 has tb1 correction.86, but its R health receipt.109596453 follows the
already-latched fault; it cannot erase that expired interval.

Actual arm at R1.05/mono515751.743058630,.743666673,.744071693 succeeded through
the real services. C normal start mono515751.883656048; Goal requests.885026086
to.886297516; accepted responses.963143597 to.964340182. The first trip occurs
about349ms after arming and129ms after first accept. Normal32wall did not finish.
The source's old correction was still within the original limit at arm; this
does not certify future headroom or make the later real stale event erroneous.

## Where the source age was introduced

All three independent sources actually emitted80 map→odom messages,50wallHz,
with correct scan-holder+.2 stamps progressing.66/.86/1.06/1.26. Their source
ticks23/7/3 and skips0 are recorded. Source1 first map→odom was published at
515750.581978402, returned.582214869; no source publish call exceeded.303ms.
Its later1.26 messages began at515751.761909010 and continued through the fault.
No evidence points to the map template geometry, zero pose or new stamp formula
as the cause of this particular stale correction.

Gateway R flow23 did not first capture that stream until515751.607862301,
about1025.884ms after the first source publication began, and then received old
stamp.66. It captured only39 map→odom messages overall and ended still at.86.
Flows43/63 started capture at515750.585477420/.586449471, captured80 each and
reached1.26. These are actual callback captures, not independent DDS arrival times.

C flow23 has the same39 messages. Its first publication returned at
515751.608669813 (~.808ms after R capture); Peer callback starts.609616281,
and its actual input edge is.66. Later actual input edges are.86, matching the
R/C records. Thus the Peer Buffer did not turn a new1.26 edge into an old.66 edge.
The bad source-age stream is already old at Gateway R callback entry, upstream
of ideal direct delivery and C Peer projection. This A1 has no business WiFi hop.

No individual original wait/handler has a100ms execution span: R wait max5.140ms,
C wait1.526ms; largest C handler2.791ms and R handler1.597ms. Inclusive polls
can be long from many short handlers and are not equivalent to a single blackout.
The missing raw-DDS receive/ready timestamp prevents unique separation of
discovery/reliable middleware/cache readiness versus Python take scheduling.
Do not label it proven OS starvation, subscriber backlog cause or simulator Run.

## Smallest defensible next step

Keep the failed case and the original correction guard. Before selecting a
behavioral fix, inspect/observe the **source1 writer→Gateway R subscription**
boundary, not C map recomputation, health retransmission or clock IPC. Existing
source rows and R tf_edges are sufficient to establish old-at-capture, but not
the first middleware-arrival time. A passive per-writer matched-reader count at
the first source publish can test an initialization/matching hypothesis; it
cannot itself prove data delivery or justify ignoring startup failures.
Any actual startup barrier/transport/scheduling change requires root's causal
choice and independent review. Do not silently warm up, drain/drop old samples,
alter QoS or relax.55 merely to get a longer run. No fix has been applied here.
