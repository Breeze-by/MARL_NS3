"""Explicit preregistered execution profiles; no automatic profile selection."""
import json
from pathlib import Path

PROFILE_FILES={
    "pace500-clock100-q10ms":"EXECUTION_PROFILE_PACE500_CLOCK100_Q10MS.json",
    "original1000-clock100-q10ms":"EXECUTION_PROFILE_ORIGINAL1000_CLOCK100_Q10MS.json",
    "controlled1000-clock100-q10ms":"EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS.json",
}

def load_profile(identifier):
    if identifier is None:return None
    if identifier not in PROFILE_FILES:raise ValueError("Unknown NET01 execution profile: "+identifier)
    return json.loads((Path(__file__).with_name("config")/PROFILE_FILES[identifier]).read_text())
