#!/usr/bin/env python3
r"""
bridge.py -- persistent Switch 2 Pro Controller -> virtual Xbox 360 pad bridge.

Reads the controller's 64-byte HID input reports, parses Nintendo's custom
layout (mapping.py), and republishes the state as a real driver-level Xbox 360
pad via ViGEmBus (vigem.py) so Dolphin / any game sees a standard XInput pad.

PERSISTENCE GUARANTEE: the virtual pad is created ONCE and held for the entire
life of this process. Nothing -- a controller unplug, a USB power hiccup, a bad
HID read, a transient ViGEm error -- removes the pad or stops the bridge. Only
YOU closing the window (Ctrl+C / close) ends it. While the controller is briefly
away the pad just reads neutral, then input resumes automatically with no need to
touch Dolphin. (As a last resort, if the pad driver itself dies, the bridge
recreates it and tells you to hit Refresh in Dolphin.)

Usage
-----
  python procon2/bridge.py                 # run the bridge
  python procon2/bridge.py --debug         # also print parsed state live
  python procon2/bridge.py --debug-hz 20   # debug print rate (default 10/s)

Stop with Ctrl+C (or just close the window).
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hid          # noqa: E402
import mapping      # noqa: E402
import xinput       # noqa: E402
import winusb       # noqa: E402
import haptics      # noqa: E402
from vigem import X360Pad, Btn  # noqa: E402

# Nintendo logical button -> Xbox 360 (XUSB) output. ZL/ZR are digital on Switch
# -> mapped to FULL analog triggers (what GameCube emulation expects). GL/GR (rear
# paddles) -> Right Shoulder = GameCube Z. CAPTURE / C and the stick-clicks (L3/R3)
# have no native X360 slot in this layout and are unmapped.
BUTTON_TO_XUSB = {
    "A": Btn.A,
    "B": Btn.B,
    "X": Btn.X,
    "Y": Btn.Y,
    "UP": Btn.DPAD_UP,
    "DOWN": Btn.DPAD_DOWN,
    "LEFT": Btn.DPAD_LEFT,
    "RIGHT": Btn.DPAD_RIGHT,
    "L": Btn.LEFT_SHOULDER,
    "R": Btn.RIGHT_SHOULDER,
    "MINUS": Btn.BACK,
    "PLUS": Btn.START,
    # GL/GR rear paddles -> Right Shoulder, which the Dolphin profile binds to
    # GameCube Z -- so the paddles act as extra Z buttons (alongside the R bumper).
    "GL": Btn.RIGHT_SHOULDER,
    "GR": Btn.RIGHT_SHOULDER,
    "HOME": Btn.GUIDE,
}
TRIGGER_LEFT = "ZL"    # digital -> LT full
TRIGGER_RIGHT = "ZR"   # digital -> RT full

RECONNECT_WAIT = 0.5   # seconds between reconnect attempts
READ_TIMEOUT_MS = 200  # per-report read timeout (returns instantly on data)
MAX_MISSES = 8         # consecutive timeouts (~1.6 s) before re-attaching
RECREATE_AFTER = 250   # consecutive feed failures (~1 s) before recreating pad


def feed(pad, state):
    pad.reset()
    btns = state.buttons
    for nin, xbtn in BUTTON_TO_XUSB.items():
        if nin in btns:
            pad.set_button(xbtn, True)
    if TRIGGER_LEFT in btns:
        pad.set_trigger_left(1.0)
    if TRIGGER_RIGHT in btns:
        pad.set_trigger_right(1.0)
    pad.set_stick_left(state.lx, state.ly)
    pad.set_stick_right(state.rx, state.ry)
    pad.update()


def _detect_slot(xi, before):
    for _ in range(40):
        new = xinput.connected_slots(xi) - before
        if new:
            return sorted(new)[0]
        time.sleep(0.05)
    return None


DOLPHIN_GCPAD_INI = os.path.join(
    os.environ.get("APPDATA", ""), "Dolphin Emulator", "Config", "GCPadNew.ini")


def _sync_dolphin_slot(slot, port="GCPad1"):
    """Slot-drift guard: re-point Dolphin's Port-1 device at the XInput slot this
    pad actually took, so the controller keeps working even if the slot shifts
    (e.g. a stale pad grabbed the usual one). Only re-points an EXISTING XInput
    binding -- never overrides a deliberately-set non-XInput device -- and only
    writes when it actually changed. Best-effort; a no-op if Dolphin isn't found.
    (If Dolphin is already open it'll re-read on next launch / Refresh.)"""
    if slot is None or not os.path.isfile(DOLPHIN_GCPAD_INI):
        return
    want = f"XInput/{slot}/Gamepad"
    try:
        with open(DOLPHIN_GCPAD_INI, "r", encoding="utf-8") as f:
            lines = f.readlines()
        section = None
        changed = False
        for i, ln in enumerate(lines):
            s = ln.strip()
            if s.startswith("[") and s.endswith("]"):
                section = s[1:-1]
            elif section == port and s.lower().replace(" ", "").startswith("device="):
                key, _, val = ln.partition("=")
                if val.strip().startswith("XInput/") and val.strip() != want:
                    lines[i] = f"{key.rstrip()} = {want}\n"
                    changed = True
                break
        if changed:
            with open(DOLPHIN_GCPAD_INI, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"[bridge] slot-drift guard: re-pointed Dolphin {port} -> {want}.")
    except Exception:
        pass


def run(debug=False, debug_hz=10.0, dolphin_sync=True):
    print("[bridge] creating virtual Xbox 360 pad via ViGEmBus...")
    xi = xinput.load()
    before = xinput.connected_slots(xi)
    pad = X360Pad()
    pad.update()
    # Capture rumble Dolphin sends to the pad (stored on pad.rumble); the read loop
    # forwards it to the controller's haptics (see haptics.py).
    pad.enable_rumble()
    slot = _detect_slot(xi, before)
    if dolphin_sync:
        _sync_dolphin_slot(slot)   # keep Dolphin's Port 1 pointed at our actual slot
    print("[bridge] virtual Xbox 360 pad is LIVE and will stay up until you close this.")
    if slot is not None:
        print(f"[bridge] >>> In Dolphin, choose device  XInput/{slot}/Gamepad  <<<")
        if before:
            print(f"[bridge]     (slots {sorted(before)} were already taken by another "
                  "Xbox-style device -- don't pick those.)")
        print("[bridge]     If it's not in Dolphin's list, click REFRESH there first.")
    else:
        print("[bridge] (couldn't detect the XInput slot; in Dolphin pick the device "
              "that APPEARS when this bridge is running, after clicking Refresh.)")
    print("[bridge] Auto-reconnects through any controller hiccup. Ctrl+C / close to stop.\n")

    dbg_interval = 1.0 / debug_hz if debug_hz > 0 else 0
    last_dbg = 0.0
    attached = False
    total_frames = 0
    t_fps = time.time()
    fps_frames = 0
    feed_fails = 0
    rumble_cnt = 0
    last_rumble_send = 0.0
    rumble_off_until = 0.0
    RUMBLE_INTERVAL = 1.0 / 80.0   # stream haptic frames at ~80 Hz while active

    def safe_neutral():
        try:
            pad.reset()
            pad.update()
        except Exception:
            pass

    try:
        while True:
            try:
                # ---- make sure we're attached to the controller ----
                try:
                    dev = hid.find_device()
                except Exception:
                    dev = None
                if not dev:
                    if attached:
                        print("[bridge] controller away -- holding the pad, waiting for it...")
                        safe_neutral()
                        attached = False
                    time.sleep(RECONNECT_WAIT)
                    continue

                # The controller boots/returns ASLEEP ("If_Hid") and streams no
                # HID until woken over its WinUSB vendor interface. Wake it on
                # every (re)attach -- harmless if it's already awake.
                if not attached:
                    try:
                        if winusb.wake():
                            print("[bridge] woke controller (WinUSB) -- HID output started.")
                    except Exception:
                        pass

                try:
                    h = hid.open_for_read(dev["path"], write=True)   # write -> rumble
                    if not h:
                        h = hid.open_for_read(dev["path"], write=False)  # input-only fallback
                except Exception:
                    h = None
                if not h:
                    time.sleep(RECONNECT_WAIT)
                    continue

                in_len = dev["in_len"] or mapping.REPORT_LEN
                if not attached:
                    name = (dev["product"] or "").strip() or "Pro Controller 2"
                    print(f"[bridge] attached to '{name}' (report len {in_len}). "
                          "Translating -> Xbox 360 pad.")
                    attached = True
                misses = 0

                # ---- read loop ----
                while True:
                    try:
                        rep = hid.read_report(h, in_len, READ_TIMEOUT_MS)
                    except Exception:
                        rep = None
                    if rep is None:
                        misses += 1
                        if misses >= MAX_MISSES:
                            break  # controller hiccup -> reattach (pad stays up)
                        continue
                    misses = 0

                    # a single bad frame or ViGEm hiccup must NOT kill the bridge
                    try:
                        if not mapping.is_target_report(rep):
                            continue
                        state = mapping.parse(rep)
                        feed(pad, state)
                        feed_fails = 0
                    except Exception as e:
                        feed_fails += 1
                        if feed_fails == 1:
                            print(f"[bridge] transient error ({type(e).__name__}) -- continuing.")
                        if feed_fails >= RECREATE_AFTER:
                            print("[bridge] pad driver unresponsive -- recreating it. "
                                  "If input doesn't resume, click Refresh in Dolphin.")
                            try:
                                new_pad = X360Pad()      # allocate BEFORE closing
                                new_pad.update()
                                new_pad.enable_rumble()  # re-arm rumble on the new pad
                                try:
                                    pad.close()
                                except Exception:
                                    pass
                                pad = new_pad
                            except Exception:
                                time.sleep(0.5)          # keep old pad; retry next cycle
                            feed_fails = 0
                        continue

                    total_frames += 1
                    fps_frames += 1
                    now = time.time()

                    # ---- forward rumble: Dolphin -> controller haptics ----
                    # Stream safe captured haptic frames at ~80 Hz while active;
                    # keep sending OFF briefly after it stops so the buzz ends cleanly.
                    if (now - last_rumble_send) >= RUMBLE_INTERVAL:
                        amp = max(pad.rumble)
                        if amp > 0:
                            hid.write_report(h, haptics.build_frame(
                                rumble_cnt, haptics.level_for(amp)))
                            rumble_cnt = (rumble_cnt + 1) & 0x0F
                            last_rumble_send = now
                            rumble_off_until = now + 0.12
                        elif now < rumble_off_until:
                            hid.write_report(h, haptics.build_frame(rumble_cnt, haptics.OFF))
                            rumble_cnt = (rumble_cnt + 1) & 0x0F
                            last_rumble_send = now

                    if debug and dbg_interval and (now - last_dbg) >= dbg_interval:
                        last_dbg = now
                        rl, rs = pad.rumble
                        rtag = f"  rumble=({rl},{rs})" if (rl or rs) else ""
                        print(f"  {state}{rtag}")
                    if (now - t_fps) >= 5.0:
                        if not debug:
                            print(f"[bridge] live: {fps_frames / (now - t_fps):5.0f} "
                                  f"reports/s ({total_frames} total)")
                        t_fps = now
                        fps_frames = 0

                try:
                    hid.close(h)
                except Exception:
                    pass
                safe_neutral()   # hold the pad (neutral) across the hiccup
                attached = False
                time.sleep(RECONNECT_WAIT)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                # absolute backstop: only Ctrl+C ends the loop, never an error
                print(f"[bridge] recovered from unexpected error: {type(e).__name__}: {e}")
                safe_neutral()
                attached = False
                time.sleep(RECONNECT_WAIT)
    except KeyboardInterrupt:
        print("\n[bridge] stopping (Ctrl+C).")
    finally:
        safe_neutral()
        try:
            pad.close()
        except Exception:
            pass
        print("[bridge] virtual pad removed. Bye.")


def main():
    ap = argparse.ArgumentParser(description="Switch 2 Pro -> Xbox 360 pad bridge")
    ap.add_argument("--debug", action="store_true",
                    help="print parsed controller state live (verify mapping)")
    ap.add_argument("--debug-hz", type=float, default=10.0,
                    help="debug print rate per second (default 10)")
    ap.add_argument("--no-dolphin-sync", action="store_true",
                    help="don't auto-point Dolphin's Port 1 at this session's XInput slot")
    args = ap.parse_args()
    run(debug=args.debug, debug_hz=args.debug_hz, dolphin_sync=not args.no_dolphin_sync)


if __name__ == "__main__":
    main()
