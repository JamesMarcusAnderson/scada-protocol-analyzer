#!/usr/bin/env python3
import argparse
import json
import sys
import time
from datetime import datetime, timezone

from . import modbus, obd

try:
    import can as pycan
except ImportError:
    pycan = None


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def modbus_scan(args):
    result = modbus.scan(args.host, args.port, args.unit, args.start, args.count)
    print(json.dumps(result, indent=2))
    return 0 if "error" not in result else 1


def can_listen(args):
    if pycan is None:
        print("python-can not installed", file=sys.stderr)
        return 2
    bus = pycan.interface.Bus(channel=args.interface, bustype="socketcan")
    t0 = time.time()
    with open(args.out, "w") as out:
        out.write("timestamp,can_id,pid,name,value,unit\n")
        while time.time() - t0 < args.seconds:
            msg = bus.recv(1.0)
            if msg is None:
                continue
            decoded = obd.decode_frame(msg.arbitration_id, bytes(msg.data))
            if decoded:
                ts = _now()
                out.write(f"{ts},{msg.arbitration_id:03X},{decoded['pid']},"
                          f"{decoded['name']},{decoded['value']},{decoded['unit']}\n")
                print(f"{ts}  {decoded['name']}={decoded['value']} {decoded['unit']}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("modbus")
    m.add_argument("--host", required=True)
    m.add_argument("--port", type=int, default=502)
    m.add_argument("--unit", type=int, default=1)
    m.add_argument("--start", type=int, default=0)
    m.add_argument("--count", type=int, default=10)
    m.set_defaults(fn=modbus_scan)

    c = sub.add_parser("can")
    c.add_argument("--interface", default="can0")
    c.add_argument("--seconds", type=int, default=30)
    c.add_argument("--out", default="can-log.csv")
    c.set_defaults(fn=can_listen)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
