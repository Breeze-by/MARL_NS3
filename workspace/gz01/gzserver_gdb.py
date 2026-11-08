"""GDB-only script: run once, save a stack only for a real SIGSEGV stop."""
import json
import os
from pathlib import Path
import sys

import gdb

sys.path.insert(0, str(Path(__file__).parent))
from debug_process import bind_owned_inferior

directory = Path(os.environ['BASE01_RUN_DIR'])
state = {'segv': False, 'exit_code': 1}
for command in ('set pagination off', 'set confirm off', 'set startup-with-shell off',
                'set disable-randomization off', 'set debuginfod enabled off',
                'set print thread-events off', 'handle SIGINT nostop noprint pass',
                'handle SIGTERM nostop noprint pass', 'handle SIGPIPE nostop noprint pass'):
    gdb.execute(command)


def stopped(event):
    if not isinstance(event, gdb.SignalEvent) or event.stop_signal != 'SIGSEGV':
        return
    identity = bind_owned_inferior(directory, os.getpid(),
                                   Path(gdb.current_progspace().filename).name)
    if identity['pid'] != gdb.selected_inferior().pid:
        raise RuntimeError('GDB inferior differs from owned executable child')
    state['segv'] = True
    (directory/'gzserver-sigsegv.json').write_text(json.dumps(
        dict(identity, signal=event.stop_signal, stage='inferior stopped before teardown'), indent=2)+'\n')
    (directory/'gzserver-sigsegv.txt').write_text(
        gdb.execute('info program', to_string=True)+'\n'+
        gdb.execute('thread apply all bt', to_string=True))


def exited(event):
    code = getattr(event, 'exit_code', None)
    if code is None:
        signal = gdb.parse_and_eval('$_exitsignal')
        code = 128+int(signal) if signal.type.code != gdb.TYPE_CODE_VOID else 1
    state['exit_code'] = code


gdb.events.stop.connect(stopped)
gdb.events.exited.connect(exited)
gdb.execute('run')
# A real fault stays stopped while the stack is written; batch teardown then
# kills that stopped inferior. Normal SIGINT is passed to the program instead.
gdb.execute('quit '+str(139 if state['segv'] else state['exit_code']))
