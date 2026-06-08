"""Izolacja testów rdzenia: importujemy pakiet `core` bez ładowania Home Assistant.

Rdzeń kalkulatora jest celowo niezależny od HA, więc testy importują go
bezpośrednio (`from core import ...`), z pominięciem warstwy integracji.
"""

import pathlib
import sys

_CORE_PARENT = (
    pathlib.Path(__file__).parent.parent
    / "custom_components"
    / "polish_energy_bill"
)
sys.path.insert(0, str(_CORE_PARENT))
