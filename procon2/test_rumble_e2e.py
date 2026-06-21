#!/usr/bin/env python3
r"""
test_rumble_e2e.py -- self-contained FULL-CHAIN rumble test (~3s).

Builds the whole pipeline in one process: virtual pad + rumble callback, wakes the
controller, opens it for HID output, then vibrates its OWN pad via XInput (exactly
what Dolphin does) and forwards the resulting rumble to the controller's haptics.
You should feel the real controller buzz -- proving Dolphin -> pad -> controller.

Close ProCon2Tool first. Hold the controller.
"""
import os
import sys
import time
import ctypes as C
from ctypes import wintypes as W

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hid       # noqa: E402
import winusb    # noqa: E402
import haptics   # noqa: E402
import xinput    # noqa: E402
from vigem import X360Pad  # noqa: E402


class VIB(C.Structure):
    _fields_ = [("l", W.WORD), ("r", W.WORD)]


def main():
    xi = xinput.load()
    dll = xi[1]
    dll.XInputSetState.argtypes = [W.DWORD, C.POINTER(VIB)]
    dll.XInputSetState.restype = W.DWORD

    print("[e2e] waking controller + opening for output...")
    try:
        winusb.wake()
    except Exception as e:
        print("[e2e] wake error (continuing):", e)
    dev = hid.find_device()
    if not dev:
        print("[e2e] controller not found (close ProCon2Tool / plug in).")
        return 1
    h = hid.open_for_read(dev["path"], write=True)
    if not h:
        print("[e2e] could not open controller for writing.")
        return 1

    before = xinput.connected_slots(xi)
    pad = X360Pad()
    pad.update()
    pad.enable_rumble()
    slot = None
    for _ in range(40):
        new = xinput.connected_slots(xi) - before
        if new:
            slot = sorted(new)[0]
            break
        time.sleep(0.05)
    if slot is None:
        print("[e2e] couldn't find our pad's XInput slot.")
        pad.close(); hid.close(h)
        return 1

    print(f"[e2e] pad on slot {slot}. Sending Dolphin-style vibration for 3s -- "
          "HOLD THE CONTROLLER and feel it buzz...")
    dll.XInputSetState(slot, C.byref(VIB(0xC000, 0xC000)))  # ~75% -> HIGH payload

    cnt = 0
    sent = 0
    t_end = time.time() + 3.0
    while time.time() < t_end:
        amp = max(pad.rumble)
        if amp > 0:
            hid.write_report(h, haptics.build_frame(cnt, haptics.level_for(amp)))
            cnt = (cnt + 1) & 0x0F
            sent += 1
        time.sleep(0.012)

    dll.XInputSetState(slot, C.byref(VIB(0, 0)))            # stop vibration
    for _ in range(5):                                      # flush OFF frames
        hid.write_report(h, haptics.build_frame(cnt, haptics.OFF))
        cnt = (cnt + 1) & 0x0F
        time.sleep(0.012)

    pad.reset(); pad.update(); pad.close()
    hid.close(h)
    print(f"[e2e] done. pad.rumble last seen = {pad.rumble}, haptic frames forwarded = {sent}")
    print("[e2e] >>> Did the controller buzz for ~3 seconds? <<<")
    return 0


if __name__ == "__main__":
    sys.exit(main())
