#!/usr/bin/env python3
r"""
vigem.py -- pure-ctypes wrapper around ViGEmClient.dll for a virtual Xbox 360 pad.

The ViGEmBus *driver* must be installed (it is on this machine:
"Nefarius Virtual Gamepad Emulation Bus"). This module loads the bundled
user-mode client DLL (vendor/ViGEmClient.dll, extracted from vgamepad's sdist)
and exposes a small X360Pad class. Zero third-party Python dependencies -- works
on any CPython including 3.14, no compiler needed.

Typical use:
    from vigem import X360Pad, Btn
    with X360Pad() as pad:
        pad.set_button(Btn.A, True)
        pad.set_stick_left(0.5, -0.25)   # floats in [-1, 1]
        pad.update()
"""
import ctypes as C
import os
import sys

# ---------------------------------------------------------------------------
# Locate + load the client DLL (arch-matched to the running Python)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ARCH = "x64" if C.sizeof(C.c_void_p) == 8 else "x86"


def _find_dll():
    cands = [
        os.path.join(_HERE, "vendor", "ViGEmClient.dll"),          # canonical (x64)
        os.path.join(_HERE, "vendor", f"ViGEmClient.{_ARCH}.dll"),  # arch-specific
    ]
    for p in cands:
        if os.path.isfile(p):
            # x64 Python must use the x64 dll; the canonical copy IS x64.
            if p.endswith("ViGEmClient.dll") and _ARCH != "x64":
                continue
            return p
    raise FileNotFoundError(
        "ViGEmClient.dll not found in vendor/. Run vendor/_fetch_vigem.py first."
    )


# ---------------------------------------------------------------------------
# Types & constants from ViGEmClient.h
# ---------------------------------------------------------------------------
VIGEM_ERROR_NONE = 0x20000000
_ERR = {
    0x20000000: "NONE",
    0xE0000001: "BUS_NOT_FOUND",
    0xE0000002: "NO_FREE_SLOT",
    0xE0000003: "INVALID_TARGET",
    0xE0000004: "REMOVAL_FAILED",
    0xE0000005: "ALREADY_CONNECTED",
    0xE0000006: "TARGET_UNINITIALIZED",
    0xE0000007: "TARGET_NOT_PLUGGED_IN",
    0xE0000008: "BUS_VERSION_MISMATCH",
    0xE0000009: "BUS_ACCESS_FAILED",
    0xE0000010: "CALLBACK_ALREADY_REGISTERED",
    0xE0000011: "CALLBACK_NOT_FOUND",
    0xE0000012: "BUS_ALREADY_CONNECTED",
    0xE0000013: "BUS_INVALID_HANDLE",
    0xE0000014: "XUSB_USERINDEX_OUT_OF_RANGE",
    0xE0000015: "INVALID_PARAMETER",
    0xE0000016: "NOT_SUPPORTED",
    0xE0000017: "WINAPI",
    0xE0000018: "TIMED_OUT",
    0xE0000019: "IS_DISPOSING",
}


def _err_name(code):
    return _ERR.get(code & 0xFFFFFFFF, f"0x{code & 0xFFFFFFFF:08X}")


class XUSB_REPORT(C.Structure):
    _fields_ = [
        ("wButtons", C.c_ushort),
        ("bLeftTrigger", C.c_ubyte),
        ("bRightTrigger", C.c_ubyte),
        ("sThumbLX", C.c_short),
        ("sThumbLY", C.c_short),
        ("sThumbRX", C.c_short),
        ("sThumbRY", C.c_short),
    ]


class Btn:
    """XUSB_BUTTON bit flags (wButtons)."""
    DPAD_UP = 0x0001
    DPAD_DOWN = 0x0002
    DPAD_LEFT = 0x0004
    DPAD_RIGHT = 0x0008
    START = 0x0010          # "+"  / Start
    BACK = 0x0020           # "-"  / Back
    LEFT_THUMB = 0x0040     # L3
    RIGHT_THUMB = 0x0080    # R3
    LEFT_SHOULDER = 0x0100  # L
    RIGHT_SHOULDER = 0x0200  # R
    GUIDE = 0x0400          # Home (Xbox guide)
    A = 0x1000
    B = 0x2000
    X = 0x4000
    Y = 0x8000


class ViGEmError(RuntimeError):
    pass


