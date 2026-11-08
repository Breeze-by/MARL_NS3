"""Bind only one executable among the specified debugger's direct children."""
import json
from pathlib import Path


def bind_owned_inferior(directory, launcher_pid, executable):
    children = Path(f'/proc/{launcher_pid}/task/{launcher_pid}/children').read_text().split()
    matches = [int(pid) for pid in children
               if (Path('/proc')/pid/'exe').exists()
               and (Path('/proc')/pid/'exe').resolve().name == executable]
    if len(matches) != 1:
        raise RuntimeError(f'Expected one owned {executable} inferior, got {matches}')
    pid = matches[0]
    identity = dict(launcher_pid=launcher_pid, pid=pid,
                    exe=str(Path(f'/proc/{pid}/exe').resolve()),
                    ownership='direct child of this exact launcher; executable matched')
    (Path(directory)/'gzserver-process.json').write_text(json.dumps(identity, indent=2)+'\n')
    return identity


def saved_owned_inferior(directory, launcher_pid, executable):
    path = Path(directory)/'gzserver-process.json'
    if not path.exists():
        return None
    identity = json.loads(path.read_text())
    if (identity['launcher_pid'] != launcher_pid or identity['pid'] == launcher_pid
            or Path(identity['exe']).name != executable):
        raise RuntimeError('Saved inferior is not this owned executable child')
    return identity
