# Actual Gazebo phase check: the old runs are aligned, unlike MOCK+5ms

Only old coordinator JSON and independent R clock CSV were read. No Gateway
large JSON, native ledger, bag, node, simulator, hash, source change or new run.
Full counts and selected original records: [real-gazebo-phase-01.json](real-gazebo-phase-01.json).

| Actual old case | Valid contiguous10ms/10iteration ACKs | ACK with latest coordinator-observed G=E | Exact matching E in independent R CSV |
| --- | ---: | ---: | ---: |
| A10 direct |14322|14322 (100%)|14322|
| B01 Wi-Fi |10951|10951 (100%)|10951|

All E values are integer multiples of10ms. In **every** original coordinator
post_physics_ACK record the already-observed actual clock equals completed E.
Because each recorded actual-clock callback precedes that ACK observation, the
sample had already been published; this does not rely on converting a DDS system
timestamp into monotonic time. At this observed ACK boundary, G=E, not E−5ms.
The comparison is at coordinator ACK receipt, not an invented server-side wall
timestamp inside World::Step. Both records show fixed_offset_ns=10000000.

Concrete B01 E103.33: coordinator records[41336] ACKmono458208.160635003,
latest observed G103.33. `clock-R.csv` line10334 has G103.33, callbackmono
458208.158679964, sourceDDS timestamp1794241166675771575; it precedes ACK.
A10 records[41336] has ACKmono450246.719548467 with G103.33, and RCSV line10334
callback450246.717662253/sourceDDS1794233205234317530. First ACKs are0→10ms,
last completed E143.22/A10 and109.51/B01, with the same alignment throughout.

The independent witness was sometimes scheduled late: at ACK observation A10's
last witness callback lags E by10ms110 times and20ms once; B's lags10ms71 times.
The coordinator already observed E in all those cases, and every exact E sample
exists in the witness CSV. Those callback delays are **not physical clock phase**.
Each case has one witness publisher GID; this analysis does not reinterpret
`received_timestamp` as an earliest-arrival guarantee.

MOCK explicitly starts at5ms and publishes actual synthetic clock on10ms
crossings. Its E=G+5ms deliberately stresses a different phase. With the current
literal physical-end credit, that can remove an otherwise available10ms token
of overlap; its one-ACK/one-token critical path is not the observed old Gazebo
phase. Preserve all old MOCK stress failures and all real B01 failures, including
the original137ms health wait. Neither old real success/failure nor this phase
check proves that a new phase-aligned full-load Wi-Fi fixture will pass.

An explicitly registered phase0 fixture would have evidence as a **fixture
contract correction**, not permission to enlarge physical credit, lower rates,
change the300ms gate or rewrite the5ms stress result. It still uses the original
iteration-driven clock publication and must not add an artificial terminal clock.
No such edit or execution was performed by this check. Evidence is limited to
these two old configurations, including their different plugin/I/O versions and
business loads; it is not a universal assertion about every future Gazebo phase.