# X360 rumble/notification callback:
#   void cb(client, target, large_motor, small_motor, led_number, user_data)
NOTIFY_FUNC = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p,
                          C.c_ubyte, C.c_ubyte, C.c_ubyte, C.c_void_p)


class _Lib:
    """Lazily-bound singleton around ViGEmClient.dll."""
    _inst = None

    def __init__(self):
        path = _find_dll()
        if _ARCH != "x64" and path.endswith("ViGEmClient.dll"):
            path = os.path.join(_HERE, "vendor", "ViGEmClient.x86.dll")
        self.path = path
        # x64 has a single calling convention; CDLL is correct there.
        self.dll = C.CDLL(path)
        d = self.dll
        d.vigem_alloc.restype = C.c_void_p
        d.vigem_alloc.argtypes = []
        d.vigem_free.restype = None
        d.vigem_free.argtypes = [C.c_void_p]
        d.vigem_connect.restype = C.c_uint
        d.vigem_connect.argtypes = [C.c_void_p]
        d.vigem_disconnect.restype = None
        d.vigem_disconnect.argtypes = [C.c_void_p]
        d.vigem_target_x360_alloc.restype = C.c_void_p
        d.vigem_target_x360_alloc.argtypes = []
        d.vigem_target_free.restype = None
        d.vigem_target_free.argtypes = [C.c_void_p]
        d.vigem_target_add.restype = C.c_uint
        d.vigem_target_add.argtypes = [C.c_void_p, C.c_void_p]
        d.vigem_target_remove.restype = C.c_uint
        d.vigem_target_remove.argtypes = [C.c_void_p, C.c_void_p]
        d.vigem_target_x360_update.restype = C.c_uint
        d.vigem_target_x360_update.argtypes = [C.c_void_p, C.c_void_p, XUSB_REPORT]
        # optional: index query (useful for XInput round-trip verification)
        if hasattr(d, "vigem_target_get_index"):
            d.vigem_target_get_index.restype = C.c_ulong
            d.vigem_target_get_index.argtypes = [C.c_void_p]
        if hasattr(d, "vigem_target_x360_register_notification"):
            d.vigem_target_x360_register_notification.restype = C.c_uint
            d.vigem_target_x360_register_notification.argtypes = [
                C.c_void_p, C.c_void_p, NOTIFY_FUNC, C.c_void_p]
        if hasattr(d, "vigem_target_x360_unregister_notification"):
            d.vigem_target_x360_unregister_notification.restype = None
            d.vigem_target_x360_unregister_notification.argtypes = [C.c_void_p]

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = _Lib()
        return cls._inst


def _clamp_axis(f):
    """float in [-1,1] -> signed 16-bit [-32768, 32767]."""
    if f <= -1.0:
        return -32768
    if f >= 1.0:
        return 32767
    return int(round(f * 32767.0))


def _clamp_trigger(f):
    """float in [0,1] -> [0,255]."""
    if f <= 0.0:
        return 0
    if f >= 1.0:
        return 255
    return int(round(f * 255.0))


