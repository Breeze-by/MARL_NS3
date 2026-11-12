# Actual reporting fixture — PASS, limited scope

One admitted invocation, runtime `197a21aa86b45fc67be41f9b6cd5ec811cc29125`, activation47a2b53. Actual outer exit0 in0.613227wall seconds, fixed timeout10s. No retry, ROS/native/Gazebo/Policy/bag or dependency installation.

The fixture compiled the actual new controller persistence statement, actual host load/outcome write, and the existing complete host save/integrity/return block from the two production source files. Original A0 and controlled-sidecar integrity gates were exercised with clean fixed inputs; the new predicate was not separately reimplemented.

| Actual input | Actual controller record | Actual host gate return / network integrity |
|---|---|---|
| Python child exit0 | startedtrue/PID863834/returncode0 |0 /true |
| Python child exit1 | startedtrue/PID863835/returncode1 |1 /false |
| Controller not created | startedfalse/PIDnull/returncodenull |1 /false |
| Actual Python child still alive | startedtrue/PID863836/returncodenull |1 /false |
| Marker missing, child actually exit0 | missing evidence, no invented controller0 |1 /false |

Actual persisted session/case/PID/observation monotonic fields were checked against the fixture. The alive child was terminated and waited only by fixture finally (returncode-15), with all four owned short Python children reaped; a subsequent `/proc` check confirms allgone. No production stop/wait/signal behavior was exercised or changed by this test.

[Actual result and source AST line ranges](result.json), [owned closure](owned-final.json), and adjacent `../controller-exit-reporting-01.launch.json`, `.exit.json`, `.stdout.txt`, `.stderr.txt` preserve the original invocation and outputs. Each case's actual host/network/controller JSON files remain in its exclusive subdirectory.

This verifies the reporting gate only. It does not fix or explain the A0 rclpy exception, qualify A0 Gazebo, or retroactively rewrite A0's raw host0/networktrue. The original A0 controllerexit1/FAIL remains. C requires separate Root admission/START.
