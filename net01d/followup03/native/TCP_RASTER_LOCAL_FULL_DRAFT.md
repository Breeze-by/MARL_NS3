# PACE10+raster A1 Full — inert configuration ablation

`TCP_RASTER_LOCAL_FULL_ADMISSION.json` is false; runtime/source checkpoint PENDING. The exact newprofile is `controlled1000-clock100-q10ms-pace10-raster`: originalPACE10 numeric profile plus equivalentbroadcast-v1 raster, no separate Gateway controlclock lane. Gateway implementation/ordinary R clock handling/STEPowner remain unchanged. This is a bounded configuration comparison motivated by existing service evidence, not an establishedrootcause fix or performance promise.

Prepared outer command, cwdrepo:
```
rtk proxy python3 -B net01d/followup03/native/observe_raster_local_full.py
```
Prepared original A1 harness command, cwd `/home/zhuyulab/ns3-workspace`:
```
rtk proxy python3 -B net-01d/workspace/net01d/run_replay.py --stage full --arm A1 --case actual-phase-local-01 --output-dir /home/zhuyulab/ns3-workspace/net-01d/workspace/net01d/followup03/runs/tcp-raster-local-01 --payloads /home/zhuyulab/ns3-workspace/net-01d/workspace/net01d/health/payloads-01 --native /home/zhuyulab/ns3-workspace/net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp --native-transport tcp-mtu-v2 --dds-take-trace --mock-phase actual-corr6201 --native-evidence-ram /dev/shm/net01d-f03-tcp-raster-local-01 --main-thread-sample --adapter-qos-events warning-free-v1 --execution-profile controlled1000-clock100-q10ms-pace10-raster --native-ledger-mode serial
```

Compared with prior A1 request, only output/RAM/profile argv values differ. Native is original0cc serial/same13LTO; A1 business uses the existing ordered local Gateway path, native receives originalclock/modelcontrol only. No nativecopy/sessionRAM/profiler variant. Tmpfs remains original evidence storage. Unique case/output/RAM/loader paths and sub108bytewire.sock are in admission.

Original32normal/60hard/3normalGoal4,4,5/RPCdrain/fourthtb3acceptedGetResultready/.8wallSUPPLY_STOP negative remain; local Action/PAUSE services keep spinning, noRADIO_OFF. Keepfirstfailure, originalsource rates/stamps/payloads,300ms health/mask,200ms pose receipt,.4simodom/.55simcorrection, quantum/credit and ownedcleanup; report actualcentralterminal or UNKNOWN honestly. No retries/Gazebo/B or extra windows.

Retain all priorclocklane failures and the verified675ms pre-native publication→take chain. Future scientific A0/A1/B/C references must share this newprofile. Source/profile review/fixedruntimecommit and Root explicitSTART remain required. Prepared JSON/AST and3-valueargvdelta only; no sourceimplementation edit/model/commit by this producer.
