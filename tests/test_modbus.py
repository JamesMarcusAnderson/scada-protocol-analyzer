import json
import pathlib
import struct

import pytest

from analyzer import modbus

DOCS = pathlib.Path(__file__).parent.parent / "docs" / "modbus-output.json"


def test_request_frame_is_a_valid_12_byte_mbap_pdu():
    frame = modbus.build_read_holding(unit=1, addr=0, count=10, tid=1)
    assert frame == bytes.fromhex("00010000000601030000000a")
    assert len(frame) == 12
    tid, pid, length, unit, fc, addr, cnt = struct.unpack(">HHHBBHH", frame)
    assert (tid, pid, length, unit, fc, addr, cnt) == (1, 0, 6, 1, 3, 0, 10)


def test_round_trip_against_live_slave(slave):
    assert modbus.scan(slave.host, slave.port, 1, 0, 10) == {
        "function": "read_holding",
        "registers": [100, 250, 375, 500, 625, 750, 875, 1000, 1125, 1250],
    }


def test_scan_reproduces_committed_docs_sample(slave):
    """docs/modbus-output.json must be output this code can actually produce."""
    expected = json.loads(DOCS.read_text())
    assert modbus.scan(slave.host, slave.port, 1, 0, 10) == expected


def test_exception_response_is_decoded():
    assert modbus.parse_pdu(bytes([0x83, 0x02])) == {"function": 3, "exception": 2}


def test_unknown_function_falls_through_to_raw():
    assert modbus.parse_pdu(bytes([0x10, 0x00, 0x00])) == {
        "function": 0x10, "raw": "100000"}


@pytest.mark.parametrize("pdu,expected", [
    (b"", {"error": "empty"}),
    (bytes([0x03]), {"error": "truncated response"}),
    (bytes([0x83]), {"error": "truncated exception"}),
    (bytes([0x03, 0x04, 0x00, 0x64]), {"error": "truncated response",
                                       "byte_count": 4, "received": 2}),
    (bytes([0x03, 0x03, 0x00, 0x64, 0x00]), {"error": "odd byte count", "byte_count": 3}),
])
def test_malformed_pdus_report_errors_instead_of_raising(pdu, expected):
    assert modbus.parse_pdu(pdu) == expected


def test_short_mbap_returns_none():
    assert modbus.parse_mbap(b"\x00\x01\x00\x00") is None


def test_unreachable_host_returns_error_not_traceback(dead_port):
    result = modbus.scan("127.0.0.1", dead_port, 1, 0, 10, timeout=0.5)
    assert result["error"] == "transport"


def test_peer_that_says_nothing_returns_short_response(silent_slave):
    result = modbus.scan(silent_slave.host, silent_slave.port, 1, 0, 10, timeout=1.0)
    assert result == {"error": "short response", "received": 0}
