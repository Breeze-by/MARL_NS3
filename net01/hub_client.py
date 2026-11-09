"""Framed, nonblocking single-owner IPC client; no ROS or source-blob lookup."""
import json
import select
import socket
import struct
import time


class HubClient:
    def __init__(self, path):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(str(path))
        self.socket.setblocking(False)
        self.outgoing = bytearray()
        self.incoming = bytearray()
        self.ready = False
        self.horizon_ns = 0
        self.deliveries = []
        self.receive = None

    def frame(self, meta, body=b""):
        self.outgoing.extend(json.dumps(dict(meta, bytes=len(body))).encode()+b"\n"+body)

    def send(self, sender, receiver, flow, cdr, rpc_id=0, source_stamp_ns=0, admission_ns=None):
        # RPC identity is transmitted, never reconstructed from a source-side table.
        meta=dict(kind="send", sender=sender, receiver=receiver, flow=flow,source_stamp_ns=source_stamp_ns)
        if admission_ns is not None:meta["admission_ns"]=admission_ns
        self.frame(meta, struct.pack("!Q", rpc_id)+cdr)

    def clock(self, horizon_ns):
        self.frame(dict(kind="clock", horizon_ns=horizon_ns))

    def observed_clock(self,horizon_ns):
        self.frame(dict(kind="observed_clock",horizon_ns=horizon_ns))

    def network_position(self,robot,x,y,z):
        self.frame(dict(kind="position",robot=robot,xyz=[x,y,z]))

    def radio_fault(self, enabled):
        self.frame(dict(kind="radio_fault", enabled=bool(enabled)))

    def poll(self):
        readable, writable, _ = select.select([self.socket], [self.socket] if self.outgoing else [], [], 0)
        if writable:
            size = self.socket.send(self.outgoing)
            del self.outgoing[:size]
        if readable:
            data = self.socket.recv(1024*1024)
            if not data:
                raise EOFError("Owned native transport connection closed")
            self.incoming.extend(data)
        while True:
            end = self.incoming.find(b"\n")
            if end < 0:
                break
            meta = json.loads(self.incoming[:end])
            size = meta["bytes"]
            if len(self.incoming) < end+1+size:
                break
            body = bytes(self.incoming[end+1:end+1+size])
            del self.incoming[:end+1+size]
            if meta["kind"] == "ready":
                self.ready = True
            elif meta["kind"] == "clock_return":
                self.horizon_ns = meta["horizon_ns"]
            elif meta["kind"] == "delivered":
                if len(body) < 8:
                    raise ValueError("Missing transmitted RPC identity")
                rpc_id, = struct.unpack("!Q", body[:8])
                self.deliveries.append(dict(meta, endpoint_receive_monotonic_ns=time.monotonic_ns()))
                if self.receive is not None:
                    self.receive(meta, body[8:], rpc_id)
            else:
                raise ValueError("Unsupported native transport frame")

    def end(self):
        self.frame(dict(kind="end"))

    def close(self):
        self.socket.close()
