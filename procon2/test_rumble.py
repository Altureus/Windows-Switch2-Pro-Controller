#!/usr/bin/env python3
r"""
test_rumble.py -- safe rumble smoke test.

Streams a SAFE captured haptic value (from ProCon2Tool's own test) to the
controller for ~1.5s, then stops. Confirms our HID output path works and that the
rumble feels right before wiring it into the bridge.

Close ProCon2Tool first (so the controller's interfaces are free), then run.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hid       # noqa: E402
import winusb    # noqa: E402
import haptics   # noqa: E402


def main():
    print("[test] waking controller (in case it's asleep)...")
    try:
        winusb.wake()
    except Exception as e:
        print("[test] wake error (continuing):", e)

    dev = hid.find_device()
    if not dev:
        print("[test] controller not found -- plug it in (and close ProCon2Tool).")
        return 1
    h = hid.open_for_read(dev["path"], write=True)
    if not h:
        print("[test] could not open the controller for writing -- is ProCon2Tool "
              "still holding it? Close that tab and retry.")
        return 1

    print("[test] buzzing ~1.5s with a SAFE value (haptics.MED) from ProCon2Tool's "
          "own test waveform...")
    cnt = 0
    sent = 0
    failed = 0
    t_end = time.time() + 1.5
    while time.time() < t_end:
        ok = hid.write_report(h, haptics.build_frame(cnt, haptics.MED))
        sent += 1
        failed += (0 if ok else 1)
        cnt = (cnt + 1) & 0x0F
        time.sleep(0.012)   # ~80 Hz
    for _ in range(4):      # stop
        hid.write_report(h, haptics.build_frame(cnt, haptics.OFF))
        cnt = (cnt + 1) & 0x0F
        time.sleep(0.012)
    hid.close(h)

    print(f"[test] done. frames sent={sent}  write-failures={failed}")
    if failed:
        print("[test] WRITES FAILED -- the HID output path was rejected; the report "
              "id / endpoint may differ. Tell me this number.")
    else:
        print("[test] writes all succeeded.")
    print("[test] >>> Did the controller RUMBLE, and was it GENTLE (not violent)? <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())
