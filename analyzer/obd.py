"""OBD-II PID decoding for ISO 15765-2 (ISO-TP) single frames on CAN.

Frame layout for a response on 0x7E8..0x7EF:

    byte 0   PCI     0x0N = single frame carrying N data bytes
    byte 1   SID     0x41 = response to a mode-01 request
    byte 2   PID
    byte 3.. payload A, B, C, D
"""

OBD_PIDS = {
    0x0C: ("RPM",           lambda b: ((b[0] << 8) | b[1]) / 4.0,   "rpm"),
    0x0D: ("Speed",         lambda b: b[0],                          "km/h"),
    0x05: ("Coolant Temp",  lambda b: b[0] - 40,                     "C"),
    0x2F: ("Fuel Level",    lambda b: b[0] * 100.0 / 255.0,          "%"),
    0x11: ("Throttle",      lambda b: b[0] * 100.0 / 255.0,          "%"),
}

RESPONSE_SID = 0x41
SF_PCI_MASK = 0xF0
SF_PCI_VALUE = 0x00
MAX_SF_DATA = 7


def decode_frame(can_id, data):
    """Decode one CAN frame. Returns a dict, or None if it is not a
    single-frame mode-01 response for a PID we know."""
    if (can_id & 0x7F8) != 0x7E8:
        return None
    if len(data) < 3:
        return None
    if (data[0] & SF_PCI_MASK) != SF_PCI_VALUE:
        return None                     # multi-frame / flow control: not handled
    sf_len = data[0] & 0x0F
    if sf_len < 2 or sf_len > MAX_SF_DATA:
        return None
    if data[1] != RESPONSE_SID:
        return None                     # 0x7F = negative response, etc.
    pid = data[2]
    if pid not in OBD_PIDS:
        return None
    name, fn, unit = OBD_PIDS[pid]
    payload = data[3:3 + sf_len - 2]
    try:
        return {"pid": f"0x{pid:02X}", "name": name, "value": fn(payload), "unit": unit}
    except IndexError:
        return None                     # frame shorter than the PID needs
