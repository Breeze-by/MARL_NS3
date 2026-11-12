"""tcp-ram-01 source-epoch check and reused original one-time load observer."""
import hashlib
import json
import subprocess
import time

from observe_lto_full import main as observe_full
from observe_lto_pair import BASE,REPO


def main():
    admission_path=BASE/'TCP_RAM_FULL_ADMISSION.json'
    admission=json.loads(admission_path.read_text())
    if admission['execution_authorized'] is not True:
        raise RuntimeError('Root tcp-ram-01 admission is pending')
    expected=admission['source_epoch_sha256']
    source=admission['source_checkpoint']
    if source.startswith('PENDING'):
        raise RuntimeError('Final source checkpoint has not been bound')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    if subprocess.run(['git','merge-base','--is-ancestor',source,head],cwd=REPO).returncode:
        raise RuntimeError('Admitted runtime source is not an ancestor of actual HEAD')
    before={name:hashlib.sha256((REPO/name).read_bytes()).hexdigest() for name in expected}
    if before!=expected:raise RuntimeError('Admitted replay/source epoch bytes changed')
    native=admission['argv'][admission['argv'].index('--native')+1]
    from pathlib import Path
    if hashlib.sha256(Path(native).read_bytes()).hexdigest()!=admission['native_sha256_reused']:
        raise RuntimeError('Admitted r2 native ELF bytes changed')
    path=BASE/'evidence/tcp-ram-01-source-epoch.json'
    epoch=dict(source_checkpoint=source,actual_HEAD=head,before_monotonic_ns=time.monotonic_ns(),
        before_sha256=before,scope='Declared replay/source/adapter files and exact r2 ELF only; not an exhaustive transitive-dependency proof')
    with path.open('x') as stream:json.dump(epoch,stream,indent=2);stream.write('\n')
    try:
        code=observe_full(admission_path,BASE/'evidence/tcp-ram-01-loader')
    finally:
        epoch.update(after_monotonic_ns=time.monotonic_ns(),
            after_sha256={name:hashlib.sha256((REPO/name).read_bytes()).hexdigest() for name in expected})
        epoch['declared_source_epoch_unchanged']=epoch['before_sha256']==epoch['after_sha256']
        path.write_text(json.dumps(epoch,indent=2)+'\n')
    return code if epoch['declared_source_epoch_unchanged'] else 1


if __name__=='__main__':raise SystemExit(main())
