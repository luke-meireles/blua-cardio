"""
shared/ — camada de ponte entre BluaDiagnostics (chatbot) e CardioMonitor (dashboard).

Reexporta as funções públicas usadas pelos dois apps para que o consumidor
não precise saber de qual módulo interno o símbolo vem.
"""
from .paths import (
    PROFILES_JSON,
    TELEMETRY_CSV,
    GABRIEL_CSV,
    PROJECT_ROOT,
)
from .patient_registry import (
    list_patients,
    get_patient,
    create_patient,
    patient_exists,
    invalidate_caches,
)
from .telemetry_store import (
    load_recent_beats,
    latest_beat,
    window_summary,
    register_alias,
)

__all__ = [
    "PROFILES_JSON", "TELEMETRY_CSV", "GABRIEL_CSV", "PROJECT_ROOT",
    "list_patients", "get_patient", "create_patient",
    "patient_exists", "invalidate_caches",
    "load_recent_beats", "latest_beat", "window_summary", "register_alias",
]
