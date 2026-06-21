#!/usr/bin/env python3
r"""
map_buttons.py -- definitive, prompted button + stick mapper.

Unlike the freehand probe, this names each control and waits for you to press
exactly that one -- so the resulting map has zero press-order ambiguity. It then
calibrates each stick axis from its real extremes. Writes mapping_data.py, which
mapping.py auto-loads, finishing the bridge.

Run:  python procon2/map_buttons.py

Controls while it runs:
  * just press the control it names; it auto-advances
  * press  s  or  Enter  to SKIP a control (e.g. one your pad lacks)
  * press  q  to quit
"""
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hid          # noqa: E402
import mapping      # noqa: E402

try:
    import msvcrt
except ImportError:
    msvcrt = None

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "mapping_data.py")

# (logical name, friendly prompt)
BUTTON_ORDER = [
    ("A", "the A button"),
    ("B", "the B button"),
    ("X", "the X button"),
    ("Y", "the Y button"),
    ("UP", "D-pad UP"),
    ("DOWN", "D-pad DOWN"),
    ("LEFT", "D-pad LEFT"),
    ("RIGHT", "D-pad RIGHT"),
    ("L", "the L bumper"),
    ("ZL", "the ZL trigger"),
    ("R", "the R bumper"),
    ("ZR", "the ZR trigger"),
    ("MINUS", "the - (Minus) button"),
    ("PLUS", "the + (Plus) button"),
    ("L3", "the LEFT stick CLICK (push it straight down)"),
    ("R3", "the RIGHT stick CLICK"),
    ("HOME", "the HOME button"),
    ("CAPTURE", "the CAPTURE button"),
    ("C", "the C button"),
    ("GL", "the LEFT back button (GL)"),
    ("GR", "the RIGHT back button (GR)"),
]

NOMINAL_CENTER = 2048
STICK_THRESH = 900   # raw deflection from center counted as "at an extreme"


def poll_keys():
    """Return 'skip', 'quit', or None based on any pending keypress."""
    if not msvcrt:
        return None
    hit = None
    while msvcrt.kbhit():
        ch = msvcrt.getwch()
        if ch in ("q", "Q"):
            hit = "quit"
        elif ch in ("s", "S", "\r", "\n"):
            hit = hit or "skip"
    return hit


def calibrate_rest(h, in_len, secs=1.5):
    cols = [Counter() for _ in range(in_len)]
    n = 0
    t_end = time.time() + secs
    while time.time() < t_end:
        rep = hid.read_report(h, in_len, 200)
        if rep is None:
            continue
        n += 1
        for i in range(min(in_len, len(rep))):
            cols[i][rep[i]] += 1
    rest = [c.most_common(1)[0][0] if c else 0 for c in cols]
    return rest, n


def at_rest(rep, rest):
    return all(rep[b] == rest[b] for b in (3, 4, 5))


def detect_button(h, in_len, rest, reverse, name, timeout=30):
    """Return (byte,bit), 'skip', 'quit', or None(timeout)."""
    t_end = time.time() + timeout
    # start from rest
    while time.time() < t_end:
        k = poll_keys()
        if k:
            return k
        rep = hid.read_report(h, in_len, 200)
        if rep and at_rest(rep, rest):
            break
    cand = None
    cnt = 0
    while time.time() < t_end:
        k = poll_keys()
        if k:
            return k
        rep = hid.read_report(h, in_len, 200)
        if rep is None:
            continue
        single = None
        for b in (3, 4, 5):
            diff = rep[b] ^ rest[b]
            if diff:
                single = (b, diff.bit_length() - 1) if (diff & (diff - 1)) == 0 else "multi"
                break
        if single is None or single == "multi":
            cand = None
            cnt = 0
            continue
        if single in reverse and reverse[single] != name:
            cand = None
            cnt = 0
            continue  # already-mapped button pressed; ignore
        if single == cand:
            cnt += 1
        else:
            cand = single
            cnt = 1
        if cnt >= 3:
            while time.time() < t_end:  # wait for release
                rep = hid.read_report(h, in_len, 200)
                if rep and (rep[cand[0]] ^ rest[cand[0]]) == 0:
                    break
            return cand
    return None


def detect_extreme(h, in_len, stick_bytes, axis, timeout=20):
    """Push-and-hold detection: return raw value at the extreme, or None."""
    t_end = time.time() + timeout
    stable = 0
    last = None
    while time.time() < t_end:
        k = poll_keys()
        if k:
            return None
        rep = hid.read_report(h, in_len, 200)
        if rep is None or max(stick_bytes) >= len(rep):
            continue
        x, y = mapping._unpack_12bit(rep, *stick_bytes)
        val = x if axis == "x" else y
        if abs(val - NOMINAL_CENTER) > STICK_THRESH:
            if last is not None and abs(val - last) < 70:
                stable += 1
            else:
                stable = 1
            last = val
            if stable >= 4:
                grabbed = val
                while time.time() < t_end:  # wait for return toward center
                    rep = hid.read_report(h, in_len, 200)
                    if rep is None:
                        continue
                    x2, y2 = mapping._unpack_12bit(rep, *stick_bytes)
                    v2 = x2 if axis == "x" else y2
                    if abs(v2 - NOMINAL_CENTER) < 400:
                        break
                return grabbed
        else:
            stable = 0
            last = None
    return None


