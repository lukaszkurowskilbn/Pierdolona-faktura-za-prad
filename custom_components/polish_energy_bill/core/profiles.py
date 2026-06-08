"""Ładowanie i walidacja profili taryfowych z plików YAML.

Profile leżą w pakiecie (core/profiles_data/*.yaml). Loader nie zależy od HA
i nadaje się do testów oraz do uruchomienia poza Home Assistant.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Group, TariffProfile, Unit, Zone

PROFILES_DIR = Path(__file__).parent / "profiles_data"

_VALID_UNITS = {u.value for u in Unit}
_VALID_GROUPS = {g.value for g in Group}
_VALID_ZONES = {z.value for z in Zone}


class ProfileError(ValueError):
    """Błąd struktury/zawartości profilu."""


def _validate(data: dict, source: str) -> None:
    for required in ("key", "tariff", "positions"):
        if required not in data:
            raise ProfileError(f"{source}: brak wymaganego pola '{required}'")

    if not data["positions"]:
        raise ProfileError(f"{source}: pusta lista 'positions'")

    seen: set[str] = set()
    for i, pos in enumerate(data["positions"]):
        where = f"{source} pozycja[{i}]"
        for required in ("key", "unit", "rate"):
            if required not in pos:
                raise ProfileError(f"{where}: brak pola '{required}'")
        if pos["key"] in seen:
            raise ProfileError(f"{where}: zduplikowany key '{pos['key']}'")
        seen.add(pos["key"])
        if pos["unit"] not in _VALID_UNITS:
            raise ProfileError(f"{where}: nieznana unit '{pos['unit']}'")
        if pos.get("group", "other") not in _VALID_GROUPS:
            raise ProfileError(f"{where}: nieznana group '{pos['group']}'")
        if pos.get("zone", "all") not in _VALID_ZONES:
            raise ProfileError(f"{where}: nieznana zone '{pos['zone']}'")


def load_profile_file(path: Path) -> TariffProfile:
    """Wczytuje i waliduje pojedynczy profil."""
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ProfileError(f"{path.name}: plik nie jest mapą YAML")
    _validate(data, path.name)
    return TariffProfile.from_dict(data)


def load_builtin_profiles(directory: Path | None = None) -> dict[str, TariffProfile]:
    """Wczytuje wszystkie profile z katalogu. Klucz = profile.key."""
    directory = directory or PROFILES_DIR
    profiles: dict[str, TariffProfile] = {}
    for path in sorted(directory.glob("*.yaml")):
        profile = load_profile_file(path)
        if profile.key in profiles:
            raise ProfileError(f"Zduplikowany klucz profilu '{profile.key}'")
        profiles[profile.key] = profile
    return profiles
