"""Pure protocol layer for the PitPat/Superun treadmill BLE interface.

This module is a faithful port of the reverse-engineered protocol implemented
in the ESP32 firmware (``src/TreadmillHandler.cpp``). It is intentionally free
of any Home Assistant or ``bleak`` imports so it can be unit tested in
isolation and reused by the connection manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

# --- Command packet framing ------------------------------------------------
START_BYTE = 0x6A
END_BYTE = 0x43
PACKET_LENGTH = 0x17  # 23 bytes, stored verbatim in byte[1]

# The firmware embeds a fixed "user id" and default weight in every command.
DEFAULT_USER_ID = 58965456623
DEFAULT_WEIGHT = 80

# A state notification is at least this many bytes before we trust it.
MIN_STATE_PACKET_LENGTH = 31


class Command(IntEnum):
    """Command byte values understood by the treadmill."""

    START_SET_SPEED = 4
    PAUSE = 2
    STOP = 0


class Status(IntEnum):
    """Decoded running state of the treadmill."""

    COUNTDOWN = 0
    RUNNING = 1
    PAUSED = 2
    STOPPED = 3
    # Internal-only: not sent by the treadmill, used when the link is down.
    DISCONNECTED = 100


STATUS_STR = {
    Status.COUNTDOWN: "countdown",
    Status.RUNNING: "running",
    Status.PAUSED: "paused",
    Status.STOPPED: "stopped",
    Status.DISCONNECTED: "disconnected",
}


@dataclass
class TreadmillData:
    """Snapshot of treadmill telemetry decoded from a state notification."""

    status: Status = Status.DISCONNECTED
    speed_cmd: float = 0.0  # target speed in km/h
    speed_feedback: float = 0.0  # current speed in km/h
    speed_max: float = 0.0  # max selectable speed in km/h
    distance_km: float = 0.0
    calories: int = 0
    steps: int = 0
    duration_sec: int = 0
    fw_version: int = 0
    imperial: bool = False


def _xor_checksum(packet: bytes, start: int, end_inclusive: int) -> int:
    """XOR every byte in ``packet[start..end_inclusive]`` (matches firmware)."""
    checksum = 0
    for i in range(start, end_inclusive + 1):
        checksum ^= packet[i]
    return checksum


def build_command(
    command: Command,
    speed: int = 0,
    *,
    incline: int = 0,
    weight: int = DEFAULT_WEIGHT,
    user_id: int = DEFAULT_USER_ID,
) -> bytes:
    """Build a 23-byte command packet.

    ``speed`` is expressed in thousandths of km/h (e.g. ``3000`` == 3.0 km/h),
    exactly as the firmware encodes it.
    """
    packet = bytearray(23)
    packet[0] = START_BYTE
    packet[1] = PACKET_LENGTH
    # bytes 2..5 are reserved (already zero)
    packet[6] = (speed >> 8) & 0xFF
    packet[7] = speed & 0xFF
    # Magic byte: 5 when a non-zero speed is set, 1 otherwise.
    packet[8] = 5 if speed != 0 else 1
    packet[9] = incline & 0xFF
    packet[10] = weight & 0xFF
    packet[11] = 0
    # Command byte; clearing bit 3 selects kph mode (matches firmware).
    packet[12] = int(command) & 0xF7
    packet[13:21] = int(user_id).to_bytes(8, "big")
    packet[21] = _xor_checksum(packet, 1, 20)
    packet[22] = END_BYTE
    return bytes(packet)


def start_command() -> bytes:
    """Start the belt (set-speed command with speed 0)."""
    return build_command(Command.START_SET_SPEED, 0)


def set_speed_command(speed: int) -> bytes:
    """Set the target speed (in thousandths of km/h)."""
    return build_command(Command.START_SET_SPEED, speed)


def pause_command() -> bytes:
    """Pause the belt."""
    return build_command(Command.PAUSE, 0)


def stop_command() -> bytes:
    """Stop the belt."""
    return build_command(Command.STOP, 0)


def parse_state(payload: bytes) -> TreadmillData | None:
    """Decode a state notification into :class:`TreadmillData`.

    Returns ``None`` for packets that are too short to be valid, mirroring the
    firmware which discards anything shorter than 31 bytes.
    """
    if payload is None or len(payload) < MIN_STATE_PACKET_LENGTH:
        return None

    current_speed = int.from_bytes(payload[3:5], "big")
    target_speed = int.from_bytes(payload[5:7], "big")
    distance = int.from_bytes(payload[7:11], "big")
    steps = int.from_bytes(payload[14:18], "big")
    calories = int.from_bytes(payload[18:20], "big")
    duration_ms = int.from_bytes(payload[20:24], "big")
    fw_version = payload[25]
    flags = payload[26]
    max_speed = int.from_bytes(payload[27:29], "big")

    imperial = bool(flags & 0x80)
    state_bits = flags & 0x18
    status = {
        0x18: Status.COUNTDOWN,
        0x08: Status.RUNNING,
        0x10: Status.PAUSED,
    }.get(state_bits, Status.STOPPED)

    return TreadmillData(
        status=status,
        speed_cmd=target_speed / 1000.0,
        speed_feedback=current_speed / 1000.0,
        speed_max=max_speed / 1000.0,
        distance_km=distance / 1000.0,
        calories=calories,
        steps=steps,
        duration_sec=duration_ms // 1000,
        fw_version=fw_version,
        imperial=imperial,
    )
