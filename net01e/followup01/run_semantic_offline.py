"""Single-purpose read-only ROS API environment for offline field comparison."""
import argparse
import json
from pathlib import Path
import subprocess
import time

REPO=Path(__file__).resolve().parents[2]
ROOTFS=Path('/home/zhuyulab/ns3-workspace/base-01-econ/isolation/rootfs')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();case='/mnt/'+str(args.case.resolve().relative_to(REPO))
    out=args.output.resolve();out.relative_to(REPO/'net01e/followup01');out.mkdir(exist_ok=False)
    argv=['bwrap','--unshare-user','--uid','0','--gid','0','--die-with-parent',
        '--ro-bind',str(ROOTFS),'/', '--tmpfs','/tmp','--ro-bind','/proc','/proc','--dev-bind','/dev','/dev',
        '--ro-bind',str(REPO),'/mnt','--bind',str(out),'/tmp/analysis','--chdir','/mnt',
        '/usr/bin/env','-i','PATH=/usr/sbin:/usr/bin:/sbin:/bin','HOME=/tmp','LANG=C.UTF-8',
        'LD_LIBRARY_PATH=/opt/ros/humble/lib',
        'PYTHONPATH=/opt/ros/humble/local/lib/python3.10/dist-packages:/opt/ros/humble/lib/python3.10/site-packages:/mnt/net01:/mnt',
        'PYTHONNOUSERSITE=1','PYTHONDONTWRITEBYTECODE=1','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1',
        '/usr/bin/python3','-B','/mnt/net01e/followup01/semantic_source_wire.py','--case',case,'--output','/tmp/analysis/results']
    (out/'argv.json').write_text(json.dumps(argv,indent=2)+'\n');begin=time.monotonic()
    with (out/'stdout.txt').open('x') as stdout,(out/'stderr.txt').open('x') as stderr:
        process=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=60)
    result=dict(exit=process.returncode,wall_s=time.monotonic()-begin,
                no_ros_init=True,read_only_repository=True,offline_saved_bodies_only=True)
    (out/'launch-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    return process.returncode


if __name__=='__main__':raise SystemExit(main())
