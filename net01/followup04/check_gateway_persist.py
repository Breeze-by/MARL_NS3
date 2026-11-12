"""One real sealed-data output check, 0Node/ROS/GZ; never rewrite the input.

Peak includes original text, parsed data and encoded text, unlike production's
already captured object graph. It is not a runtime memory bound.
"""
import argparse
import json
from pathlib import Path
import resource
import time


def main(source,output):
    output.mkdir(parents=True,exist_ok=False)
    result=dict(status='FAIL',input=str(source),output=str(output/'network-gateway.json'),
        input_bytes=source.stat().st_size,scope='Single real A10 JSON, default dumps exact text comparison; no original slow dump replay; 0Node/ROS/GZ/NN')
    try:
        began=time.monotonic();original=source.read_text();data=json.loads(original)
        result['read_and_parse_wall_s']=time.monotonic()-began
        began=time.monotonic();encoded=json.dumps(data)
        result['encode_wall_s']=time.monotonic()-began
        result['exact_text_equal']=encoded==original
        if not result['exact_text_equal']:raise AssertionError('Default C-encoder changed saved JSON text')
        began=time.monotonic()
        with (output/'network-gateway.json').open('x') as stream:stream.write(encoded)
        result['write_and_close_wall_s']=time.monotonic()-began
        result['encode_write_wall_s']=result['encode_wall_s']+result['write_and_close_wall_s']
        result['output_bytes']=(output/'network-gateway.json').stat().st_size
        result['peak_test_RSS_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result['status']='PASS'
    except BaseException as error:result['error']=repr(error);raise
    finally:(output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    main(args.input,args.output)
