import pytest

from analyzer import obd


def _sf(sid, pid, *payload):
    """Build an ISO 15765-2 single frame: PCI, SID, PID, payload."""
    data = bytes([len(payload) + 2, sid, pid, *payload])
    return data + bytes(8 - len(data))


def test_rpm_matches_docs_sample():
    # 0x1B58 = 7000 raw; 7000 / 4 = 1750 rpm
    assert obd.decode_frame(0x7E8, _sf(0x41, 0x0C, 0x1B, 0x58)) == {
        "pid": "0x0C", "name": "RPM", "value": 1750.0, "unit": "rpm"}


def test_speed_matches_docs_sample():
    assert obd.decode_frame(0x7E8, _sf(0x41, 0x0D, 0x2A)) == {
        "pid": "0x0D", "name": "Speed", "value": 42, "unit": "km/h"}


def test_coolant_matches_docs_sample():
    # 88 C requires A - 40 == 88, i.e. A == 128 == 0x80
    assert obd.decode_frame(0x7E8, _sf(0x41, 0x05, 0x80)) == {
        "pid": "0x05", "name": "Coolant Temp", "value": 88, "unit": "C"}


def test_fuel_and_throttle():
    assert obd.decode_frame(0x7E8, _sf(0x41, 0x2F, 0xFF))["value"] == pytest.approx(100.0)
    assert obd.decode_frame(0x7E8, _sf(0x41, 0x11, 0x00))["value"] == pytest.approx(0.0)


def test_other_response_ids_are_accepted():
    assert obd.decode_frame(0x7EF, _sf(0x41, 0x0D, 0x2A))["value"] == 42


@pytest.mark.parametrize("can_id", [0x7DF, 0x7E0, 0x123, 0x7F0])
def test_non_response_ids_are_ignored(can_id):
    assert obd.decode_frame(can_id, _sf(0x41, 0x0D, 0x2A)) is None


def test_request_sid_is_not_a_response():
    assert obd.decode_frame(0x7E8, _sf(0x01, 0x0D, 0x2A)) is None


def test_negative_response_is_not_a_pid():
    # PCI=0x03, SID=0x7F, rejected PID, exception code
    assert obd.decode_frame(0x7E8, bytes([0x03, 0x7F, 0x0D, 0x11, 0, 0, 0, 0])) is None


def test_unknown_pid_is_ignored():
    assert obd.decode_frame(0x7E8, _sf(0x41, 0x99, 0x01)) is None


def test_multi_frame_is_not_decoded():
    # PCI 0x10 = first frame of a multi-frame message
    assert obd.decode_frame(0x7E8, bytes([0x10, 0x0A, 0x41, 0x0C, 0x1B, 0x58, 0, 0])) is None


def test_truncated_frame_does_not_raise():
    assert obd.decode_frame(0x7E8, bytes([0x04, 0x41, 0x0C])) is None
    assert obd.decode_frame(0x7E8, b"") is None
    assert obd.decode_frame(0x7E8, bytes([0x04])) is None


def test_pci_length_is_respected():
    # PCI claims 2 data bytes (SID + PID) but RPM needs 2 payload bytes
    assert obd.decode_frame(0x7E8, bytes([0x02, 0x41, 0x0C, 0x1B, 0x58, 0, 0, 0])) is None
