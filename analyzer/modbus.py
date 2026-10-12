import socket
import struct

MBAP_LEN = 7
READ_HOLDING = 0x03


def build_read_holding(unit, addr, count, tid=1):
    """Build a Modbus TCP MBAP + PDU frame for FC03 read holding registers."""
    return struct.pack(">HHHBBHH", tid, 0, 6, unit, READ_HOLDING, addr, count)


def parse_mbap(data):
    """Split an MBAP header off the front of a response. None if too short."""
    if len(data) < MBAP_LEN:
        return None
    tid, pid, length, unit = struct.unpack(">HHHB", data[:MBAP_LEN])
    return {"tid": tid, "pid": pid, "length": length, "unit": unit, "pdu": data[MBAP_LEN:]}


def parse_pdu(pdu):
    if not pdu:
        return {"error": "empty"}
    fc = pdu[0]
    if fc & 0x80:
        if len(pdu) < 2:
            return {"error": "truncated exception"}
        return {"function": fc & 0x7F, "exception": pdu[1]}
    if fc == READ_HOLDING:
        if len(pdu) < 2:
            return {"error": "truncated response"}
        byte_count = pdu[1]
        if byte_count % 2:
            return {"error": "odd byte count", "byte_count": byte_count}
        if len(pdu) < 2 + byte_count:
            return {"error": "truncated response", "byte_count": byte_count,
                    "received": len(pdu) - 2}
        regs = struct.unpack(">" + "H" * (byte_count // 2), pdu[2:2 + byte_count])
        return {"function": "read_holding", "registers": list(regs)}
    return {"function": fc, "raw": pdu.hex()}


def _recv_exactly(sock, n):
    """Read exactly n bytes, or fewer only if the peer closes first."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def scan(host, port=502, unit=1, start=0, count=10, timeout=2.0):
    """Send one read-holding-registers request and parse the reply.

    Returns a parsed PDU dict, or {"error": ...} on any transport or framing
    problem. Never raises for a socket condition, so a caller always gets a
    report it can write to disk.
    """
    frame = build_read_holding(unit, start, count)
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(frame)
            head = _recv_exactly(s, MBAP_LEN + 2)          # MBAP + FC + byte count
            if len(head) < MBAP_LEN:
                return {"error": "short response", "received": len(head)}
            mbap = parse_mbap(head)
            # MBAP "length" counts the unit id plus the PDU after it, so the
            # full frame is that plus the 6-byte tid/pid/length header.
            expected = MBAP_LEN - 1 + mbap["length"]
            if len(head) < expected:
                head += _recv_exactly(s, expected - len(head))
    except OSError as exc:
        return {"error": "transport", "detail": str(exc)}

    if len(head) < expected:
        return {"error": "truncated response", "received": len(head), "expected": expected}
    # Re-split the MBAP off the *complete* frame: mbap["pdu"] above was sliced
    # from the first 9 bytes and does not contain the register data.
    return parse_pdu(parse_mbap(head)["pdu"])
