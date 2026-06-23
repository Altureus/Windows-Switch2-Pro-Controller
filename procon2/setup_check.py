#!/usr/bin/env python3
r"""
setup_check.py -- verify the prerequisites are in place and point you at anything
missing. Run it (or "Setup Check.bat") before the first launch.

Checks: Python, the bundled ViGEmClient.dll, the ViGEmBus *driver* (the one piece
you must install yourself), and whether the controller is plugged in.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OK = "[ OK ]"
NO = "[FAIL]"
SKIP = "[ -- ]"
VIGEMBUS_URL = "https://github.com/nefarius/ViGEmBus/releases/latest"
PYTHON_URL = "https://www.python.org/downloads/"


def main():
    print("=" * 58)
    print(" Switch 2 Pro -> Xbox pad bridge -- setup check")
    print("=" * 58)
    problems = []

    # 1. Python (it's running, so it's installed -- just report it)
    v = sys.version_info
    bits = "64-bit" if sys.maxsize > 2**32 else "32-bit"
    print(f"{OK} Python {v.major}.{v.minor}.{v.micro} ({bits})")
    if sys.maxsize <= 2**32:
        print("       ! 32-bit Python -- 64-bit is recommended.")

    if sys.platform != "win32":
        print(f"{NO} This tool is Windows-only.")
        problems.append("not running on Windows")

    # 2. Bundled ViGEmClient.dll (ships with the repo)
    dll = os.path.join(HERE, "vendor", "ViGEmClient.dll")
    if os.path.isfile(dll):
        print(f"{OK} ViGEmClient.dll present (vendor/)")
    else:
        print(f"{NO} ViGEmClient.dll missing -- run: python vendor/_fetch_vigem.py")
        problems.append("ViGEmClient.dll missing")

    # 3. ViGEmBus DRIVER -- the kernel driver you must install. Test by actually
    #    creating (then removing) a virtual pad.
    if os.path.isfile(dll):
        try:
            from vigem import X360Pad
            X360Pad().close()
            print(f"{OK} ViGEmBus driver installed and working")
        except Exception as e:
            print(f"{NO} ViGEmBus driver not working ({type(e).__name__})")
            drivers = os.path.join(os.path.dirname(HERE), "drivers")
            inst = next((f for f in os.listdir(drivers)
                         if f.lower().startswith("vigembus") and f.lower().endswith(".exe")),
                        None) if os.path.isdir(drivers) else None
            if inst:
                print(f"       Install the bundled driver: drivers\\{inst}  (double-click, needs admin)")
            print(f"       Or get the latest: {VIGEMBUS_URL}")
            problems.append("ViGEmBus driver not installed")

    # 4. Controller present? (informational -- not required to pass)
    try:
        import hid
        if hid.find_device():
            print(f"{OK} Switch 2 Pro Controller detected (USB 057E:2069)")
        else:
            print(f"{SKIP} Controller not detected -- plug it in via USB when ready.")
    except Exception:
        print(f"{SKIP} Could not check for the controller.")

    print("-" * 58)
    if problems:
        print("Setup INCOMPLETE -- fix the [FAIL] item(s) above, then re-run:")
        for p in problems:
            print("   - " + p)
        return 1
    print("All set! Run  Start (Auto-detect).bat , then point Dolphin at the XInput pad.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
