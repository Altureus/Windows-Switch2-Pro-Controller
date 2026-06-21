#!/usr/bin/env python3
r"""
mapping.py -- parse a Switch 2 Pro Controller HID input report into logical state.

  report bytes (Nintendo custom layout)  ->  ParsedState(buttons, sticks)

================================  STATUS  ===================================
VERIFIED on real hardware (procon2_probe.py):
  * report id   = 0x09, length 64
  * byte 1      = frame counter
  * byte 2      = 0x23 constant marker
  * bytes 3,4,5 = button bitfields (8 + 8 + 5 = 21 buttons, all 0x00 at rest)
  * bytes 6,7,8   = LEFT stick  (12-bit packed)   rest ~ (2043, 2168)
  * bytes 9,10,11 = RIGHT stick (12-bit packed)   rest ~ (2223, 2030)
  * bytes 16..44  = IMU -- ignored
  * bytes 45..63  = padding 0x00

The exact button bit<->name assignment and stick sign/range come from the
guided tool `map_buttons.py`, which writes `mapping_data.py`. If that file
exists it overrides the provisional defaults below (see the bottom of this file).
============================================================================
"""

REPORT_ID = 0x09
REPORT_LEN = 64

BUTTONS = ("A", "B", "X", "Y", "UP", "DOWN", "LEFT", "RIGHT",
           "L", "R", "ZL", "ZR", "MINUS", "PLUS", "L3", "R3",
           "HOME", "CAPTURE", "C", "GL", "GR")

# ====================  PROVISIONAL DEFAULTS  ================================
# Best interpretation of the first freehand capture, assuming strict press
# order A,B,X,Y / Up,Down,Left,Right / L,R,ZL,ZR / -,+ / L3,R3 / Home,Capture,C
# / GL,GR. The d-pad/shoulder rows are UNCERTAIN (press-order sensitive) --
# run map_buttons.py to replace all of this with a verified mapping_data.py.
BUTTON_BITS = {
    "A": (3, 0), "B": (3, 1), "X": (3, 2), "Y": (3, 3),
    "DOWN": (3, 4), "RIGHT": (3, 5), "R3": (3, 6), "R": (3, 7),
    "ZR": (4, 0), "PLUS": (4, 1), "MINUS": (4, 2), "ZL": (4, 3),
    "UP": (4, 4), "LEFT": (4, 5), "L3": (4, 6), "L": (4, 7),
    "HOME": (5, 0), "CAPTURE": (5, 1), "GR": (5, 2), "GL": (5, 3), "C": (5, 4),
}

LEFT_STICK_BYTES = (6, 7, 8)
RIGHT_STICK_BYTES = (9, 10, 11)
STICK_12BIT = True

# Per-axis linear calibration as (raw_at_negative_extreme, raw_at_positive_extreme),
# where "positive" = Xbox convention (right / up = +32767). Filled by map_buttons.py.
# Defaults: symmetric around the observed rest centers, ~±1800 of 12-bit range,
# Y inverted (raw tends to fall as the stick goes up). Good enough to be usable;
# calibration makes it exact.
STICK_CAL = {
    "LX": (2043 - 1800, 2043 + 1800),
    "LY": (2168 + 1800, 2168 - 1800),
    "RX": (2223 - 1800, 2223 + 1800),
    "RY": (2030 + 1800, 2030 - 1800),
}
DEADZONE = 0.08
# ====================  END PROVISIONAL DEFAULTS  ===========================


class ParsedState:
    __slots__ = ("buttons", "lx", "ly", "rx", "ry", "raw_btn", "counter")

    def __init__(self):
        self.buttons = set()
        self.lx = 0.0
        self.ly = 0.0
        self.rx = 0.0
        self.ry = 0.0
        self.raw_btn = (0, 0, 0)
        self.counter = 0

    def __repr__(self):
        b = "+".join(sorted(self.buttons)) or "-"
        return (f"<{b} L=({self.lx:+.2f},{self.ly:+.2f}) "
                f"R=({self.rx:+.2f},{self.ry:+.2f}) "
                f"btn={self.raw_btn[0]:02x},{self.raw_btn[1]:02x},{self.raw_btn[2]:02x}>")


def _unpack_12bit(report, b0, b1, b2):
    lo, mid, hi = report[b0], report[b1], report[b2]
    x = lo | ((mid & 0x0F) << 8)
    y = (mid >> 4) | (hi << 4)
    return x, y


def _norm(raw, cal):
    """Raw axis -> float in [-1,1] via linear (neg,pos) endpoints + deadzone."""
    neg, pos = cal
    span = (pos - neg) or 1
    v = 2.0 * (raw - neg) / span - 1.0
    if v < -1.0:
        v = -1.0
    elif v > 1.0:
        v = 1.0
    if -DEADZONE < v < DEADZONE:
        return 0.0
    return v


def parse(report):
    """bytes -> ParsedState. Tolerant of short/None input (returns neutral)."""
    st = ParsedState()
    if not report or len(report) < 6:
        return st
    st.counter = report[1]
    st.raw_btn = (report[3], report[4], report[5])
    for name, (bi, bit) in BUTTON_BITS.items():
        if bi < len(report) and (report[bi] >> bit) & 1:
            st.buttons.add(name)

    if STICK_12BIT and max(LEFT_STICK_BYTES) < len(report):
        lx, ly = _unpack_12bit(report, *LEFT_STICK_BYTES)
        st.lx = _norm(lx, STICK_CAL["LX"])
        st.ly = _norm(ly, STICK_CAL["LY"])
    if STICK_12BIT and max(RIGHT_STICK_BYTES) < len(report):
        rx, ry = _unpack_12bit(report, *RIGHT_STICK_BYTES)
        st.rx = _norm(rx, STICK_CAL["RX"])
        st.ry = _norm(ry, STICK_CAL["RY"])
    return st


def is_target_report(report):
    return bool(report) and len(report) >= 6 and report[0] == REPORT_ID


# ---- optional override from the guided tool --------------------------------
try:
    import mapping_data as _md  # noqa
    BUTTON_BITS = getattr(_md, "BUTTON_BITS", BUTTON_BITS)
    LEFT_STICK_BYTES = getattr(_md, "LEFT_STICK_BYTES", LEFT_STICK_BYTES)
    RIGHT_STICK_BYTES = getattr(_md, "RIGHT_STICK_BYTES", RIGHT_STICK_BYTES)
    STICK_12BIT = getattr(_md, "STICK_12BIT", STICK_12BIT)
    STICK_CAL = getattr(_md, "STICK_CAL", STICK_CAL)
    DEADZONE = getattr(_md, "DEADZONE", DEADZONE)
    _SOURCE = "mapping_data.py (calibrated)"
except ImportError:
    _SOURCE = "provisional defaults (run map_buttons.py to calibrate)"
