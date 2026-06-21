#!/usr/bin/env python3
r"""
selftest_vigem.py -- prove the virtual Xbox 360 pad works end to end.

Creates a ViGEm X360 pad, writes known button/stick/trigger states, then reads
them back through the Windows XInput API (XInput1_4.dll) -- the same API Dolphin
and games use. If the values round-trip, the whole OUTPUT half of the bridge is
verified on this machine, independent of the controller mapping.

Run:  python procon2/selftest_vigem.py
"""
import ctypes as C
import sys
import time
from ctypes import wintypes as W

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from vigem import X360Pad, Btn  # noqa: E402


# ---- XInput -----------------------------------------------------------------
class XINPUT_GAMEPAD(C.Structure):
    _fields_ = [
        ("wButtons", W.WORD),
        ("bLeftTrigger", W.BYTE),
        ("bRightTrigger", W.BYTE),
        ("sThumbLX", C.c_short),
        ("sThumbLY", C.c_short),
        ("sThumbRX", C.c_short),
        ("sThumbRY", C.c_short),
    ]


class XINPUT_STATE(C.Structure):
    _fields_ = [("dwPacketNumber", W.DWORD), ("Gamepad", XINPUT_GAMEPAD)]


def load_xinput():
    for name in ("XInput1_4.dll", "xinput1_3.dll", "XInput9_1_0.dll"):
        try:
            dll = C.WinDLL(name)
        except OSError:
            continue
        dll.XInputGetState.argtypes = [W.DWORD, C.POINTER(XINPUT_STATE)]
        dll.XInputGetState.restype = W.DWORD
        return name, dll
    raise OSError("No XInput DLL found")


ERROR_SUCCESS = 0


def connected_slots(dll):
    out = set()
    st = XINPUT_STATE()
    for i in range(4):
        if dll.XInputGetState(i, C.byref(st)) == ERROR_SUCCESS:
            out.add(i)
    return out


def read_slot(dll, i):
    st = XINPUT_STATE()
    if dll.XInputGetState(i, C.byref(st)) != ERROR_SUCCESS:
        return None
    g = st.Gamepad
    return {
        "buttons": g.wButtons & 0xFFFF,
        "lt": g.bLeftTrigger & 0xFF,
        "rt": g.bRightTrigger & 0xFF,
        "lx": g.sThumbLX, "ly": g.sThumbLY,
        "rx": g.sThumbRX, "ry": g.sThumbRY,
    }


def main():
    xi_name, xi = load_xinput()
    print(f"[selftest] XInput: {xi_name}")

    before = connected_slots(xi)
    print(f"[selftest] XInput slots connected BEFORE: {sorted(before)}")

    pad = X360Pad()
    print(f"[selftest] created ViGEm X360 pad (target index {pad.xinput_index()})")
    pad.update()  # neutral, so it registers as connected

    # find our slot: the newly-connected one
    slot = None
    for _ in range(60):  # up to ~3s
        time.sleep(0.05)
        now = connected_slots(xi)
        new = now - before
        if new:
            slot = sorted(new)[0]
            break
    if slot is None:
        # maybe the LED index is directly usable
        idx = pad.xinput_index()
        if idx is not None and read_slot(xi, idx) is not None:
            slot = idx
    if slot is None:
        print("[selftest] FAIL: virtual pad did not appear as an XInput device.")
        pad.close()
        return 1
    print(f"[selftest] virtual pad is XInput slot {slot}\n")

    # ---- round-trip test vectors -------------------------------------------
    vectors = [
        ("A only", lambda p: (p.set_button(Btn.A, True),),
         {"buttons": Btn.A}),
        ("B + Y", lambda p: (p.set_button(Btn.B, True), p.set_button(Btn.Y, True)),
         {"buttons": Btn.B | Btn.Y}),
        ("D-pad up + Start", lambda p: (p.set_button(Btn.DPAD_UP, True),
                                        p.set_button(Btn.START, True)),
         {"buttons": Btn.DPAD_UP | Btn.START}),
        ("LStick full right", lambda p: (p.set_stick_left(1.0, 0.0),),
         {"lx": 32767, "ly": 0}),
        ("LStick full up", lambda p: (p.set_stick_left(0.0, 1.0),),
         {"lx": 0, "ly": 32767}),
        ("RStick down-left", lambda p: (p.set_stick_right(-1.0, -1.0),),
         {"rx": -32768, "ry": -32768}),
        ("Triggers LT=128 RT=255", lambda p: (p.set_trigger_left(128 / 255),
                                              p.set_trigger_right(1.0)),
         {"lt": 128, "rt": 255}),
    ]

    passes = 0
    for name, apply_fn, expect in vectors:
        pad.reset()
        apply_fn(pad)
        pad.update()
        time.sleep(0.06)
        got = read_slot(xi, slot)
        if got is None:
            print(f"  [FAIL] {name}: slot read returned None")
            continue
        ok = all(got.get(k) == v for k, v in expect.items())
        passes += ok
        detail = ", ".join(f"{k}={got.get(k)}(exp {v})" for k, v in expect.items())
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<24} {detail}")

    pad.reset()
    pad.update()
    pad.close()

    total = len(vectors)
    print(f"\n[selftest] {passes}/{total} round-trip checks passed.")
    if passes == total:
        print("[selftest] OUTPUT HALF VERIFIED: ViGEm -> XInput works perfectly.")
        return 0
    print("[selftest] some checks failed -- see above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
