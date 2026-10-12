"""Shared fixtures: throwaway Modbus TCP slaves on ephemeral ports."""
import socket
import struct
import threading

import pytest


def _serve(sock, handler):
    conn, _ = sock.accept()
    try:
        handler(conn)
    finally:
        try:
            conn.close()
        except OSError:
            pass


def _reply_handler(registers):
    def handle(conn):
        req = conn.recv(1024)
        if len(req) < 12:
            return
        tid, _pid, _len, unit, fc, _addr, cnt = struct.unpack(">HHHBBHH", req[:12])
        if fc == 0x03:
            body = struct.pack(">BB", fc, cnt * 2) + b"".join(
                struct.pack(">H", registers[i % len(registers)]) for i in range(cnt))
        else:
            body = struct.pack(">BB", fc | 0x80, 0x01)      # illegal function
        conn.sendall(struct.pack(">HHHB", tid, 0, len(body) + 1, unit) + body)
        # Closing straight away can discard the response if the client has not
        # read it yet, so hold the connection open until the peer goes away.
        try:
            conn.settimeout(5)
            conn.recv(1)
        except OSError:
            pass
    return handle


class FakeSlave:
    """A one-shot Modbus TCP slave bound to an ephemeral localhost port."""

    def __init__(self, handler):
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        self.host, self.port = sock.getsockname()
        self.thread = threading.Thread(target=_serve, args=(sock, handler), daemon=True)
        self.thread.start()
        self._sock = sock

    def close(self):
        self._sock.close()
        self.thread.join(timeout=2)


DOC_REGISTERS = [100, 250, 375, 500, 625, 750, 875, 1000, 1125, 1250]


@pytest.fixture
def slave():
    s = FakeSlave(_reply_handler(DOC_REGISTERS))
    yield s
    s.close()


@pytest.fixture
def silent_slave():
    """Accepts the connection, replies with nothing, then closes."""
    def handle(conn):
        conn.recv(1024)
    s = FakeSlave(handle)
    yield s
    s.close()


@pytest.fixture
def dead_port():
    """A port with nothing listening on it."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