class X360Pad:
    """A single virtual Xbox 360 controller backed by ViGEmBus."""

    def __init__(self):
        self._lib = _Lib.get()
        d = self._lib.dll
        self._client = d.vigem_alloc()
        if not self._client:
            raise ViGEmError("vigem_alloc returned NULL")
        rc = d.vigem_connect(self._client)
        if rc != VIGEM_ERROR_NONE:
            d.vigem_free(self._client)
            self._client = None
            raise ViGEmError(f"vigem_connect failed: {_err_name(rc)} "
                             "(is the ViGEmBus driver installed/running?)")
        self._target = d.vigem_target_x360_alloc()
        if not self._target:
            d.vigem_disconnect(self._client)
            d.vigem_free(self._client)
            self._client = None
            raise ViGEmError("vigem_target_x360_alloc returned NULL")
        rc = d.vigem_target_add(self._client, self._target)
        if rc != VIGEM_ERROR_NONE:
            self._teardown()
            raise ViGEmError(f"vigem_target_add failed: {_err_name(rc)}")
        self._report = XUSB_REPORT()
        self.rumble = (0, 0)      # latest (large_motor, small_motor) from the game
        self._notify_cb = None

    # ---- state setters ---------------------------------------------------
    def set_button(self, mask, pressed=True):
        if pressed:
            self._report.wButtons |= mask
        else:
            self._report.wButtons &= ~mask & 0xFFFF

    def set_buttons_raw(self, value):
        self._report.wButtons = value & 0xFFFF

    def set_trigger_left(self, f):
        self._report.bLeftTrigger = _clamp_trigger(f)

    def set_trigger_right(self, f):
        self._report.bRightTrigger = _clamp_trigger(f)

    def set_stick_left(self, x, y):
        self._report.sThumbLX = _clamp_axis(x)
        self._report.sThumbLY = _clamp_axis(y)

    def set_stick_right(self, x, y):
        self._report.sThumbRX = _clamp_axis(x)
        self._report.sThumbRY = _clamp_axis(y)

    def set_left_raw(self, x, y):
        self._report.sThumbLX = max(-32768, min(32767, int(x)))
        self._report.sThumbLY = max(-32768, min(32767, int(y)))

    def set_right_raw(self, x, y):
        self._report.sThumbRX = max(-32768, min(32767, int(x)))
        self._report.sThumbRY = max(-32768, min(32767, int(y)))

    def reset(self):
        self._report = XUSB_REPORT()

    # ---- commit ----------------------------------------------------------
    def update(self):
        rc = self._lib.dll.vigem_target_x360_update(
            self._client, self._target, self._report
        )
        if rc != VIGEM_ERROR_NONE:
            raise ViGEmError(f"vigem_target_x360_update failed: {_err_name(rc)}")

    def xinput_index(self):
        """LED/user index ViGEm assigned (maps to the XInput slot), or None."""
        d = self._lib.dll
        if hasattr(d, "vigem_target_get_index"):
            return int(d.vigem_target_get_index(self._target))
        return None

    # ---- rumble (game -> us) --------------------------------------------
    def enable_rumble(self, handler=None):
        """Register for rumble that the consuming app (e.g. Dolphin) sends to this
        pad. The latest (large_motor, small_motor) -- each 0..255 -- is stored on
        self.rumble; if handler is given it's also called handler(large, small).
        Returns True if registered. The callback runs on a ViGEm thread, so keep
        handler fast (just stash values; do the work from your own loop)."""
        d = self._lib.dll
        if not hasattr(d, "vigem_target_x360_register_notification"):
            return False

        def _cb(client, target, large, small, led, user):
            self.rumble = (large, small)
            if handler is not None:
                try:
                    handler(large, small)
                except Exception:
                    pass

        self._notify_cb = NOTIFY_FUNC(_cb)  # keep a ref so it isn't GC'd
        rc = d.vigem_target_x360_register_notification(
            self._client, self._target, self._notify_cb, None)
        return rc == VIGEM_ERROR_NONE

    # ---- lifecycle -------------------------------------------------------
    def _teardown(self):
        d = self._lib.dll
        if getattr(self, "_target", None):
            # Stop rumble callbacks BEFORE freeing the target, and keep the Python
            # callback object alive until AFTER the free, so an in-flight callback
            # from ViGEm's thread can't hit a freed target or a GC'd trampoline.
            if hasattr(d, "vigem_target_x360_unregister_notification"):
                try:
                    d.vigem_target_x360_unregister_notification(self._target)
                except Exception:
                    pass
            try:
                d.vigem_target_remove(self._client, self._target)
            except Exception:
                pass
            d.vigem_target_free(self._target)
            self._target = None
            self._notify_cb = None
        if getattr(self, "_client", None):
            d.vigem_disconnect(self._client)
            d.vigem_free(self._client)
            self._client = None

    def close(self):
        self._teardown()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self._teardown()
        except Exception:
            pass


if __name__ == "__main__":
    # minimal smoke test: create the pad, assert it added, hold A briefly.
    import time
    print(f"[vigem] loading {_Lib.get().path}")
    pad = X360Pad()
    idx = pad.xinput_index()
    print(f"[vigem] virtual X360 pad added. xinput_index={idx}")
    print("[vigem] pressing A + left stick right for 2s...")
    pad.set_button(Btn.A, True)
    pad.set_stick_left(1.0, 0.0)
    pad.update()
    time.sleep(2.0)
    pad.reset()
    pad.update()
    pad.close()
    print("[vigem] removed. OK.")
