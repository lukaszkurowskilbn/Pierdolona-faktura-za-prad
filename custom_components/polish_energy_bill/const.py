"""Stałe integracji Polski Rachunek za Prąd."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "polish_energy_bill"

PLATFORMS: Final = ["sensor", "number", "button"]

# --- klucze config entry (data) ---
CONF_NAME: Final = "name"
CONF_PROFILE: Final = "profile"
CONF_MODE: Final = "mode"                 # "sensor" | "manual"
CONF_ZONE_SENSORS: Final = "zone_sensors" # {zone: entity_id}

# --- klucze options ---
CONF_RATE_OVERRIDES: Final = "rate_overrides"       # {pos_key: float}
CONF_ENABLED_OVERRIDES: Final = "enabled_overrides" # {pos_key: bool}
CONF_BILLING_DAYS: Final = "billing_days"           # int | None (None = auto)
CONF_BILLING_MONTHS: Final = "billing_months"       # float

MODE_SENSOR: Final = "sensor"
MODE_MANUAL: Final = "manual"

DEFAULT_BILLING_MONTHS: Final = 1.0

# klucz przechowywania manualnego zużycia per strefa (number encje)
CONF_MANUAL_CONSUMPTION: Final = "manual_consumption"  # {zone: float}
