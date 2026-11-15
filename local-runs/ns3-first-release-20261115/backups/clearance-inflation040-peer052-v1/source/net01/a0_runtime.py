"""A0 safety-only registration; no business relay, policy or launch integration.

The HQ hook runs after its original journal append and before the original
LoggedActionClient's DDS send. Registry.poll() belongs to the independent R
guardian loop, never to the inference executor. All clocks here are host mono.
"""
import json
import os
from pathlib import Path
import selectors
import socket
import time

from delivery_guard import LocalStop

ACK_TIMEOUT_S = .1
MAX_FRAME_BYTES = 2048


class SafetyAdmissionError(RuntimeError):
    pass


class A0LocalStop(LocalStop):
    """Only registered UUIDs can become owned/accepted from direct ROS evidence."""
    def register_uuid(self, uuid):
        if not self.guard.may_send_goal():
            return False
        self.owned.add(uuid)
        return True

    def response_evidence(self, uuid, accepted):
        # Called only for a registered UUID and the original actual journal
        # response. This is not a synthetic ROS SendGoal response.
        self.records.append(dict(kind='a0_actual_response_evidence',uuid=uuid,accepted=accepted))
        if not accepted:
            self.owned.discard(uuid)
        elif uuid not in self.terminals:
            self.accepted.add(uuid)
            if self.guard.fault or self.guard.halted:
                self.cancel_owned(uuid)

    def result_evidence(self, uuid, status):
        self.records.append(dict(kind='a0_actual_result_evidence',uuid=uuid,status=status))
        if status in (4,5,6):
            self.terminals[uuid]=status
            self.accepted.discard(uuid)
            self.owned.discard(uuid)

    def observe_status(self, message):
        # LocalStop already records real terminal statuses. Direct active
        # statuses also establish actual acceptance, but only for owned UUIDs.
        for status in message.status_list:
            uuid=bytes(status.goal_info.goal_id.uuid).hex()
            if uuid in self.owned and status.status in (1,2,3):
                if uuid not in self.accepted:
                    self.records.append(dict(kind='a0_actual_active_status',uuid=uuid,status=status.status,
                        monotonic_ns=time.monotonic_ns()))
                self.accepted.add(uuid)
                if self.guard.fault or self.guard.halted:
                    self.cancel_owned(uuid)
        super().observe_status(message)


class SafetyRegistry:
    """One private Unix listener, bounded nonblocking work per existing R poll."""
    def __init__(self, path, session_id, guards):
        self.path=Path(path)
        self.session_id=session_id
        self.guards=guards
        self.registrations={}
        self.events=[]
        self.selector=selectors.DefaultSelector()
        self.listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        # No unlink/reuse: an old socket is an ownership/setup error.
        self.listener.bind(str(self.path))
        os.chmod(self.path,0o600)
        self.listener.listen(8)
        self.listener.setblocking(False)
        self.selector.register(self.listener,selectors.EVENT_READ,None)
        self.connections={}

    def event(self, kind, **fields):
        self.events.append(dict(kind=kind,monotonic_ns=time.monotonic_ns(),**fields))

    def process(self, request):
        robot,uuid=request['robot'],request['uuid']
        if request['session_id']!=self.session_id or robot not in self.guards:
            raise ValueError('A0 safety session/robot mismatch')
        if len(bytes.fromhex(uuid))!=16:
            raise ValueError('A0 safety UUID must have 16 bytes')
        reply=dict(session_id=self.session_id,robot=robot,uuid=uuid,kind=request['kind'],
            token=request['token'],ok=False)
        if time.monotonic_ns()>=request['deadline_ns']:
            reply['reason']='expired_safety_request'
            return reply
        key=(robot,uuid)
        stop=self.guards[robot]
        if request['kind']=='request':
            if key in self.registrations:
                reply['reason']='duplicate_registration_not_a_send_permit'
            elif stop.register_uuid(uuid):
                self.registrations[key]=dict(token=request['token'],
                    registered_monotonic_ns=time.monotonic_ns())
                reply.update(ok=True,registered=True)
            else:
                reply['reason']='guardian_not_permitted'
        else:
            registration=self.registrations.get(key)
            if registration is None or registration['token']!=request['token']:
                reply['reason']='unregistered_UUID_or_token'
            elif request['kind']=='response':
                accepted=request['accepted']
                if type(accepted) is not bool or (accepted and request['accepted_uuid']!=uuid):
                    raise ValueError('Actual acceptance identity mismatch')
                stop.response_evidence(uuid,accepted)
                reply.update(ok=True,event_observed=True)
            elif request['kind']=='result':
                stop.result_evidence(uuid,request['raw_status'])
                reply.update(ok=True,event_observed=True)
            else:
                raise ValueError('Unknown A0 safety event')
        self.event('safety_registration_or_evidence',request=request,reply=reply)
        return reply

    def drop(self, connection):
        self.selector.unregister(connection)
        self.connections.pop(connection)
        connection.close()

    def poll(self):
        # No accept/read/send loop can wait for a client or complete a Goal.
        # A slow/incomplete client expires independently of its HQ lifetime.
        for connection,state in list(self.connections.items()):
            if time.monotonic()>=state['expires']:
                self.drop(connection)
        for key,mask in self.selector.select(0)[:8]:
            connection=key.fileobj
            if connection is self.listener:
                if len(self.connections)>=8:
                    continue
                accepted,_=connection.accept()
                accepted.setblocking(False)
                state=dict(input=bytearray(),output=b'',expires=time.monotonic()+ACK_TIMEOUT_S)
                self.connections[accepted]=state
                self.selector.register(accepted,selectors.EVENT_READ,state)
                continue
            state=key.data
            try:
                if mask & selectors.EVENT_READ:
                    data=connection.recv(MAX_FRAME_BYTES+1-len(state['input']))
                    if not data:
                        self.drop(connection)
                        continue
                    state['input'].extend(data)
                    if len(state['input'])>MAX_FRAME_BYTES:
                        raise ValueError('Oversize safety registration')
                    if b'\n' in state['input']:
                        line,rest=state['input'].split(b'\n',1)
                        if rest:
                            raise ValueError('Only one safety event per connection')
                        reply=self.process(json.loads(line))
                        state['output']=json.dumps(reply,separators=(',',':')).encode()+b'\n'
                        self.selector.modify(connection,selectors.EVENT_WRITE,state)
                elif mask & selectors.EVENT_WRITE:
                    sent=connection.send(state['output'])
                    state['output']=state['output'][sent:]
                    if not state['output']:
                        self.drop(connection)
            except BlockingIOError:
                pass
            except (ConnectionError,OSError):
                self.drop(connection)

    def snapshot(self):
        return dict(session_id=self.session_id,events=self.events,
            registrations=[dict(robot=r,uuid=u,**value) for (r,u),value in self.registrations.items()],
            connections=len(self.connections),
            owned_unknown_or_active={str(r):sorted(stop.owned) for r,stop in self.guards.items()})

    def close(self):
        for connection in list(self.connections):
            self.drop(connection)
        self.selector.unregister(self.listener)
        self.listener.close()
        self.selector.close()
        self.path.unlink()


