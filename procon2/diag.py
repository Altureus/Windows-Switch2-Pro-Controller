#!/usr/bin/env python3
r"""
diag.py -- bridge + per-press self-check logger.

Same as bridge.py (reads controller -> parses -> feeds a virtual X360 pad) but
ALSO reads its OWN pad back through XInput and logs a line every time the
pressed-button set changes, showing BOTH sides:

    controller=<parsed>   ->   XInput slot N buttons=0x....

If pressing A shows `controller=A -> ... buttons=0x1000`, the whole chain works
at the OS level and the problem is purely inside Dolphin. If the XInput side
stays 0x0000 while the controller side shows the press, feeding is the break.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hid          # noqa: E402
import mapping      # noqa: E402
import xinput       # noqa: E402
from vigem import X360Pad  # noqa: E402
from bridge import feed    # noqa: E402


def main():
    dev = hid.find_device()
    if not dev:
        print("[diag] no controller (057E:2069). Plug it in.", flush=True)
        return 1
    h = hid.open_for_read(dev["path"], write=False)
    in_len = dev["in_len"] or mapping.REPORT_LEN

    xi = xinput.load()
    before = xinput.connected_slots(xi)
    pad = X360Pad()
    pad.update()
    slot = None
    for _ in range(40):
        new = xinput.connected_slots(xi) - before
        if new:
            slot = sorted(new)[0]
            break
        time.sleep(0.05)
    print(f"[diag] virtual pad at XInput slot {slot}. "
          "PRESS A, B, then wiggle both sticks.", flush=True)

    last = None
    try:
        while True:
            rep = hid.read_report(h, in_len, 200)
            if rep is None or not mapping.is_target_report(rep):
                continue
            st = mapping.parse(rep)
            feed(pad, st)
            rb = xinput.read_slot(xi, slot) if slot is not None else None
            parsed = "+".join(sorted(st.buttons)) or "-"
            xib = f"0x{rb['buttons']:04x}" if rb else "?"
            # also flag stick motion
            moved = ""
            if rb and (abs(rb["lx"]) > 9000 or abs(rb["ly"]) > 9000):
                moved += f" Lstick=({rb['lx']:+d},{rb['ly']:+d})"
            if rb and (abs(rb["rx"]) > 9000 or abs(rb["ry"]) > 9000):
                moved += f" Rstick=({rb['rx']:+d},{rb['ry']:+d})"
            r3, r4, r5 = st.raw_btn
            key = (parsed, xib, st.raw_btn, bool(moved))
            if key != last:
                print(f"[diag] controller={parsed:16s} raw=[{r3:02x} {r4:02x} {r5:02x}]"
                      f" -> XInput slot{slot} buttons={xib}{moved}", flush=True)
                last = key
            time.sleep(0.004)
    except KeyboardInterrupt:
        pass
    finally:
        pad.close()


if __name__ == "__main__":
    sys.exit(main())
