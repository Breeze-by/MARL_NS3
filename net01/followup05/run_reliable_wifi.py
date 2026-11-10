"""Own the single admitted Hub/native and rootfs ROS fixture, total60wall."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

repo=Path(__file__).resolve().parents[2]
case=repo/'net01/followup05/evidence/reliable-wifi-01'
case.mkdir(parents=True,exist_ok=False)
sock=repo/'f05-wifi-01.sock'
if sock.exists():raise FileExistsError(sock)
native=repo.parent/'build/followup03-release-portable-native/net01-payload'
hub_command=['python3','-B',str(repo/'net01/tools/packet_hub.py'),'--socket',str(sock),
    '--native',str(native),'--output',str(case/'hub'),'--profile','B','--wall','50',
    '--allow-radio-fault','--clock-source','gazebo','--control-trace']
ros_command=['bash',str(repo/'net01/ros-python.sh'),'/mnt/net01/followup05/check_reliable_wifi.py',
    '--socket','/mnt/'+sock.name,'--output','/mnt/net01/followup05/evidence/reliable-wifi-01/ros']
(case/'commands.json').write_text(json.dumps(dict(hub=hub_command,ROS=ros_command),indent=2)+'\n')
started=time.monotonic();deadline=started+60.;processes={};logs=[];forced=[]
result=dict(scope='single actual Gateway/DDS/ns3-WiFi fixture,0Gazebo/Nav2/Policy',status='FAIL')
try:
    for name,command in (('hub',hub_command),('ROS',ros_command)):
        if name=='ROS':
            until=min(deadline,time.monotonic()+10.)
            while not sock.exists() and time.monotonic()<until:
                if processes['hub'].poll() is not None:raise RuntimeError('Hub exited before IPC listen')
                time.sleep(.01)
            if not sock.exists():raise TimeoutError('owned Hub socket readiness')
        out=(case/(name+'.stdout.txt')).open('x');err=(case/(name+'.stderr.txt')).open('x');logs.extend((out,err))
        processes[name]=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True)
    ros_exit=processes['ROS'].wait(timeout=max(0.,deadline-time.monotonic()))
    hub_exit=processes['hub'].wait(timeout=max(0.,deadline-time.monotonic()))
    result.update(ROS_exit=ros_exit,hub_exit=hub_exit)
    if ros_exit or hub_exit:raise RuntimeError('owned ROS or Hub returned nonzero; preserve first fixture result')
    result['status']='PASS within staged synthetic fixture; expected final delivery INVALID remains recorded'
except BaseException as error:
    result['error']=repr(error)
finally:
    for name,process in processes.items():
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);forced.append(dict(role=name,PGID=process.pid,signal='SIGKILL'))
            process.wait()
    for log in logs:log.close()
    result.update(wall_s=time.monotonic()-started,forced=forced,
        exits={name:process.returncode for name,process in processes.items()})
    (case/'process-exit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
raise SystemExit(0 if result['status'].startswith('PASS') else 1)
