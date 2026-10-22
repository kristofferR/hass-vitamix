# hass-vitamix

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Home Assistant custom component for [Vitamix](https://www.vitamix.com/) Self-Detect
blenders (Ascent A2300 / A2500 / A3300 / A3500 and Venturist 330 / 350) over
Bluetooth Low Energy.

> [!NOTE]
> This is an **unofficial** integration. It is not endorsed by, affiliated
> with, or supported by Vita-Mix Corporation.

Built on top of the [`vitamix-ble`](https://github.com/kristofferR/vitamix-ble)
library.

## Features

- **Auto-discovery** via Home Assistant's Bluetooth platform, by local name
  or service UUID. Works with the local adapter or any
  [Bluetooth Proxy](https://esphome.io/projects/?type=bluetooth-proxy) /
  BLE-capable Shelly device.
- **Panel detection** like the official Perfect Blend app (C-panel Ascent
  A3300/A3500, B-panel Ascent A2300/A2500 and Venturist), with each panel
  polled on its own registers.
- **Entities**:
  - `sensor.<device>_state`: sleeping, no container, idle, ready (press
    pulse / press start), running
  - `binary_sensor.<device>_motor_running`, `_sleeping`, `_container_attached`
  - `sensor.<device>_container`: short id of the attached Self-Detect container
  - `sensor.<device>_container_max_runtime`, `_container_name`, and (disabled
    by default) `_container_id`, `_recipe_state`
- **Services**: `vitamix.upload_program` (up to four power/time/ramp steps,
  checked against the attached container; then press start on the blender)
  and `vitamix.cancel`.
- **Diagnostics**: detected panel and firmware, last advertisement (proxy,
  RSSI, age), last successful poll, last error and Home Assistant's
  reachability explanation.
- Adaptive polling: slow while idle, fast while the motor runs.

## Experimental motor control

The official app has no remote start, live speed control or remote stop.
`start_motor`, `set_motor_speed`, `stop_motor`, `play_melody` and
`load_program` write registers the app never uses this way. They only appear
after enabling **Experimental motor control** in the integration's options.
Do not rely on `stop_motor` as a safety stop.

## Troubleshooting

- The panel sleeps when idle. **Turn the dial** to wake it, as the official
  app instructs, then reload the integration.
- If setup keeps retrying, download the diagnostics: they show which proxy
  last heard the blender and at what signal strength. The nearest proxy is
  not always the one that receives it, and a signal around −90 dBm is too
  weak to connect. Moving a proxy closer usually fixes it.
- Requires Home Assistant 2026.6 or newer.

## Install

### HACS (recommended)

1. In HACS, add this repository as a **Custom repository** of category
   "Integration":
   `https://github.com/kristofferR/hass-vitamix`
2. Install **Vitamix** from HACS and restart Home Assistant.
3. The blender should be auto-discovered. If not, *Settings → Devices →
   Add Integration → Vitamix*.

### Manual

Copy `custom_components/vitamix/` into your Home Assistant
`config/custom_components/` directory and restart.

## Hardware tested

- Vitamix Ascent A3500 (earlier versions, which polled slave 0x67).
- Vitamix Ascent A3500i (EU, 2023): connects and polls; the C-panel register
  paths used since panel detection still need confirmation on hardware.

Other Self-Detect models speaking the same protocol should work out of
the box; please open an issue if yours doesn't.

## License

MIT — see [LICENSE](LICENSE).
