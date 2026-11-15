"""Finite actual-wire HELLO/ACK bootstrap, never a source-data cache."""
import struct
import time

HELLO_FLOW = 65535
ACK_FLOW = 65534


class LinkSession:
    def __init__(self, hub, session_id):
        self.hub = hub
        self.nonce = struct.pack("!Q", session_id)
        self.acked = set()
        self.sent = False
        self.events = []

    def begin(self):
        if self.sent:
            raise RuntimeError("No implicit repeated connection attempts")
        self.sent = True
        for peer in (1, 2, 3):
            self.hub.send(0, peer, HELLO_FLOW, b"HELLO"+self.nonce)
            self.events.append(dict(kind="hello_sent", peer=peer, monotonic_ns=time.monotonic_ns()))

    def receive(self, meta, body, rpc_id):
        if meta["flow"] not in (HELLO_FLOW, ACK_FLOW):
            return False
        if rpc_id != 0:
            raise ValueError("Handshake cannot carry an Action RPC")
        sender, receiver = meta["sender"], meta["receiver"]
        if meta["flow"] == HELLO_FLOW:
            if sender != 0 or receiver not in (1,2,3) or body != b"HELLO"+self.nonce:
                raise ValueError("Invalid actual destination HELLO")
            self.events.append(dict(meta, kind="STA_received_hello", endpoint_monotonic_ns=time.monotonic_ns()))
            self.hub.send(receiver,0,ACK_FLOW,b"ACK"+self.nonce)
        else:
            if receiver != 0 or sender not in (1,2,3) or body != b"ACK"+self.nonce:
                raise ValueError("Invalid actual central ACK")
            self.acked.add(sender)
            self.events.append(dict(meta, kind="central_received_ACK", endpoint_monotonic_ns=time.monotonic_ns()))
        return True

    @property
    def ready(self):
        return self.acked == {1,2,3}
