"""Przyciski: ustawienie bieżącego odczytu licznika jako punkt zero."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_SENSOR
from .coordinator import BillCoordinator
from .core import Zone

ZONE_LABEL = {
    Zone.ALL: "całodobowa",
    Zone.DAY: "dzień",
    Zone.NIGHT: "noc",
    Zone.PEAK: "szczyt",
    Zone.OFF_PEAK: "poza szczytem",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BillCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.mode != MODE_SENSOR:
        return  # przycisk ma sens tylko gdy zużycie pochodzi z sensora
    async_add_entities(
        SetZeroButton(coordinator, entry, zone)
        for zone in coordinator.base_profile.zones
    )


class SetZeroButton(ButtonEntity):
    """Zapisuje aktualny odczyt licznika jako nowy punkt zero (start okresu)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: BillCoordinator, entry: ConfigEntry, zone: Zone
    ) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._zone = zone
        self._attr_name = f"Ustaw jako zero ({ZONE_LABEL.get(zone, zone.value)})"
        self._attr_unique_id = f"{entry.entry_id}_setzero_{zone.value}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.title,
            "manufacturer": self.coordinator.base_profile.seller,
            "model": self.coordinator.base_profile.name,
        }

    async def async_press(self) -> None:
        await self.coordinator.capture_zero(self._zone)
