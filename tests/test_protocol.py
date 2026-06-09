"""Offline tests for the pure treadmill protocol layer.

Runnable without Home Assistant or pytest:

    python3 tests/test_protocol.py

Also discoverable by pytest.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "custom_components", "pacekeeper"),
)

from protocol import (  # noqa: E402
    Command,
    Status,
    pause_command,
    parse_state,
    set_speed_command,
    start_command,
    stop_command,
)


def _reference_make_packet(command: int, speed: int) -> bytes:
    """Independent re-implementation of the firmware ``makePacket``.

    Mirrors ``src/TreadmillHandler.cpp`` byte-for-byte so we can assert the
    Python port produces identical packets.
    """
    out = bytearray(23)
    out[0] = 0x6A
    out[1] = 0x17
    for i in range(2, 6):
        out[i] = 0
    out[6] = (speed >> 8) & 0xFF
    out[7] = speed & 0xFF
    out[8] = 5 if speed != 0 else 1
    out[9] = 0
    out[10] = 80
    out[11] = 0
    out[12] = command & 0xF7
    user_id = 58965456623
    for i in range(8):
        out[13 + i] = (user_id >> (56 - i * 8)) & 0xFF
    checksum = 0
    for i in range(1, 21):
        checksum ^= out[i]
    out[21] = checksum
    out[22] = 0x43
    return bytes(out)


def test_command_packets_match_firmware() -> None:
    cases = [
        (start_command(), Command.START_SET_SPEED, 0),
        (set_speed_command(3000), Command.START_SET_SPEED, 3000),
        (set_speed_command(6000), Command.START_SET_SPEED, 6000),
        (pause_command(), Command.PAUSE, 0),
        (stop_command(), Command.STOP, 0),
    ]
    for packet, command, speed in cases:
        expected = _reference_make_packet(int(command), speed)
        assert packet == expected, (
            f"{command!r} speed={speed}: {packet.hex()} != {expected.hex()}"
        )
        assert len(packet) == 23
        assert packet[0] == 0x6A and packet[22] == 0x43
        assert packet[1] == 0x17


def test_set_speed_encodes_big_endian() -> None:
    packet = set_speed_command(3000)  # 0x0BB8
    assert packet[6] == 0x0B
    assert packet[7] == 0xB8
    assert packet[8] == 5  # non-zero speed -> magic byte 5


def test_checksum_is_xor_of_payload() -> None:
    packet = set_speed_command(1234)
    expected = 0
    for byte in packet[1:21]:
        expected ^= byte
    assert packet[21] == expected


def _build_state_packet(
    *,
    current_speed: int,
    target_speed: int,
    distance: int,
    steps: int,
    calories: int,
    duration_ms: int,
    fw: int,
    flags: int,
    max_speed: int,
) -> bytes:
    payload = bytearray(31)
    payload[3:5] = current_speed.to_bytes(2, "big")
    payload[5:7] = target_speed.to_bytes(2, "big")
    payload[7:11] = distance.to_bytes(4, "big")
    payload[14:18] = steps.to_bytes(4, "big")
    payload[18:20] = calories.to_bytes(2, "big")
    payload[20:24] = duration_ms.to_bytes(4, "big")
    payload[25] = fw
    payload[26] = flags
    payload[27:29] = max_speed.to_bytes(2, "big")
    return bytes(payload)


def test_parse_state_decodes_fields() -> None:
    packet = _build_state_packet(
        current_speed=2500,
        target_speed=3000,
        distance=1234,
        steps=987,
        calories=42,
        duration_ms=65000,
        fw=7,
        flags=0x08,  # running, metric
        max_speed=6000,
    )
    data = parse_state(packet)
    assert data is not None
    assert data.status is Status.RUNNING
    assert data.speed_feedback == 2.5
    assert data.speed_cmd == 3.0
    assert data.distance_km == 1.234
    assert data.steps == 987
    assert data.calories == 42
    assert data.duration_sec == 65
    assert data.fw_version == 7
    assert data.speed_max == 6.0
    assert data.imperial is False


def test_parse_state_status_bits() -> None:
    expected = {
        0x18: Status.COUNTDOWN,
        0x08: Status.RUNNING,
        0x10: Status.PAUSED,
        0x00: Status.STOPPED,
    }
    for flags, status in expected.items():
        packet = _build_state_packet(
            current_speed=0,
            target_speed=0,
            distance=0,
            steps=0,
            calories=0,
            duration_ms=0,
            fw=1,
            flags=flags,
            max_speed=0,
        )
        data = parse_state(packet)
        assert data is not None
        assert data.status is status, f"flags={flags:#x}"


def test_parse_state_imperial_flag() -> None:
    packet = _build_state_packet(
        current_speed=0,
        target_speed=0,
        distance=0,
        steps=0,
        calories=0,
        duration_ms=0,
        fw=1,
        flags=0x80,  # imperial bit set
        max_speed=0,
    )
    data = parse_state(packet)
    assert data is not None
    assert data.imperial is True


def test_parse_state_imperial_does_not_rescale() -> None:
    # The treadmill reports km/h / km over BLE even when its panel is set to
    # mph/miles; Home Assistant converts to the user's unit system for display,
    # so the decoder must NOT rescale based on the imperial flag.
    packet = _build_state_packet(
        current_speed=3000,  # 3.0 km/h
        target_speed=3000,
        distance=1000,  # 1.0 km
        steps=0,
        calories=0,
        duration_ms=0,
        fw=1,
        flags=0x80 | 0x08,  # imperial panel + running
        max_speed=6000,
    )
    data = parse_state(packet)
    assert data is not None
    assert data.imperial is True
    assert abs(data.speed_feedback - 3.0) < 0.001
    assert abs(data.speed_cmd - 3.0) < 0.001
    assert abs(data.speed_max - 6.0) < 0.001
    assert abs(data.distance_km - 1.0) < 0.001


def test_parse_state_metric_not_converted() -> None:
    packet = _build_state_packet(
        current_speed=3000,  # 3.0 km/h
        target_speed=3000,
        distance=1000,  # 1.0 km
        steps=0,
        calories=0,
        duration_ms=0,
        fw=1,
        flags=0x08,  # metric + running
        max_speed=6000,
    )
    data = parse_state(packet)
    assert data is not None
    assert data.imperial is False
    assert abs(data.speed_feedback - 3.0) < 0.001
    assert abs(data.distance_km - 1.0) < 0.001




def test_parse_state_rejects_short_packets() -> None:
    assert parse_state(b"") is None
    assert parse_state(bytes(30)) is None
    assert parse_state(None) is None


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as err:
            failures += 1
            print(f"FAIL {test.__name__}: {err}")
        except Exception as err:  # noqa: BLE001 - report, don't abort the run
            failures += 1
            print(f"ERROR {test.__name__}: {type(err).__name__}: {err}")
        else:
            print(f"ok   {test.__name__}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run())
