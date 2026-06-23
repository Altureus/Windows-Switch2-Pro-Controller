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

> **Don't want to install Python?** Grab the prebuilt **`Switch2ProBridge.exe`** from the
> [latest release](../../releases/latest): run the bundled ViGEmBus installer once, then run
> the exe — that's it. The Python steps below are only for running from source.

1. **Install Python 3** — <https://www.python.org/downloads/>. In the installer, tick
   **"Add python.exe to PATH"**. (No `pip install` needed — this app has *zero* Python dependencies.)
2. **Install the ViGEmBus driver** — double-click the bundled
   **`drivers/ViGEmBus_1.22.0_x64_x86_arm64.exe`** (one click, needs admin); it's the
   kernel-mode piece. Newer versions: <https://github.com/nefarius/ViGEmBus/releases/latest>.
3. **Get this repo** — download the [latest release](../../releases/latest) zip (or `git clone`) and unzip it.
4. *(Recommended)* double-click **`Setup Check.bat`** — it verifies Python + ViGEmBus are
   ready and flags anything missing.
5. Run **`Start (Auto-detect).bat`** — it uses **USB** if the controller is plugged in,
   otherwise **Bluetooth**, and switches live when you plug or unplug. (Power users can force
   one with `python procon2\launch.py --usb` or `--bluetooth`.) Keep the window open. In Dolphin,
   set a controller port to **Standard Controller → Configure**, pick the **`XInput/N/Gamepad`**
   it prints, and bind your controls.

The bridge keeps Dolphin pointed at whatever XInput slot it lands on, auto-wakes the
controller on every (re)attach, and survives unplugs.

> ⚠️ The bundled `procon2/mapping_data.py` is calibrated for **my** controller. If a
> button or stick feels off, run **`Map Buttons.bat`** (`map_buttons.py`) — it names each
> control, you press it, and it writes your own verified mapping.

## Autostart (optional)

Don't want to open `Start (Auto-detect).bat` every time? Double-click **`Install Autostart.bat`** —
the bridge then launches **silently at every login** (no window), so the controller just
works. Per-user, no admin.

- **`Stop Bridge.bat`** — stop the hidden bridge now.
- **`Uninstall Autostart.bat`** — stop launching it at login.

It simply drops a shortcut in your Startup folder that runs `pythonw launch.py` (auto
USB/Bluetooth). You can also drive it directly: `python procon2\autostart.py install|uninstall|status|stop`.

## Wireless (Bluetooth) — optional

Got a Bluetooth LE adapter? You can run the bridge **cordless**. Windows' own
"Add a device" can't pair the Switch 2 Pro (it doesn't use standard
HID-over-Bluetooth), so this talks to it directly over BLE.

1. **One-time:** `pip install bleak` (only the wireless path needs it; the launcher
   tells you if it's missing).
2. Double-click **`Start (Auto-detect).bat`** — with no USB cable connected, it connects
   over Bluetooth.
3. **First connection:** hold the small recessed sync button until the player LEDs
   run, so the controller **bonds** to this PC. After that, just turn it on / tap a
   button and it reconnects automatically — no pairing mode needed.

Everything downstream is identical to the wired path: same virtual Xbox 360 pad,
same Dolphin setup, and **rumble works wirelessly too** (Dolphin → controller over
BLE). The wireless path is the only piece that needs a Python package (`bleak`); the
USB path stays zero-dependency.

## How & why (deep dive)

See [`procon2/README.md`](procon2/README.md) for the reverse-engineering notes: the report
layout, the wake sequence, the haptic format, and a file-by-file breakdown.

## Troubleshooting

**The controller is moving my mouse, opening random windows, or popping up an
on-screen keyboard.** That's **Steam Input**, not this bridge. While Steam is
running, its *desktop configuration* grabs any Xbox-style controller — including
this virtual pad — and maps the right stick to the mouse, buttons to clicks, and a
button to Steam's on-screen keyboard. Fix it once in **Steam → Settings →
Controller**: turn **off** Steam Input for **Xbox controllers**, or disable the
**Desktop Layout** so the controller can't drive your desktop. (Fully quitting
Steam — tray icon → Exit — stops it immediately.)

## Credits

- [ViGEmBus / ViGEmClient](https://github.com/nefarius/ViGEmBus) by Nefarius (MIT).
- Wake + haptic protocol reverse-engineered with help from HandHeldLegend's ProCon2Tool
  and [`NSW2-controller-enabler`](https://github.com/ikz87/NSW2-controller-enabler).
- **Bluetooth LE** protocol adapted from
  [`CareyScott/switch2controllerpc`](https://github.com/CareyScott/switch2controllerpc)
  by Scott Carey (MIT) — see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

MIT — see [LICENSE](LICENSE). Third-party components: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

*Disclaimer: not affiliated with or endorsed by Nintendo. "Nintendo Switch" is a
trademark of Nintendo. Use at your own risk.*
