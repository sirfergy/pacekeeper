"""Number platform (speed control) for the PaceKeeper treadmill."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PaceKeeperConfigEntry
from .const import (
    MAX_SPEED_KMH,
    MIN_SPEED_KMH,
    SPEED_STEP_KMH,
    STOP_THRESHOLD_KMH,
)
from .entity import PaceKeeperEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaceKeeperConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the speed number entity."""
    async_add_entities([PaceKeeperSpeedNumber(entry.runtime_data.coordinator)])


class PaceKeeperSpeedNumber(PaceKeeperEntity, NumberEntity):
    """Target speed slider. Setting it (re)starts the belt; 0 stops it."""

    _attr_translation_key = "speed"
    _attr_device_class = NumberDeviceClass.SPEED
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_min_value = MIN_SPEED_KMH
    _attr_native_max_value = MAX_SPEED_KMH
    _attr_native_step = SPEED_STEP_KMH
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_speed"

    @property
    def native_value(self) -> float:
        return round(self.data.speed_cmd, 2)

    async def async_set_native_value(self, value: float) -> None:
        if value <= STOP_THRESHOLD_KMH:
            await self.coordinator.treadmill.async_stop()
            return
        speed_milli = int(round(value * 1000))
        speed_milli = max(0, min(speed_milli, int(MAX_SPEED_KMH * 1000)))
        await self.coordinator.treadmill.async_set_speed(speed_milli)
