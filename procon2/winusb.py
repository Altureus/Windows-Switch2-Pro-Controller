#!/usr/bin/env python3
r"""
winusb.py -- native USB-bulk "wake" for the Switch 2 Pro Controller.

The controller boots ASLEEP ("If_Hid"): it enumerates but emits NO HID input
reports until it is woken over its WinUSB vendor interface (MI_01). The wake
cannot go through HID (those init bytes aren't valid HID reports -> err 87); it
must be a USB bulk transfer, exactly what the browser tool ProCon2Tool does over
WebUSB. MI_01 is bound to the WINUSB driver, so we can do the same natively.

Pure ctypes against winusb.dll (reuses hid.py's SetupDi/kernel32 plumbing). Zero
third-party dependencies.

    import winusb
    winusb.wake()      # returns True if the init sequence was sent

The device-interface GUID below comes from the registry:
  HKLM\...\USB\VID_057E&PID_2069&MI_01\<inst>\Device Parameters\DeviceInterfaceGUID
"""
import ctypes as C
import time
from ctypes import wintypes as W

import hid  # reuse SetupDi + kernel32 + GUID/structs/constants

winusb = C.WinDLL("winusb", use_last_error=True)

WINUSB_IFACE_GUID = "{6F13725E-EF0E-4FD3-AE5F-B2DE989EC825}"

