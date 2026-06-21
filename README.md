# Switch 2 Pro Controller → Xbox pad bridge (Windows)

A native Windows app that makes the **Nintendo Switch 2 Pro Controller**
(USB `057E:2069`) work as a standard Xbox 360 controller — in **Dolphin** and any
game/emulator — with **rumble**, an **auto-reconnect/auto-wake** loop, and **zero
third-party Python packages** (pure `ctypes`).

The Switch 2 Pro is a new controller Windows can't use out of the box: it
enumerates as a raw HID device (`If_Hid`), boots **asleep** (streams nothing until
woken), and uses a custom report layout emulators can't parse. Existing tools are
either browser-based (and drop when the tab loses focus) or flaky Bluetooth. As far
as I can tell this is the only **native, USB-wired, self-waking** tool that presents
it as a real driver-level Xbox pad.

## What it does

- **Wakes** the controller over its WinUSB vendor interface.
- **Reads** its 64-byte HID reports and **parses** the custom button/stick layout.
- **Publishes** a virtual Xbox 360 pad via **ViGEmBus** → Dolphin sees normal XInput.
- **Rumble** both ways: emulator → controller haptics.
- **Never drops**: holds the virtual pad and auto-reconnects/re-wakes through any hiccup.

```
Switch 2 Pro (asleep)  ->  WinUSB bulk wake        (winusb.py)
                       ->  read HID reports         (hid.py)
                       ->  parse custom layout      (mapping.py)
                       ->  virtual Xbox 360 pad     (vigem.py / ViGEmBus)  ->  Dolphin (XInput)
                       <-  rumble: HID report 0x02  (haptics.py)
```

## Requirements

- **Windows 10/11 (x64)**
- **Python 3** (any modern version, including 3.14 — **no `pip install` needed**)
- **ViGEmBus driver** installed — <https://github.com/nefarius/ViGEmBus>
  (the bundled `ViGEmClient.dll` is only the user-mode client; the kernel driver is separate)
- A **Switch 2 Pro Controller** connected via USB

## Quick start

1. Install the **ViGEmBus** driver (link above).
2. Double-click **`Start Bridge.bat`** (or run `python procon2\bridge.py`). Keep the window open.
3. In Dolphin: set a controller port to **Standard Controller → Configure**, pick the
   **`XInput/N/Gamepad`** the bridge prints, and bind your controls (or load a profile).

The bridge keeps Dolphin pointed at whatever XInput slot it lands on, auto-wakes the
controller on every (re)attach, and survives unplugs.

> ⚠️ The bundled `procon2/mapping_data.py` is calibrated for **my** controller. If a
> button or stick feels off, run **`Map Buttons.bat`** (`map_buttons.py`) — it names each
> control, you press it, and it writes your own verified mapping.

## How & why (deep dive)

See [`procon2/README.md`](procon2/README.md) for the reverse-engineering notes: the report
layout, the wake sequence, the haptic format, and a file-by-file breakdown.

## Credits

- [ViGEmBus / ViGEmClient](https://github.com/nefarius/ViGEmBus) by Nefarius (MIT).
- Wake + haptic protocol reverse-engineered with help from HandHeldLegend's ProCon2Tool
  and [`NSW2-controller-enabler`](https://github.com/ikz87/NSW2-controller-enabler).

## License

MIT — see [LICENSE](LICENSE). Third-party components: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

*Disclaimer: not affiliated with or endorsed by Nintendo. "Nintendo Switch" is a
trademark of Nintendo. Use at your own risk.*
