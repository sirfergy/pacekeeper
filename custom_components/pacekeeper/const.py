"""Constants for the PaceKeeper treadmill integration."""

from __future__ import annotations

DOMAIN = "pacekeeper"

# GATT layout of the PitPat/Superun treadmill (see src/platform.h).
SERVICE_PAD_UUID = "0000fba0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_WRITE_UUID = "0000fba1-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_NOTIFY_STATE_UUID = "0000fba2-0000-1000-8000-00805f9b34fb"

# Advertised name prefix used for Bluetooth discovery.
DEVICE_NAME_PREFIX = "PitPat"

DEFAULT_NAME = "PaceKeeper Treadmill"
MANUFACTURER = "PitPat"
MODEL = "Treadmill (BLE)"

# Speed slider bounds, in km/h, matching the firmware's MQTT number entity.
MIN_SPEED_KMH = 0.0
MAX_SPEED_KMH = 6.0
SPEED_STEP_KMH = 0.1

# Speeds at or below this (in km/h) are treated as a stop request, matching the
# firmware which stops the belt for any commanded speed <= 100 (0.1 km/h).
STOP_THRESHOLD_KMH = 0.1
