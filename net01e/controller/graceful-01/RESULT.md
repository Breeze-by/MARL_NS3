# External graceful adapter — bounded five-case qualification

Root START/pin `057e099648afa8da654e7d740b189aa83e5e12f5`; one fixed five-case execution,8.243432wall. Actual child raw exits **0/0/0/1/0** exactly match the declared cases. Actual parent exit **1** preserves the non-SIGINT RuntimeError child1. This expected test verdict is distinct from blanket all-process-exit0. No retry, production activation or Gazebo followed; production GRACEFUL_ADMISSION remains false.

| Case / exact PID | Actual evidence |
|---|---|
| Fixed constructor SIGINT /1106665 /0 | Same installed OccupancyGrid constructor code below real `_take_subscription:400`; one SIGINT returned without throwing, conversion completed, one callback returned. Its new send_goal was blocked at the single external gate; original submit calls0. |
| Normal DDS /1106680 /0 | Three real typed callbacks, then callback-boundary SIGINT, ROS alive at spin return, normal destroy/context shutdown. |
| Idle no DDS /1106692 /0 | One external SIGINT, no input publisher; handler47.843392ms and spin boundary48.068818ms after request-before. ROS alive at boundary. No native wait hang. |
| Non-SIGINT callback error /1106704 /1 | Actual `RuntimeError('NET01E_NON_SIGNAL_CALLBACK_FAILURE')`, complete executor/callback traceback preserved and bare re-raised; no signal was sent. |
| Original accepted-goal cancellation /1106716 /0 | Real controlled NavigateToPose accepted UUID `0102030405060708090a0b0c0d0e0f10`; post-handler new submission blocked; original halt/close invoked, server received cancel for the same UUID, public status5 and independent GetResult5 witnessed. |

Fixed hook request620901013069428ns → handler620901013114819ns → signal return620901013118958ns → callback620901013787610ns → safe spin boundary620901013925674ns → destruction begins620901014597812ns. The generic conversion failure previously observed under the default raising handler did not occur under this reviewed adapter, for the same controlled interruption location. Genuine unrelated errors remain nonzero.

Action handler620907245848863ns, callback returns620907245877405ns, spin boundary620907245924655ns with context alive. Original close620907246639283→620907249881251ns executes original `CheckpointHeadquarters.halt`, then closes controller context. Separate server context receives original cancel and status5 at620907253174447ns and public GetResult response5. The test uses existing ControlledServer and fixture allocator/ledger hooks; it does not load a model or execute real Nav2/motion. Original Cancel response **client receipt is not claimed** after controller destruction.

All exact child PIDs were waited to actual exit. No cleanup TERM/KILL occurred; postcheck found no check_graceful.py process or domain97 UDP31650–31899 participant. No robot/Goal allocator/SLAM/Nav2/safety threshold/model/701 encoding source changed.

Scope: the single gate admits entry into original send_goal, not actual DDS send or Nav2 acceptance. No in-flight-admitted call occurred in these stop cases. A call already past that gate may complete; original close cancels existing accepted handles but does not drain pending/late acceptance. That ownership boundary remains unproved here and must use the unchanged independent safety chain in any later integrated run. This fixes the demonstrated installed SIGINT/conversion failure mechanism; original A0's exact failing topic and historical unique trigger remain unknown, and its historical process-integrity FAIL is unchanged.
