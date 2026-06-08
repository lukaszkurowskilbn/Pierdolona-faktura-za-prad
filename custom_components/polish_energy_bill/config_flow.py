"""Konfiguracja przez UI: wybór profilu, trybu zużycia, sensorów i opcji."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_BILLING_DAYS,
    CONF_BILLING_MONTHS,
    CONF_ENABLED_OVERRIDES,
    CONF_MODE,
    CONF_NAME,
    CONF_PROFILE,
    CONF_ZONE_SENSORS,
    DEFAULT_BILLING_MONTHS,
    DOMAIN,
    MODE_MANUAL,
    MODE_SENSOR,
)
from .core import Zone, load_builtin_profiles


async def _load_profiles(hass):
    return await hass.async_add_executor_job(load_builtin_profiles)


class PolishEnergyBillConfigFlow(ConfigFlow, domain=DOMAIN):
    """Główny flow dodawania integracji."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._profiles: dict = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._profiles = await _load_profiles(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_PROFILE: user_input[CONF_PROFILE],
                CONF_MODE: user_input[CONF_MODE],
            }
            if user_input[CONF_MODE] == MODE_SENSOR:
                return await self.async_step_sensors()
            self._data[CONF_ZONE_SENSORS] = {}
            return self._create()

        profile_options = [
            {"value": key, "label": p.name} for key, p in self._profiles.items()
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Rachunek za prąd"): str,
                vol.Required(CONF_PROFILE): SelectSelector(
                    SelectSelectorConfig(
                        options=profile_options, mode=SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required(CONF_MODE, default=MODE_SENSOR): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": MODE_SENSOR, "label": "Z sensora HA"},
                            {"value": MODE_MANUAL, "label": "Ręczne wpisywanie"},
                        ],
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wybór sensora zużycia dla każdej strefy profilu."""
        profile = self._profiles[self._data[CONF_PROFILE]]

        if user_input is not None:
            self._data[CONF_ZONE_SENSORS] = {
                zone.value: user_input[zone.value]
                for zone in profile.zones
                if user_input.get(zone.value)
            }
            return self._create()

        zone_labels = {
            Zone.ALL: "Zużycie całodobowe [kWh]",
            Zone.DAY: "Zużycie strefa dzienna [kWh]",
            Zone.NIGHT: "Zużycie strefa nocna [kWh]",
            Zone.PEAK: "Zużycie szczyt [kWh]",
            Zone.OFF_PEAK: "Zużycie poza szczytem [kWh]",
        }
        fields: dict = {}
        for zone in profile.zones:
            fields[vol.Required(zone.value)] = EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="energy")
            )
        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(fields),
            description_placeholders={"profile": profile.name},
        )

    @callback
    def _create(self) -> ConfigFlowResult:
        return self.async_create_entry(
            title=self._data[CONF_NAME], data=self._data, options={}
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> "PolishEnergyBillOptionsFlow":
        return PolishEnergyBillOptionsFlow(entry)


class PolishEnergyBillOptionsFlow(OptionsFlow):
    """Opcje: okres rozliczeniowy + które pozycje są aktywne."""

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        profiles = await _load_profiles(self.hass)
        profile = profiles[self.entry.data[CONF_PROFILE]]

        if user_input is not None:
            enabled = {
                pos.key: (pos.key in user_input.get("enabled_positions", []))
                for pos in profile.positions
            }
            options = {
                CONF_BILLING_MONTHS: user_input[CONF_BILLING_MONTHS],
                CONF_BILLING_DAYS: user_input.get(CONF_BILLING_DAYS) or 0,
                CONF_ENABLED_OVERRIDES: enabled,
            }
            return self.async_create_entry(title="", data=options)

        enabled_overrides = self.entry.options.get(CONF_ENABLED_OVERRIDES, {})
        current_enabled = [
            pos.key
            for pos in profile.positions
            if enabled_overrides.get(pos.key, pos.enabled)
        ]
        position_options = [
            {"value": pos.key, "label": f"{pos.name} ({pos.rate} zł)"}
            for pos in profile.positions
        ]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BILLING_MONTHS,
                    default=self.entry.options.get(
                        CONF_BILLING_MONTHS, DEFAULT_BILLING_MONTHS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=12, step=0.01, mode="box")
                ),
                vol.Optional(
                    CONF_BILLING_DAYS,
                    default=self.entry.options.get(CONF_BILLING_DAYS, 0),
                ): NumberSelector(
                    NumberSelectorConfig(min=0, max=366, step=1, mode="box")
                ),
                vol.Optional(
                    "enabled_positions", default=current_enabled
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=position_options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