def map_stick(h, in_len, label, stick_bytes):
    print(f"\n-- {label} stick --")
    res = {}
    for axis, word, key in (("y", "UP", "up"), ("y", "DOWN", "down"),
                            ("x", "LEFT", "left"), ("x", "RIGHT", "right")):
        print(f"   push the {label} stick fully {word} and hold...", end="", flush=True)
        v = detect_extreme(h, in_len, stick_bytes, axis)
        if v is None:
            print(" (skipped)")
        else:
            print(f" {v}")
        res[key] = v
    return res


def fmt_cal(neg, pos, fallback):
    if neg is None or pos is None:
        return fallback
    return (neg, pos)


def main():
    dev = hid.find_device()
    if not dev:
        print("No Switch 2 Pro (057E:2069) found. Plug it in via USB.")
        return 1
    h = hid.open_for_read(dev["path"], write=False)
    if not h:
        print("Could not open the controller for reading.")
        return 1
    in_len = dev["in_len"] or mapping.REPORT_LEN

    print("=" * 64)
    print(" Switch 2 Pro -- guided button & stick mapper")
    print("=" * 64)
    print("I'll name each control; press exactly that one. (s/Enter = skip,"
          " q = quit)\n")
    print("First: leave the controller ALONE for ~1.5s (calibrating rest)...")
    rest, n = calibrate_rest(h, in_len)
    if n < 20:
        print(f"Only {n} frames -- is it awake/connected? Aborting.")
        hid.close(h)
        return 1
    print(f"   rest bytes 3,4,5 = {rest[3]:02x} {rest[4]:02x} {rest[5]:02x} "
          f"({n} frames)\n")

    button_bits = {}
    reverse = {}
    try:
        for i, (name, desc) in enumerate(BUTTON_ORDER, 1):
            print(f"[{i:2}/{len(BUTTON_ORDER)}] press {desc} ...", end="", flush=True)
            res = detect_button(h, in_len, rest, reverse, name)
            if res == "quit":
                print(" quit.")
                hid.close(h)
                return 1
            if res == "skip" or res is None:
                print(" (skipped)")
                continue
            button_bits[name] = res
            reverse[res] = name
            print(f"  -> byte{res[0]} bit{res[1]}")

        print("\nNow the sticks (4 quick holds each).")
        left = map_stick(h, in_len, "LEFT", mapping.LEFT_STICK_BYTES)
        right = map_stick(h, in_len, "RIGHT", mapping.RIGHT_STICK_BYTES)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        hid.close(h)
        return 1
    hid.close(h)

    d = mapping.STICK_CAL  # provisional fallbacks
    stick_cal = {
        "LX": fmt_cal(left["left"], left["right"], d["LX"]),
        "LY": fmt_cal(left["down"], left["up"], d["LY"]),
        "RX": fmt_cal(right["left"], right["right"], d["RX"]),
        "RY": fmt_cal(right["down"], right["up"], d["RY"]),
    }

    # ---- write mapping_data.py ---------------------------------------------
    lines = [
        "# auto-generated by map_buttons.py -- verified button & stick mapping.",
        "# Delete this file to fall back to mapping.py's provisional defaults.",
        "",
        "BUTTON_BITS = {",
    ]
    for name in mapping.BUTTONS:
        if name in button_bits:
            b, bit = button_bits[name]
            lines.append(f"    {name!r}: ({b}, {bit}),")
    lines.append("}")
    lines.append("")
    lines.append(f"LEFT_STICK_BYTES = {tuple(mapping.LEFT_STICK_BYTES)}")
    lines.append(f"RIGHT_STICK_BYTES = {tuple(mapping.RIGHT_STICK_BYTES)}")
    lines.append("STICK_12BIT = True")
    lines.append("STICK_CAL = {")
    for k in ("LX", "LY", "RX", "RY"):
        lines.append(f"    {k!r}: {tuple(stick_cal[k])},")
    lines.append("}")
    lines.append("DEADZONE = 0.08")
    lines.append("")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("\n" + "=" * 64)
    print(f"Wrote {OUT}")
    print(f"  buttons mapped : {len(button_bits)}/{len(BUTTON_ORDER)}")
    miss = [n for n, _ in BUTTON_ORDER if n not in button_bits]
    if miss:
        print(f"  not mapped     : {', '.join(miss)}")
    print("  stick cal      :")
    for k in ("LX", "LY", "RX", "RY"):
        print(f"     {k} (neg,pos) = {stick_cal[k]}")
    print("\nDone. Now run:  python procon2\\bridge.py --debug   to verify, then")
    print("point Dolphin at the virtual Xbox 360 pad.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
