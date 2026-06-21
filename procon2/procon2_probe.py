#!/usr/bin/env python3
r"""
procon2_probe.py  --  Switch 2 Pro Controller HID prober (pure ctypes, no deps)

Purpose
-------
Reverse-engineering aid for the Nintendo Switch 2 Pro Controller (USB 057E:2069)
and friends (Joy-Con 2 L/R, NSO GameCube).  It does three things:

  1. Enumerates every HID interface on the machine and flags Nintendo ones.
  2. Opens the target controller's HID interface(s) and streams the raw INPUT
     reports as hex, highlighting which bytes change as you press buttons /
     move sticks  ->  this is how we crack the button/stick byte layout.
  3. (optional, experimental) Tries to "wake" the controller by sending the
     ProCon2Tool init sequence as HID output reports.  NOTE: ProCon2Tool sends
     these over a USB *bulk* endpoint, not HID, so this may be rejected -- the
     point is to learn empirically whether the HID path is accepted.

Zero third-party dependencies. Works on any CPython (incl. 3.14) on Windows.

Usage
-----
  python procon2_probe.py --list            # list all HID devices, flag Nintendo
  python procon2_probe.py                    # find Pro Controller 2, stream reports
  python procon2_probe.py --pid 0x2069 --seconds 20
  python procon2_probe.py --wake             # also try the HID-output wake sequence

Recommended capture workflow
----------------------------
  A) Plug in the controller, run `python procon2_probe.py` COLD. Note whether
     anything streams.
  B) "Wake" it with ProCon2Tool in the browser, leave that tab open, then run
     `python procon2_probe.py` again and press one button at a time. Paste the
     output back so we can map every button/axis.
"""

import argparse
import ctypes as C
import sys
import time
from ctypes import wintypes as W

if sys.platform != "win32":
    sys.exit("This probe is Windows-only (uses the Win32 HID API).")

# ---------------------------------------------------------------------------
# Win32 library handles
# ---------------------------------------------------------------------------
setupapi = C.WinDLL("setupapi", use_last_error=True)
hid = C.WinDLL("hid", use_last_error=True)
kernel32 = C.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = C.c_size_t
NTSTATUS = C.c_long

# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------
class GUID(C.Structure):
    _fields_ = [
        ("Data1", C.c_ulong),
        ("Data2", C.c_ushort),
        ("Data3", C.c_ushort),
        ("Data4", C.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(C.Structure):
    _fields_ = [
        ("cbSize", W.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", W.DWORD),
        ("Reserved", ULONG_PTR),
    ]


class SP_DEVICE_INTERFACE_DETAIL_DATA_W(C.Structure):
    # Fixed-size path buffer so we avoid the variable-length-struct dance.
    _fields_ = [
        ("cbSize", W.DWORD),
        ("DevicePath", W.WCHAR * 1024),
    ]


class HIDD_ATTRIBUTES(C.Structure):
    _fields_ = [
        ("Size", W.ULONG),
        ("VendorID", C.c_ushort),
        ("ProductID", C.c_ushort),
        ("VersionNumber", C.c_ushort),
    ]


class HIDP_CAPS(C.Structure):
    # Exact layout (32 x USHORT = 64 bytes). HidP_GetCaps fills all of it.
    _fields_ = [
        ("Usage", C.c_ushort),
        ("UsagePage", C.c_ushort),
        ("InputReportByteLength", C.c_ushort),
        ("OutputReportByteLength", C.c_ushort),
        ("FeatureReportByteLength", C.c_ushort),
        ("Reserved", C.c_ushort * 17),
        ("NumberLinkCollectionNodes", C.c_ushort),
        ("NumberInputButtonCaps", C.c_ushort),
        ("NumberInputValueCaps", C.c_ushort),
        ("NumberInputDataIndices", C.c_ushort),
        ("NumberOutputButtonCaps", C.c_ushort),
        ("NumberOutputValueCaps", C.c_ushort),
        ("NumberOutputDataIndices", C.c_ushort),
        ("NumberFeatureButtonCaps", C.c_ushort),
        ("NumberFeatureValueCaps", C.c_ushort),
        ("NumberFeatureDataIndices", C.c_ushort),
    ]


class OVERLAPPED(C.Structure):
    _fields_ = [
        ("Internal", ULONG_PTR),
        ("InternalHigh", ULONG_PTR),
        ("Offset", W.DWORD),
        ("OffsetHigh", W.DWORD),
        ("hEvent", W.HANDLE),
    ]


# ---------------------------------------------------------------------------
# Prototypes
# ---------------------------------------------------------------------------
hid.HidD_GetHidGuid.argtypes = [C.POINTER(GUID)]
hid.HidD_GetHidGuid.restype = None

hid.HidD_GetAttributes.argtypes = [W.HANDLE, C.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = W.BOOLEAN

hid.HidD_GetProductString.argtypes = [W.HANDLE, C.c_void_p, W.ULONG]
hid.HidD_GetProductString.restype = W.BOOLEAN
hid.HidD_GetManufacturerString.argtypes = [W.HANDLE, C.c_void_p, W.ULONG]
hid.HidD_GetManufacturerString.restype = W.BOOLEAN

hid.HidD_GetPreparsedData.argtypes = [W.HANDLE, C.POINTER(C.c_void_p)]
hid.HidD_GetPreparsedData.restype = W.BOOLEAN
hid.HidD_FreePreparsedData.argtypes = [C.c_void_p]
hid.HidD_FreePreparsedData.restype = W.BOOLEAN
hid.HidP_GetCaps.argtypes = [C.c_void_p, C.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = NTSTATUS
hid.HidD_SetOutputReport.argtypes = [W.HANDLE, C.c_void_p, W.ULONG]
hid.HidD_SetOutputReport.restype = W.BOOLEAN

setupapi.SetupDiGetClassDevsW.argtypes = [C.POINTER(GUID), W.LPCWSTR, W.HWND, W.DWORD]
setupapi.SetupDiGetClassDevsW.restype = W.HANDLE
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    W.HANDLE, C.c_void_p, C.POINTER(GUID), W.DWORD, C.POINTER(SP_DEVICE_INTERFACE_DATA)
]
setupapi.SetupDiEnumDeviceInterfaces.restype = W.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    W.HANDLE, C.POINTER(SP_DEVICE_INTERFACE_DATA),
    C.POINTER(SP_DEVICE_INTERFACE_DETAIL_DATA_W), W.DWORD, C.POINTER(W.DWORD), C.c_void_p,
]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = W.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [W.HANDLE]
setupapi.SetupDiDestroyDeviceInfoList.restype = W.BOOL

kernel32.CreateFileW.argtypes = [
    W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE
]
kernel32.CreateFileW.restype = W.HANDLE
kernel32.CloseHandle.argtypes = [W.HANDLE]
kernel32.CloseHandle.restype = W.BOOL
kernel32.ReadFile.argtypes = [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(OVERLAPPED)]
kernel32.ReadFile.restype = W.BOOL
kernel32.CreateEventW.argtypes = [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR]
kernel32.CreateEventW.restype = W.HANDLE
kernel32.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
kernel32.WaitForSingleObject.restype = W.DWORD
kernel32.GetOverlappedResult.argtypes = [W.HANDLE, C.POINTER(OVERLAPPED), C.POINTER(W.DWORD), W.BOOL]
kernel32.GetOverlappedResult.restype = W.BOOL
kernel32.CancelIo.argtypes = [W.HANDLE]
kernel32.CancelIo.restype = W.BOOL

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x01
FILE_SHARE_WRITE = 0x02
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE_VALUE = C.c_void_p(-1).value
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0x0
WAIT_TIMEOUT = 0x102
HIDP_STATUS_SUCCESS = 0x00110000

VENDOR_NINTENDO = 0x057E
KNOWN_PIDS = {
    0x2066: "Joy-Con 2 (R)",
    0x2067: "Joy-Con 2 (L)",
    0x2069: "Pro Controller 2",
    0x2073: "NSO GameCube",
    0x2009: "Switch 1 Pro Controller",
}

# ---------------------------------------------------------------------------
# ProCon2Tool init sequence (sent over USB bulk by the original tool).
# We try them as HID output reports here purely to learn what's accepted.
# Source: HandHeldLegend/handheldlegend.github.io  procon2tool/index.html
# ---------------------------------------------------------------------------
INIT_SEQUENCE = [
    ("INIT_0x03 (starts HID output @4ms)",
     [0x03, 0x91, 0x00, 0x0d, 0x00, 0x08, 0x00, 0x00, 0x01, 0x00,
      0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]),
    ("CMD_0x07", [0x07, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    ("CMD_0x16", [0x16, 0x91, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
    ("ENABLE_HAPTICS",
     [0x03, 0x91, 0x00, 0x0a, 0x00, 0x04, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00]),
    ("SET_PLAYER_LED=1",
     [0x09, 0x91, 0x00, 0x07, 0x00, 0x08, 0x00, 0x00, 0x01,
      0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
]


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------
def _read_hid_string(getter, handle):
    buf = C.create_unicode_buffer(256)
    if getter(handle, buf, C.sizeof(buf)):
        return buf.value
    return ""


def enumerate_hid():
    guid = GUID()
    hid.HidD_GetHidGuid(C.byref(guid))
    hdev = setupapi.SetupDiGetClassDevsW(
        C.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )
    if hdev == INVALID_HANDLE_VALUE or hdev is None:
        raise OSError(f"SetupDiGetClassDevs failed: {C.get_last_error()}")

    results = []
    try:
        idx = 0
        while True:
            iface = SP_DEVICE_INTERFACE_DATA()
            iface.cbSize = C.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(
                hdev, None, C.byref(guid), idx, C.byref(iface)
            ):
                break  # ERROR_NO_MORE_ITEMS
            idx += 1

            detail = SP_DEVICE_INTERFACE_DETAIL_DATA_W()
            # cbSize is the *header* size: 8 on 64-bit, 6 on 32-bit unicode.
            detail.cbSize = 8 if C.sizeof(C.c_void_p) == 8 else 6
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                hdev, C.byref(iface), C.byref(detail), C.sizeof(detail), None, None
            ):
                continue
            path = detail.DevicePath

            info = {"path": path, "vid": None, "pid": None, "usage_page": None,
                    "usage": None, "in_len": None, "out_len": None,
                    "product": "", "manufacturer": ""}

            # Open with 0 access -> works even when system holds the device.
            h = kernel32.CreateFileW(
                path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None
            )
            if h != INVALID_HANDLE_VALUE and h is not None:
                try:
                    attrs = HIDD_ATTRIBUTES()
                    attrs.Size = C.sizeof(HIDD_ATTRIBUTES)
                    if hid.HidD_GetAttributes(h, C.byref(attrs)):
                        info["vid"] = attrs.VendorID
                        info["pid"] = attrs.ProductID
                    info["product"] = _read_hid_string(hid.HidD_GetProductString, h)
                    info["manufacturer"] = _read_hid_string(hid.HidD_GetManufacturerString, h)
                    pp = C.c_void_p()
                    if hid.HidD_GetPreparsedData(h, C.byref(pp)):
                        try:
                            caps = HIDP_CAPS()
                            if hid.HidP_GetCaps(pp, C.byref(caps)) == HIDP_STATUS_SUCCESS:
                                info["usage_page"] = caps.UsagePage
                                info["usage"] = caps.Usage
                                info["in_len"] = caps.InputReportByteLength
                                info["out_len"] = caps.OutputReportByteLength
                        finally:
                            hid.HidD_FreePreparsedData(pp)
                finally:
                    kernel32.CloseHandle(h)
            results.append(info)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return results


def fmt_dev(d):
    vid = f"{d['vid']:04X}" if d["vid"] is not None else "????"
    pid = f"{d['pid']:04X}" if d["pid"] is not None else "????"
    up = f"{d['usage_page']:04X}" if d["usage_page"] is not None else "??"
    us = f"{d['usage']:02X}" if d["usage"] is not None else "??"
    tag = ""
    if d["vid"] == VENDOR_NINTENDO:
        tag = "  <== NINTENDO: " + KNOWN_PIDS.get(d["pid"], "unknown PID")
    name = (d["product"] or "").strip()
    return (f"VID={vid} PID={pid} usagePage={up} usage={us} "
            f"in={d['in_len']} out={d['out_len']}  '{name}'{tag}")


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
def open_for_read(path, write=False):
    access = GENERIC_READ | (GENERIC_WRITE if write else 0)
    h = kernel32.CreateFileW(
        path, access, FILE_SHARE_READ | FILE_SHARE_WRITE, None,
        OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None
    )
    if h == INVALID_HANDLE_VALUE or h is None:
        return None
    return h


def read_report(handle, length, timeout_ms):
    """Overlapped read with timeout. Returns bytes or None on timeout/error."""
    ev = kernel32.CreateEventW(None, True, False, None)
    ov = OVERLAPPED()
    ov.hEvent = ev
    buf = (C.c_ubyte * length)()
    nread = W.DWORD(0)
    try:
        ok = kernel32.ReadFile(handle, buf, length, C.byref(nread), C.byref(ov))
        if not ok:
            err = C.get_last_error()
            if err != ERROR_IO_PENDING:
                return None
        if kernel32.WaitForSingleObject(ev, timeout_ms) != WAIT_OBJECT_0:
            kernel32.CancelIo(handle)
            return None
        if not kernel32.GetOverlappedResult(handle, C.byref(ov), C.byref(nread), False):
            return None
        return bytes(buf[: nread.value])
    finally:
        kernel32.CloseHandle(ev)


def try_wake(path, out_len):
    print("\n[wake] Trying ProCon2Tool init as HID output reports "
          "(experimental -- original tool uses USB bulk, so rejection is expected)...")
    h = open_for_read(path, write=True)
    if h is None:
        print(f"[wake] could not open for write (err {C.get_last_error()}). "
              "Device may be exclusively held.")
        return
    try:
        length = out_len if out_len and out_len > 0 else 64
        for name, data in INIT_SEQUENCE:
            payload = bytes(data) + b"\x00" * (length - len(data)) if len(data) < length else bytes(data[:length])
            buf = (C.c_ubyte * length).from_buffer_copy(payload)
            ok = hid.HidD_SetOutputReport(h, buf, length)
            print(f"[wake]   {'OK ' if ok else 'REJ'}  {name}"
                  f"{'' if ok else f' (err {C.get_last_error()})'}")
            time.sleep(0.01)
    finally:
        kernel32.CloseHandle(h)


def map_mode(path, in_len, calib_seconds=5, press_seconds=120):
    """Guided mapping: learn the IMU noise, then isolate button/stick bytes."""
    length = in_len if in_len and in_len > 0 else 64
    h = open_for_read(path, write=False)
    if h is None:
        print(f"[map] could not open device for reading (err {C.get_last_error()}).")
        return

    try:
        # ---- Phase 1: learn idle noise -----------------------------------
        print(f"\n[map] PHASE 1 ({calib_seconds}s): leave the controller ALONE "
              "(hands off, sticks centered) so I can learn the IMU noise...")
        cols = [list() for _ in range(length)]
        deadline = time.time() + calib_seconds
        frames = 0
        while time.time() < deadline:
            rep = read_report(h, length, 500)
            if rep is None:
                continue
            frames += 1
            for i in range(min(length, len(rep))):
                cols[i].append(rep[i])
        if frames < 20:
            print(f"[map] only {frames} frames -- is the controller awake? Aborting.")
            return

        from collections import Counter
        rest = [Counter(c).most_common(1)[0][0] if c else 0 for c in cols]
        span = [(max(c) - min(c)) if c else 0 for c in cols]
        # Buttons/quiet bytes barely move at idle; IMU bytes swing widely.
        noise = set(i for i in range(length) if span[i] > 4)
        noise.add(1)  # frame counter
        stable = [i for i in range(length) if i not in noise]
        button_bytes = [i for i in stable if rest[i] in (0x00, 0xff)]
        print(f"[map] learned from {frames} frames. "
              f"volatile/IMU bytes: {sorted(noise)}")
        print(f"[map] stable bytes: {stable}")
        print(f"[map] button-bitfield candidates (rest 00/ff): {button_bytes}")

        # ---- Phase 2: capture inputs -------------------------------------
        print("\n[map] PHASE 2: now press ONE button at a time, then sweep each "
              "stick fully. Watch the lines below. Press Ctrl+C when done.\n")
        seen = {}             # offset -> set of values already printed
        bits_seen = {i: 0 for i in button_bytes}
        lo = [255] * length
        hi = [0] * length
        deadline2 = time.time() + press_seconds
        try:
            while time.time() < deadline2:
                rep = read_report(h, length, 500)
                if rep is None:
                    continue
                # track full range for EVERY byte (reveals stick sweeps later)
                for i in range(min(length, len(rep))):
                    v = rep[i]
                    if v < lo[i]:
                        lo[i] = v
                    if v > hi[i]:
                        hi[i] = v
                # clean button watch: only the stable bitfield bytes
                for i in button_bytes:
                    v = rep[i]
                    if v != rest[i]:
                        bits_seen[i] |= (v ^ rest[i])
                        s = seen.setdefault(i, set())
                        if v not in s:
                            s.add(v)
                            diff = v ^ rest[i]
                            setbits = [b for b in range(8) if diff & (1 << b)]
                            print(f"  BUTTON  byte{i:>2}: {rest[i]:02x} -> {v:02x}"
                                  f"   new bit(s) {setbits}")
        except KeyboardInterrupt:
            pass

        # ---- Summary ------------------------------------------------------
        print("\n\n[map] ===== SUMMARY =====")
        changed = [i for i in button_bytes if bits_seen[i]]
        print("BUTTON bytes that changed (these are your real buttons):")
        if changed:
            for i in changed:
                print(f"  byte{i:>2}  rest={rest[i]:02x}  bits ever set: "
                      f"{bits_seen[i]:08b}")
        else:
            print("  (none changed -- did you actually press buttons? "
                  "they should appear at idx 3/4/5)")
        print("\nStick / analog candidates (pre-IMU bytes 2-15 that swung widely):")
        any_stick = False
        for i in range(2, 16):
            if hi[i] - lo[i] > 32:
                any_stick = True
                tag = ("idle-volatile (maybe IMU/timestamp)" if i in noise
                       else "idle-stable (LIKELY REAL STICK)")
                print(f"  byte{i:>2}  rest={rest[i]:02x}  min={lo[i]:02x} "
                      f"max={hi[i]:02x}  span={hi[i] - lo[i]}  [{tag}]")
        if not any_stick:
            print("  (none yet -- sweep each stick fully to its edges)")
        print("\n(IMU region ~idx16-44 deliberately ignored.)")
        print("\n[map] Paste this whole SUMMARY (and the BUTTON lines) back to me.")
    finally:
        kernel32.CloseHandle(h)


def stream(path, in_len, seconds):
    length = in_len if in_len and in_len > 0 else 64
    h = open_for_read(path, write=False)
    if h is None:
        print(f"[read] could not open device for reading (err {C.get_last_error()}).")
        return
    print(f"\n[read] streaming input reports for {seconds}s "
          f"(report length {length}). Press buttons / move sticks now...")
    print("[read] changed bytes vs previous report are marked with ^ underneath.\n")
    last = None
    count = 0
    baseline = None
    changed_mask = set()
    deadline = time.time() + seconds
    try:
        while time.time() < deadline:
            rep = read_report(h, length, 500)
            if rep is None:
                continue
            count += 1
            if baseline is None:
                baseline = rep
            if rep != last:
                hexs = " ".join(f"{b:02x}" for b in rep)
                print(f"#{count:05d}  {hexs}")
                if last is not None and len(last) == len(rep):
                    marks = []
                    for i, (a, b) in enumerate(zip(last, rep)):
                        if a != b:
                            marks.append("^^")
                            changed_mask.add(i)
                        else:
                            marks.append("  ")
                    print(f"        {' '.join(marks)}")
                last = rep
    finally:
        kernel32.CloseHandle(h)
    print(f"\n[read] done. {count} reports captured.")
    if count == 0:
        print("[read] NOTHING streamed -> controller is asleep (still 'If_Hid'). "
              "Wake it first (ProCon2Tool / Steam) then re-run.")
    elif changed_mask:
        idxs = ", ".join(str(i) for i in sorted(changed_mask))
        print(f"[read] byte offsets that changed while you were pressing: {idxs}")
        print("[read] ^ those are our button/stick/dpad bytes. Paste this output back.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Switch 2 Pro Controller HID prober")
    ap.add_argument("--list", action="store_true", help="list all HID devices and exit")
    ap.add_argument("--pid", type=lambda x: int(x, 0), default=0x2069,
                    help="target product id (default 0x2069 = Pro Controller 2)")
    ap.add_argument("--seconds", type=int, default=15, help="seconds to stream (--raw)")
    ap.add_argument("--calib", type=int, default=5, help="map: idle calibration seconds")
    ap.add_argument("--press-seconds", type=int, default=120,
                    help="map: max seconds to capture presses before auto-stop")
    ap.add_argument("--raw", action="store_true",
                    help="firehose: print every changed report (very noisy)")
    ap.add_argument("--wake", action="store_true",
                    help="also try the HID-output wake sequence first")
    args = ap.parse_args()

    devs = enumerate_hid()

    if args.list:
        print(f"Found {len(devs)} HID interfaces:\n")
        for d in sorted(devs, key=lambda x: (x["vid"] or 0, x["pid"] or 0)):
            print("  " + fmt_dev(d))
        nin = [d for d in devs if d["vid"] == VENDOR_NINTENDO]
        print(f"\nNintendo interfaces: {len(nin)}")
        return

    targets = [d for d in devs if d["vid"] == VENDOR_NINTENDO and d["pid"] == args.pid]
    if not targets:
        nin = [d for d in devs if d["vid"] == VENDOR_NINTENDO]
        print(f"No device with VID=057E PID={args.pid:04X} found.")
        if nin:
            print("But these Nintendo devices are present:")
            for d in nin:
                print("  " + fmt_dev(d))
            print("\nTry: python procon2_probe.py --pid 0x<PID_from_above>")
        else:
            print("No Nintendo HID devices at all. Is the controller plugged in via USB?")
            print("Run `python procon2_probe.py --list` to see everything.")
        return

    print(f"Target: VID=057E PID={args.pid:04X}  "
          f"({KNOWN_PIDS.get(args.pid, 'unknown')}) -- {len(targets)} interface(s)")
    for d in targets:
        print("  " + fmt_dev(d))

    for d in targets:
        if args.wake:
            try_wake(d["path"], d["out_len"])
        if args.raw:
            stream(d["path"], d["in_len"], args.seconds)
        else:
            map_mode(d["path"], d["in_len"], args.calib, args.press_seconds)


if __name__ == "__main__":
    main()