# ProCon2Tool init sequence, sent over the bulk OUT pipe of MI_01.
# INIT_0x03's own comment in ProCon2Tool: "Starts HID output at 4ms intervals."
WAKE_SEQUENCE = [
    bytes([0x03, 0x91, 0x00, 0x0d, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00,
           0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
    bytes([0x07, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x16, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    bytes([0x03, 0x91, 0x00, 0x0a, 0x00, 0x04, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00]),
    bytes([0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x01,
           0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
]

ERROR_IO_PENDING = 997
USBD_PIPE_TYPE_BULK = 2


class USB_INTERFACE_DESCRIPTOR(C.Structure):
    _fields_ = [
        ("bLength", C.c_ubyte), ("bDescriptorType", C.c_ubyte),
        ("bInterfaceNumber", C.c_ubyte), ("bAlternateSetting", C.c_ubyte),
        ("bNumEndpoints", C.c_ubyte), ("bInterfaceClass", C.c_ubyte),
        ("bInterfaceSubClass", C.c_ubyte), ("bInterfaceProtocol", C.c_ubyte),
        ("iInterface", C.c_ubyte),
    ]


class WINUSB_PIPE_INFORMATION(C.Structure):
    _fields_ = [
        ("PipeType", C.c_int), ("PipeId", C.c_ubyte),
        ("MaximumPacketSize", C.c_ushort), ("Interval", C.c_ubyte),
    ]


winusb.WinUsb_Initialize.argtypes = [W.HANDLE, C.POINTER(C.c_void_p)]
winusb.WinUsb_Initialize.restype = W.BOOL
winusb.WinUsb_Free.argtypes = [C.c_void_p]
winusb.WinUsb_Free.restype = W.BOOL
winusb.WinUsb_QueryInterfaceSettings.argtypes = [
    C.c_void_p, C.c_ubyte, C.POINTER(USB_INTERFACE_DESCRIPTOR)]
winusb.WinUsb_QueryInterfaceSettings.restype = W.BOOL
winusb.WinUsb_QueryPipe.argtypes = [
    C.c_void_p, C.c_ubyte, C.c_ubyte, C.POINTER(WINUSB_PIPE_INFORMATION)]
winusb.WinUsb_QueryPipe.restype = W.BOOL
winusb.WinUsb_WritePipe.argtypes = [
    C.c_void_p, C.c_ubyte, C.c_void_p, W.ULONG, C.POINTER(W.ULONG), C.c_void_p]
winusb.WinUsb_WritePipe.restype = W.BOOL
winusb.WinUsb_GetOverlappedResult.argtypes = [
    C.c_void_p, C.POINTER(hid.OVERLAPPED), C.POINTER(W.ULONG), W.BOOL]
winusb.WinUsb_GetOverlappedResult.restype = W.BOOL
winusb.WinUsb_AbortPipe.argtypes = [C.c_void_p, C.c_ubyte]
winusb.WinUsb_AbortPipe.restype = W.BOOL


def _guid(s):
    s = s.strip("{}")
    p = s.split("-")
    g = hid.GUID()
    g.Data1 = int(p[0], 16)
    g.Data2 = int(p[1], 16)
    g.Data3 = int(p[2], 16)
    d = bytes.fromhex(p[3] + p[4])
    for i in range(8):
        g.Data4[i] = d[i]
    return g


def _find_path(guid_str, vid="057e", pid="2069"):
    guid = _guid(guid_str)
    h = hid.setupapi.SetupDiGetClassDevsW(
        C.byref(guid), None, None, hid.DIGCF_PRESENT | hid.DIGCF_DEVICEINTERFACE)
    if h == hid.INVALID_HANDLE_VALUE or h is None:
        return None
    try:
        i = 0
        while True:
            iface = hid.SP_DEVICE_INTERFACE_DATA()
            iface.cbSize = C.sizeof(hid.SP_DEVICE_INTERFACE_DATA)
            if not hid.setupapi.SetupDiEnumDeviceInterfaces(
                    h, None, C.byref(guid), i, C.byref(iface)):
                break
            i += 1
            detail = hid.SP_DEVICE_INTERFACE_DETAIL_DATA_W()
            detail.cbSize = 8 if C.sizeof(C.c_void_p) == 8 else 6
            if hid.setupapi.SetupDiGetDeviceInterfaceDetailW(
                    h, C.byref(iface), C.byref(detail), C.sizeof(detail), None, None):
                path = detail.DevicePath
                low = path.lower()
                if f"vid_{vid}" in low and f"pid_{pid}" in low:
                    return path
    finally:
        hid.setupapi.SetupDiDestroyDeviceInfoList(h)
    return None


def _write_pipe(usb, pipe_id, data, timeout_ms=1000):
    buf = (C.c_ubyte * len(data)).from_buffer_copy(data)
    written = W.ULONG(0)
    ev = hid.kernel32.CreateEventW(None, True, False, None)
    ov = hid.OVERLAPPED()
    ov.hEvent = ev
    try:
        ok = winusb.WinUsb_WritePipe(usb, pipe_id, buf, len(data),
                                     C.byref(written), C.byref(ov))
        if not ok:
            if C.get_last_error() != ERROR_IO_PENDING:
                return False, 0
            if hid.kernel32.WaitForSingleObject(ev, timeout_ms) != hid.WAIT_OBJECT_0:
                # timed out: abort the pipe and reap, so the bulk transfer can't
                # write into buf/ov after this frame's locals are reclaimed.
                winusb.WinUsb_AbortPipe(usb, pipe_id)
                winusb.WinUsb_GetOverlappedResult(usb, C.byref(ov), C.byref(written), True)
                return False, 0
            if not winusb.WinUsb_GetOverlappedResult(usb, C.byref(ov),
                                                     C.byref(written), False):
                return False, 0
        return True, written.value
    finally:
        hid.kernel32.CloseHandle(ev)


def find_bulk_out(usb, verbose=False):
    idesc = USB_INTERFACE_DESCRIPTOR()
    if not winusb.WinUsb_QueryInterfaceSettings(usb, 0, C.byref(idesc)):
        return None
    for pidx in range(idesc.bNumEndpoints):
        pipe = WINUSB_PIPE_INFORMATION()
        if winusb.WinUsb_QueryPipe(usb, 0, pidx, C.byref(pipe)):
            kind = {0: "ctrl", 1: "iso", 2: "bulk", 3: "intr"}.get(pipe.PipeType, "?")
            d = "IN" if pipe.PipeId & 0x80 else "OUT"
            if verbose:
                print(f"[winusb]   pipe {pidx}: id=0x{pipe.PipeId:02x} {kind} {d} "
                      f"max={pipe.MaximumPacketSize}")
            if pipe.PipeType == USBD_PIPE_TYPE_BULK and not (pipe.PipeId & 0x80):
                return pipe.PipeId
    return None


def wake(verbose=False):
    """Send the init sequence over the vendor bulk pipe. Returns True on success."""
    path = _find_path(WINUSB_IFACE_GUID)
    if not path:
        if verbose:
            print("[winusb] vendor (MI_01) interface not found -- is it plugged in?")
        return False
    if verbose:
        print(f"[winusb] opening {path}")
    h = hid.kernel32.CreateFileW(
        path, hid.GENERIC_READ | hid.GENERIC_WRITE,
        hid.FILE_SHARE_READ | hid.FILE_SHARE_WRITE, None,
        hid.OPEN_EXISTING, hid.FILE_FLAG_OVERLAPPED, None)
    if h == hid.INVALID_HANDLE_VALUE or h is None:
        if verbose:
            print(f"[winusb] CreateFile failed (err {C.get_last_error()})")
        return False
    usb = C.c_void_p()
    try:
        if not winusb.WinUsb_Initialize(h, C.byref(usb)):
            if verbose:
                print(f"[winusb] WinUsb_Initialize failed (err {C.get_last_error()})")
            return False
        pipe = find_bulk_out(usb, verbose)
        if pipe is None:
            if verbose:
                print("[winusb] no bulk OUT pipe found")
            return False
        if verbose:
            print(f"[winusb] bulk OUT pipe = 0x{pipe:02x}; sending {len(WAKE_SEQUENCE)} cmds")
        all_ok = True
        for i, cmd in enumerate(WAKE_SEQUENCE):
            ok, n = _write_pipe(usb, pipe, cmd)
            all_ok = all_ok and ok
            if verbose:
                print(f"[winusb]   cmd{i} ({len(cmd)}B): {'OK' if ok else 'FAIL'} "
                      f"wrote {n}" + ("" if ok else f" (err {C.get_last_error()})"))
            time.sleep(0.02)
        return all_ok
    finally:
        try:
            winusb.WinUsb_Free(usb)
        except Exception:
            pass
        hid.kernel32.CloseHandle(h)


# ---------------------------------------------------------------------------
# Rumble / haptics  (NOT YET IMPLEMENTED -- see the safety note)
# ---------------------------------------------------------------------------
# Transport is solved: we can already write to the bulk OUT pipe (0x02). What's
# missing is the exact "play rumble" PACKET FORMAT for the Switch 2 Pro, which is
# UNDOCUMENTED as of mid-2026. Every public tool (ProCon2Tool, ikz87/NSW2-
# controller-enabler, SDL3) only *enables* haptics during init via
#   ENABLE_HAPTICS = 03 91 00 0A 00 04 00 00 09 00 00 00
# -- none of them sends a play-with-amplitude command.
#
# What IS known:
#   * Vendor command shape: [subcmd, 0x91, 0x00, seq, 0x00, datalen, 0x00, 0x00, data...]
#   * Rumble is HD-rumble style: per actuator 2 bytes High-Band + 2 bytes Low-Band
#     encoding (HF frequency + LF amplitude), Switch-1 lineage. Neutral ~ 00 01 40 40.
#   * ProCon2Tool has a working "play test haptic" feature (HID, report id ~0x02).
#
# !! SAFETY !! HandHeldLegend warns that real maximum amplitude values can DAMAGE
# the linear actuators. So we do NOT guess commands here -- a wrong packet could
# physically harm the controller. Implement this ONLY from a known-good source:
#   1. Capture the exact bytes ProCon2Tool sends on "play test haptic" (USBPcap/
#      Wireshark, or Chrome WebUSB logging), or
#   2. A published Switch-2 rumble spec / a real gameplay USB capture.
# Then fill in send_rumble() with that verified packet + safe amplitude clamping.
def send_rumble(large_motor, small_motor):
    """Forward a rumble (each 0..255) to the controller. NOT IMPLEMENTED -- the
    haptic packet format is undocumented and guessing risks actuator damage.
    Returns False until a verified, safe command is wired in (see notes above)."""
    return False


if __name__ == "__main__":
    print("[winusb] attempting native wake...")
    ok = wake(verbose=True)
    print(f"[winusb] wake sent: {ok}")
    # verify the controller now streams HID
    time.sleep(0.3)
    d = hid.find_device()
    if d:
        hh = hid.open_for_read(d["path"])
        n = 0
        for _ in range(40):
            if hid.read_report(hh, d["in_len"] or 64, 200):
                n += 1
        hid.close(hh)
        print(f"[winusb] HID reports after wake: {n}  "
              f"({'STREAMING -- wake works!' if n else 'still asleep :('})")
    else:
        print("[winusb] controller HID interface not found")
