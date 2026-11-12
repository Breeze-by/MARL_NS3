# A1 direct failure and monitoring boundary

Direct failure is the recorder's uncaught **rosbag2 SqliteException / SQLITE_BUSY(5), database locked**, not a Guard/WiFi/RL failure. Original generic OR-process poll then raised at Unix1794386504.959917/Rsim177.25. Exploration was still alive and got SIGINT at1794386504.9611626,then exited0; launch remained alive until later SIGINT. Original end_process omits exit events for alreadydead children, so exactbagreturncode is **NOT_RECORDED**. Do not inventSIGABRTcode or naturalcontrollerexit.

Bagflush/openbag1 timestamped lines1794386463.508784438/.510448799 precede an untimestamped exception. The second line is41.449s before fatal and is **not** exactexceptiontime. Last active readonly probe sampled just beforeSQLiteopen at mono603546149712762±.5ms, tooltotal1.026304097s, readingbag1's last committedclock177.08 plus3odom with explicitcon.close beforeprint. Exactquery begin/end/close and lockowner were not recorded. It is a plausible monitoring-interference candidate; unique historicalreader causality and writerjournalmode remain **UNRESOLVED**. Actualquerycode/source/argv are preserved in `live-sql-monitor-evidence.json`.

The actualtb3 resultstatus6 is Unix1794386426.254362822,**78.706s beforefatal** and before finalSIGINT/PAUSE. It belongs to exploration, not shutdowncancel. ExactresultUUID/Nav2internalreason is unresolved from this smallstatuslog; no general navigationfailure-rate claim.

Futurecounterfactual must keep originalrecorder/core/Nav2/Policy/model unchanged and perform **no liveDB opens/SQL/PRAGMA**. Existing clockwitness is RAM-only until exit, so it is not a liveCSV tail source. Minimalmonitoring is exactowned processliveness; optional existingappendlog complete lines are nonauthoritativeprogress. Read witness/ACK/closedbag onlyafterwriterexit. No timeout/PRAGMA/bagdisable/source change, no newNode or mechanismunit. Any newA1 is separateRootSTART; this firstcase remainsFAIL156.2/180sim,with actualsafetystop and retainedfailedseal kept separate.

Smallstructured timeline/provenance: `BAG_FAILURE_TIMELINE.json`; canonicalraw evidence remains unchanged.