class SafetyClient:
    def __init__(self, path, session_id):
        self.path=str(path)
        self.session_id=session_id

    def call(self, row, kind):
        deadline=time.monotonic()+ACK_TIMEOUT_S
        request=dict(session_id=self.session_id,robot=int(row['robot'][2:]),
            uuid=row['request_uuid'],token=row['token'],kind=kind,
            deadline_ns=int(deadline*1e9))
        if kind=='response':
            request.update(accepted=row['accepted'],accepted_uuid=row['accepted_uuid'])
        elif kind=='result':
            request['raw_status']=row['raw_status']
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
            connection.settimeout(max(0.,deadline-time.monotonic()))
            connection.connect(self.path)
            connection.settimeout(max(0.,deadline-time.monotonic()))
            connection.sendall(json.dumps(request,separators=(',',':')).encode()+b'\n')
            frame=bytearray()
            while b'\n' not in frame:
                connection.settimeout(max(0.,deadline-time.monotonic()))
                data=connection.recv(MAX_FRAME_BYTES+1-len(frame))
                if not data:
                    raise ConnectionError('Safety ACK missing')
                frame.extend(data)
                if len(frame)>MAX_FRAME_BYTES:
                    raise ValueError('Oversize safety ACK')
        line,rest=frame.split(b'\n',1)
        if rest:
            raise ValueError('Unexpected trailing safety ACK')
        response=json.loads(line)
        if time.monotonic()>=deadline:
            raise TimeoutError('Safety ACK deadline elapsed')
        if any(response[key]!=request[key] for key in ('session_id','robot','uuid','token','kind')):
            raise ValueError('Safety ACK identity mismatch')
        return response


def install_hq_record_hook(node, safety):
    """Return the original bound record method for explicit fixture restoration.

    Registration rejection/timeout raises before LoggedActionClient's original
    super.send_goal_async is entered. A response/evidence delivery failure does
    not erase its actual journal or fabricate a Nav2 response/terminal.
    """
    original_record=node.record
    kinds={'rl_actual_nav2_goal_request':'request','rl_actual_nav2_goal_response':'response',
        'rl_actual_nav2_goal_result':'result'}
    def record(row):
        original_record(row)
        kind=kinds.get(row.get('kind'))
        if kind is None:
            return
        try:
            response=safety.call(row,kind)
        except (OSError,ValueError) as error:
            original_record(dict(kind='a0_safety_registration_or_evidence_unknown',
                sim=node.now(),robot=row['robot'],request_uuid=row['request_uuid'],
                token=row['token'],original_kind=row['kind'],not_dispatched=(kind=='request'),
                registration_state='UNKNOWN',detail=repr(error)))
            if kind=='request':
                raise SafetyAdmissionError('A0 safety ACK unknown; actual Goal not dispatched') from error
            return
        original_record(dict(kind='a0_safety_ack',sim=node.now(),robot=row['robot'],
            request_uuid=row['request_uuid'],token=row['token'],original_kind=row['kind'],
            not_dispatched=(kind=='request' and not response['ok']),safety_ack=response))
        if kind=='request' and not response['ok']:
            raise SafetyAdmissionError('A0 registration denied; actual Goal not dispatched')
    node.record=record
    return original_record
