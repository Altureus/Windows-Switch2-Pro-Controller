#!/usr/bin/env python3
r"""
haptics.py -- Switch 2 Pro rumble, via HID output report 0x02.

Format reverse-engineered from ProCon2Tool's "play test haptic" log (so these are
the controller's OWN official test values -- known safe, won't over-drive the
linear actuators). Each report is 64 bytes:

  [0]      0x02                report id
  [1]      0x50 | counter      counter cycles 0x0..0xF each frame
  [2..6]   5-byte payload      actuator A
  [7..16]  00
  [17]     0x50 | counter      same counter
  [18..22] 5-byte payload      actuator B
  [23..63] 00

Sustained rumble needs a continuous stream of these (~60-90 Hz) with the counter
incrementing; stop by streaming the OFF payload (or just stopping).

The payloads below are taken VERBATIM from the captured test waveform -- we do NOT
synthesize new amplitudes (that's where the actuator-damage risk lives).
"""
REPORT_ID = 0x02
REPORT_LEN = 64

# 5-byte per-actuator payloads, lifted straight from ProCon2Tool's test log.
OFF = bytes([0x00, 0x00, 0x00, 0x00, 0x00])
LOW = bytes([0x3f, 0x01, 0xf0, 0x19, 0x00])   # faded tail of the test
MED = bytes([0x3f, 0x19, 0xf0, 0x99, 0x00])   # sustained mid
HIGH = bytes([0x3f, 0x25, 0xf0, 0x99, 0x00])  # strongest sustained value seen


def build_frame(counter, data_a, data_b=None):
    """Build a 64-byte HID output report for one rumble frame."""
    if data_b is None:
        data_b = data_a
    f = bytearray(REPORT_LEN)
    f[0] = REPORT_ID
    c = 0x50 | (counter & 0x0F)
    f[1] = c
    f[2:7] = data_a
    f[17] = c
    f[18:23] = data_b
    return bytes(f)


def level_for(amplitude):
    """Map a 0..255 motor value to one of the captured (safe) payloads.
    Biased upward: MED felt very gentle in testing, so light rumble uses MED and
    anything moderate-or-stronger uses HIGH (the strongest *captured* value -- we
    don't synthesize beyond it, to stay in the actuator-safe range)."""
    if amplitude <= 0:
        return OFF
    if amplitude < 96:
        return MED
    return HIGH
