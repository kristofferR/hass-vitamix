# Vitamix integration for Home Assistant

Adds a [Vitamix](https://www.vitamix.com/) Self-Detect blender (Ascent / Venturist
series) to Home Assistant over Bluetooth Low Energy. Discovery is automatic if
the blender is in range of any HA-registered Bluetooth scanner — the laptop
running HA, a USB BT dongle, or any [Bluetooth Proxy](https://esphome.io/projects/?type=bluetooth-proxy)
or BLE-capable Shelly device.

Exposes the blender's state (sleeping, container, ready, running) as Home
Assistant entities, and can upload custom programs the way the official app
does. A physical start press is still required to spin the blade.

Powered by [vitamix-ble](https://github.com/kristofferR/vitamix-ble).
