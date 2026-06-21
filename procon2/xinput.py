#!/usr/bin/env python3
r"""
xinput.py -- tiny read-only XInput helper (slot enumeration + state read).

Used to tell the user exactly which XInput slot the virtual pad occupies, so
they pick the right device in Dolphin.
"""
import ctypes as C
from ctypes import wintypes as W


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


ERROR_SUCCESS = 0


def load():
    """Return (dll_name, dll) or None if XInput is unavailable."""
    for name in ("XInput1_4.dll", "xinput1_3.dll", "XInput9_1_0.dll"):
        try:
            dll = C.WinDLL(name)
        except OSError:
            continue
        dll.XInputGetState.argtypes = [W.DWORD, C.POINTER(XINPUT_STATE)]
        dll.XInputGetState.restype = W.DWORD
        return name, dll
    return None


def connected_slots(handle):
    """handle = the (name, dll) tuple from load(). Returns set of slots 0..3."""
    if not handle:
        return set()
    _, dll = handle
    out = set()
    st = XINPUT_STATE()
    for i in range(4):
        if dll.XInputGetState(i, C.byref(st)) == ERROR_SUCCESS:
            out.add(i)
    return out


def read_slot(handle, i):
    if not handle:
        return None
    _, dll = handle
    st = XINPUT_STATE()
    if dll.XInputGetState(i, C.byref(st)) != ERROR_SUCCESS:
        return None
    g = st.Gamepad
    return {
        "buttons": g.wButtons & 0xFFFF,
        "lt": g.bLeftTrigger & 0xFF, "rt": g.bRightTrigger & 0xFF,
        "lx": g.sThumbLX, "ly": g.sThumbLY,
        "rx": g.sThumbRX, "ry": g.sThumbRY,
    }
