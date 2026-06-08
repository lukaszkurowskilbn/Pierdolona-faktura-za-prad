"""DataUpdateCoordinator — spina zużycie, stawki i kalkulator."""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_BILLING_DAYS,
    CONF_BILLING_MONTHS,
    CONF_ENABLED_OVERRIDES,
    CONF_MODE,
    CONF_ZONE_SENSORS,
    DEFAULT_BILLING_MONTHS,
    DOMAIN,
    MODE_MANUAL,
)
from .core import (
    Bill,
    BillingPeriod,
    Consumption,
    TariffProfile,
    Zone,
    calculate,
)

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=1)


class BillCoordinator(DataUpdateCoordinator[Bill]):
    """Liczy rachunek na bazie aktualnych danych i odświeża go cyklicznie."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        base_profile: TariffProfile,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self.base_profile = base_profile

        # Stan żywy, zasilany przez encje number (RestoreNumber):
        self.rate_overrides: dict[str, Decimal] = {}
        self.manual_consumption: dict[Zone, Decimal] = {}
        # Punkt zero (odczyt licznika bazowy) per strefa — tryb sensor:
        self.baseline: dict[Zone, Decimal] = {}
        # Rejestr encji baseline, by przycisk mógł je ustawić:
        self._baseline_entities: dict[Zone, Any] = {}

    # --- API dla encji number ---

    @callback
    def set_rate_override(self, key: str, value: float) -> None:
        self.rate_overrides[key] = Decimal(str(value))

    @callback
    def set_manual_consumption(self, zone: Zone, value: float) -> None:
        self.manual_consumption[zone] = Decimal(str(value))

    @callback
    def set_baseline(self, zone: Zone, value: float) -> None:
        self.baseline[zone] = Decimal(str(value))

    @callback
    def register_baseline_entity(self, zone: Zone, entity: Any) -> None:
        self._baseline_entities[zone] = entity

    async def capture_zero(self, zone: Zone) -> bool:
        """Zapisuje bieżący odczyt sensora strefy jako punkt zero.

        Zwraca True, jeśli udało się odczytać sensor. Aktualizuje też encję
        number 'Odczyt zero', by wartość była widoczna w UI.
        """
        entity_id = self.zone_sensors.get(zone.value)
        if not entity_id:
            return False
        value = self._read_sensor(entity_id)
        if value is None:
            return False
        entity = self._baseline_entities.get(zone)
        if entity is not None:
            await entity.async_set_native_value(float(value))
        else:
            self.set_baseline(zone, float(value))
            await self.async_request_refresh()
        return True

    # --- konfiguracja z opcji ---

    @property
    def mode(self) -> str:
        return self.entry.data.get(CONF_MODE, MODE_MANUAL)

    @property
    def zone_sensors(self) -> dict[str, str]:
        return self.entry.data.get(CONF_ZONE_SENSORS, {})

    @property
    def enabled_overrides(self) -> dict[str, bool]:
        return self.entry.options.get(CONF_ENABLED_OVERRIDES, {})

    def _billing_period(self) -> BillingPeriod:
        months = Decimal(
            str(self.entry.options.get(CONF_BILLING_MONTHS, DEFAULT_BILLING_MONTHS))
        )
        days = self.entry.options.get(CONF_BILLING_DAYS)
        if not days:  # auto: liczba dni bieżącego miesiąca
            today = date.today()
            days = calendar.monthrange(today.year, today.month)[1]
        return BillingPeriod(days=int(days), months=months)

    # --- odczyt zużycia ---

    def _read_consumption(self) -> Consumption:
        by_zone: dict[Zone, Decimal] = {}
        if self.mode == MODE_MANUAL:
            by_zone = dict(self.manual_consumption)
        else:
            for zone_name, entity_id in self.zone_sensors.items():
                value = self._read_sensor(entity_id)
                if value is None:
                    continue
                zone = Zone(zone_name)
                # Zużycie liczone od punktu zero (bazowego odczytu licznika).
                base = self.baseline.get(zone, Decimal("0"))
                by_zone[zone] = max(Decimal("0"), value - base)
        if not by_zone:
            by_zone = {Zone.ALL: Decimal("0")}
        return Consumption(by_zone)

    def _read_sensor(self, entity_id: str) -> Decimal | None:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", "", None):
            return None
        try:
            return Decimal(str(state.state))
        except (InvalidOperation, ValueError):
            _LOGGER.warning("Sensor %s ma niepoprawną wartość: %s", entity_id, state.state)
            return None

    # --- główna pętla ---

    async def _async_update_data(self) -> Bill:
        profile = self.base_profile.customize(
            rate_overrides=self.rate_overrides,
            enabled_overrides=self.enabled_overrides,
        )
        consumption = self._read_consumption()
        period = self._billing_period()
        return calculate(profile, consumption, period)

    def effective_profile(self) -> TariffProfile:
        """Profil z aktualnymi override'ami — używany przez encje number."""
        return self.base_profile.customize(
            rate_overrides=self.rate_overrides,
            enabled_overrides=self.enabled_overrides,
        )
