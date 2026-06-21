#!/usr/bin/env python3
r"""
selftest_bridge.py -- prove the WHOLE pipeline end to end, in ~3 seconds.

    real Switch 2 Pro (HID)  ->  mapping.parse  ->  ViGEm X360 pad  ->  XInput

No button presses required: a rising frame counter proves the controller is live
and being read; the XInput read-back proves the parsed state reaches a real
driver-level pad. (Press things while it runs to see buttons/sticks move.)

Run:  python procon2/selftest_bridge.py [seconds]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hid          # noqa: E402
import mapping      # noqa: E402
from vigem import X360Pad  # noqa: E402
from bridge import feed    # noqa: E402
from selftest_vigem import load_xinput, read_slot, connected_slots  # noqa: E402


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0

    dev = hid.find_device()
    if not dev:
        print("[selftest] No Switch 2 Pro (057E:2069) found. Plug it in via USB.")
        return 1
    print(f"[selftest] controller: '{(dev['product'] or '').strip()}' "
          f"in_len={dev['in_len']}")
    h = hid.open_for_read(dev["path"], write=False)
    if not h:
        print("[selftest] could not open controller for reading.")
        return 1
    in_len = dev["in_len"] or mapping.REPORT_LEN

    xi_name, xi = load_xinput()
    before = connected_slots(xi)
    pad = X360Pad()
    pad.update()
    slot = None
    for _ in range(60):
        time.sleep(0.05)
        new = connected_slots(xi) - before
        if new:
            slot = sorted(new)[0]
            break
    print(f"[selftest] XInput={xi_name}  virtual pad slot={slot}\n")

    frames = 0
    first_counter = last_counter = None
    last_state = None
    nonzero_btn_seen = False
    stick_moved = False
    t_end = time.time() + seconds
    while time.time() < t_end:
        rep = hid.read_report(h, in_len, 200)
        if rep is None:
            continue
        if not mapping.is_target_report(rep):
            continue
        state = mapping.parse(rep)
        feed(pad, state)
        frames += 1
        last_state = state
        if first_counter is None:
            first_counter = state.counter
        last_counter = state.counter
        if state.buttons:
            nonzero_btn_seen = True
        if abs(state.lx) > 0.3 or abs(state.ly) > 0.3 or \
           abs(state.rx) > 0.3 or abs(state.ry) > 0.3:
            stick_moved = True

    hid.close(h)
    rb = read_slot(xi, slot) if slot is not None else None
    elapsed = seconds
    fps = frames / elapsed if elapsed else 0

    print("[selftest] ===== RESULT =====")
    print(f"  frames read           : {frames}  (~{fps:.0f}/s)")
    print(f"  frame counter         : {first_counter} -> {last_counter} "
          f"({'advancing OK' if frames > 1 and first_counter != last_counter else 'NOT advancing'})")
    print(f"  last parsed state     : {last_state}")
    print(f"  buttons seen pressed  : {'yes' if nonzero_btn_seen else 'no (none pressed)'}")
    print(f"  sticks moved >0.3     : {'yes' if stick_moved else 'no (at rest)'}")
    print(f"  XInput read-back slot : {slot}")
    print(f"  XInput read-back data : {rb}")

    pad.reset(); pad.update(); pad.close()

    ok = frames > 1 and slot is not None and rb is not None
    print(f"\n[selftest] {'PIPELINE LIVE: controller -> parse -> ViGEm -> XInput works.' if ok else 'FAIL -- see above.'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
