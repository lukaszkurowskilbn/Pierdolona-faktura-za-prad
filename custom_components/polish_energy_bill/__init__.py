"""Integracja Polski Rachunek za Prąd."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_PROFILE, DOMAIN, PLATFORMS
from .coordinator import BillCoordinator
from .core import ProfileError, load_builtin_profiles

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Konfiguracja wpisu integracji."""
    profile_key = entry.data[CONF_PROFILE]

    # Wczytanie profili to operacja I/O — wykonujemy poza pętlą zdarzeń.
    try:
        profiles = await hass.async_add_executor_job(load_builtin_profiles)
    except ProfileError as err:
        raise ConfigEntryError(f"Błąd profilu taryfowego: {err}") from err

    base_profile = profiles.get(profile_key)
    if base_profile is None:
        raise ConfigEntryError(f"Nieznany profil taryfowy: {profile_key}")

    coordinator = BillCoordinator(hass, entry, base_profile)
    # Pierwsze odświeżenie po dodaniu encji (number muszą najpierw wnieść stawki),
    # więc nie wymuszamy refresh tutaj — zrobi to platforma number po starcie.

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Usunięcie wpisu integracji."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Przeładowanie po zmianie opcji (sensory, billing, włączone pozycje)."""
    await hass.config_entries.async_reload(entry.entry_id)
