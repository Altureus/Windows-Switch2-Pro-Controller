#!/usr/bin/env python3
r"""
hid.py -- minimal pure-ctypes Win32 HID layer (enumerate / open / read).

Extracted from the proven procon2_probe.py so the bridge and probe share one
code path. Zero third-party dependencies; Windows-only.
"""
import ctypes as C
import sys
from ctypes import wintypes as W

if sys.platform != "win32":
    raise RuntimeError("hid.py is Windows-only (uses the Win32 HID API).")

setupapi = C.WinDLL("setupapi", use_last_error=True)
hid = C.WinDLL("hid", use_last_error=True)
kernel32 = C.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = C.c_size_t
NTSTATUS = C.c_long


class GUID(C.Structure):
    _fields_ = [("Data1", C.c_ulong), ("Data2", C.c_ushort),
                ("Data3", C.c_ushort), ("Data4", C.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", W.DWORD), ("Reserved", ULONG_PTR)]


class SP_DEVICE_INTERFACE_DETAIL_DATA_W(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("DevicePath", W.WCHAR * 1024)]


class HIDD_ATTRIBUTES(C.Structure):
    _fields_ = [("Size", W.ULONG), ("VendorID", C.c_ushort),
                ("ProductID", C.c_ushort), ("VersionNumber", C.c_ushort)]


class HIDP_CAPS(C.Structure):
    _fields_ = [
        ("Usage", C.c_ushort), ("UsagePage", C.c_ushort),
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
    _fields_ = [("Internal", ULONG_PTR), ("InternalHigh", ULONG_PTR),
                ("Offset", W.DWORD), ("OffsetHigh", W.DWORD),
                ("hEvent", W.HANDLE)]


hid.HidD_GetHidGuid.argtypes = [C.POINTER(GUID)]
hid.HidD_GetHidGuid.restype = None
hid.HidD_GetAttributes.argtypes = [W.HANDLE, C.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = W.BOOLEAN
hid.HidD_GetProductString.argtypes = [W.HANDLE, C.c_void_p, W.ULONG]
hid.HidD_GetProductString.restype = W.BOOLEAN
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
    W.HANDLE, C.c_void_p, C.POINTER(GUID), W.DWORD, C.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiEnumDeviceInterfaces.restype = W.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    W.HANDLE, C.POINTER(SP_DEVICE_INTERFACE_DATA),
    C.POINTER(SP_DEVICE_INTERFACE_DETAIL_DATA_W), W.DWORD, C.POINTER(W.DWORD), C.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = W.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [W.HANDLE]
setupapi.SetupDiDestroyDeviceInfoList.restype = W.BOOL

kernel32.CreateFileW.argtypes = [
    W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]
kernel32.CreateFileW.restype = W.HANDLE
kernel32.CloseHandle.argtypes = [W.HANDLE]
kernel32.CloseHandle.restype = W.BOOL
kernel32.ReadFile.argtypes = [
    W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(OVERLAPPED)]
kernel32.ReadFile.restype = W.BOOL
kernel32.WriteFile.argtypes = [
    W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(OVERLAPPED)]
kernel32.WriteFile.restype = W.BOOL
kernel32.CreateEventW.argtypes = [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR]
kernel32.CreateEventW.restype = W.HANDLE
kernel32.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
kernel32.WaitForSingleObject.restype = W.DWORD
kernel32.GetOverlappedResult.argtypes = [
    W.HANDLE, C.POINTER(OVERLAPPED), C.POINTER(W.DWORD), W.BOOL]
kernel32.GetOverlappedResult.restype = W.BOOL
kernel32.CancelIo.argtypes = [W.HANDLE]
kernel32.CancelIo.restype = W.BOOL

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
HIDP_STATUS_SUCCESS = 0x00110000

VENDOR_NINTENDO = 0x057E
PID_PROCON2 = 0x2069


def _read_str(getter, handle):
    buf = C.create_unicode_buffer(256)
    if getter(handle, buf, C.sizeof(buf)):
        return buf.value
    return ""


def enumerate_hid():
    """Return a list of dicts describing every present HID interface."""
    guid = GUID()
    hid.HidD_GetHidGuid(C.byref(guid))
    hdev = setupapi.SetupDiGetClassDevsW(
        C.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if hdev == INVALID_HANDLE_VALUE or hdev is None:
        raise OSError(f"SetupDiGetClassDevs failed: {C.get_last_error()}")
    results = []
    try:
        idx = 0
        while True:
            iface = SP_DEVICE_INTERFACE_DATA()
            iface.cbSize = C.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(
                    hdev, None, C.byref(guid), idx, C.byref(iface)):
                break
            idx += 1
            detail = SP_DEVICE_INTERFACE_DETAIL_DATA_W()
            detail.cbSize = 8 if C.sizeof(C.c_void_p) == 8 else 6
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                    hdev, C.byref(iface), C.byref(detail), C.sizeof(detail), None, None):
                continue
            path = detail.DevicePath
            info = {"path": path, "vid": None, "pid": None, "usage_page": None,
                    "usage": None, "in_len": None, "out_len": None, "product": ""}
            h = kernel32.CreateFileW(
                path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
            if h != INVALID_HANDLE_VALUE and h is not None:
                try:
                    attrs = HIDD_ATTRIBUTES()
                    attrs.Size = C.sizeof(HIDD_ATTRIBUTES)
                    if hid.HidD_GetAttributes(h, C.byref(attrs)):
                        info["vid"] = attrs.VendorID
                        info["pid"] = attrs.ProductID
                    info["product"] = _read_str(hid.HidD_GetProductString, h)
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


def find_device(vid=VENDOR_NINTENDO, pid=PID_PROCON2):
    """Return the first matching interface dict, or None."""
    for d in enumerate_hid():
        if d["vid"] == vid and d["pid"] == pid:
            return d
    return None


def open_for_read(path, write=False):
    """Open a HID path for overlapped reads (and optionally writes). Returns
    a handle int, or None on failure."""
    access = GENERIC_READ | (GENERIC_WRITE if write else 0)
    h = kernel32.CreateFileW(
        path, access, FILE_SHARE_READ | FILE_SHARE_WRITE, None,
        OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if h == INVALID_HANDLE_VALUE or h is None:
        return None
    return h


def read_report(handle, length, timeout_ms):
    """Overlapped read with timeout. Returns bytes, or None on timeout/error."""
    ev = kernel32.CreateEventW(None, True, False, None)
    ov = OVERLAPPED()
    ov.hEvent = ev
    buf = (C.c_ubyte * length)()
    nread = W.DWORD(0)
    try:
        ok = kernel32.ReadFile(handle, buf, length, C.byref(nread), C.byref(ov))
        if ok:
            return bytes(buf[: nread.value])   # completed synchronously
        if C.get_last_error() != ERROR_IO_PENDING:
            return None
        if kernel32.WaitForSingleObject(ev, timeout_ms) != WAIT_OBJECT_0:
            # timed out: cancel AND reap it, so the driver can't write into
            # buf/ov after this frame's locals are reclaimed.
            kernel32.CancelIo(handle)
            kernel32.GetOverlappedResult(handle, C.byref(ov), C.byref(nread), True)
            return None
        if not kernel32.GetOverlappedResult(handle, C.byref(ov), C.byref(nread), False):
            return None
        return bytes(buf[: nread.value])
    finally:
        kernel32.CloseHandle(ev)


def write_report(handle, data, timeout_ms=200):
    """Overlapped HID output-report write. data[0] must be the report id.
    Returns True on success. Handle must be opened with write=True."""
    ev = kernel32.CreateEventW(None, True, False, None)
    ov = OVERLAPPED()
    ov.hEvent = ev
    buf = (C.c_ubyte * len(data)).from_buffer_copy(bytes(data))
    nwr = W.DWORD(0)
    try:
        ok = kernel32.WriteFile(handle, buf, len(data), C.byref(nwr), C.byref(ov))
        if not ok:
            if C.get_last_error() != ERROR_IO_PENDING:
                return False
            if kernel32.WaitForSingleObject(ev, timeout_ms) != WAIT_OBJECT_0:
                kernel32.CancelIo(handle)
                kernel32.GetOverlappedResult(handle, C.byref(ov), C.byref(nwr), True)
                return False
            if not kernel32.GetOverlappedResult(handle, C.byref(ov), C.byref(nwr), False):
                return False
        return True
    finally:
        kernel32.CloseHandle(ev)


def close(handle):
    if handle:
        kernel32.CloseHandle(handle)
