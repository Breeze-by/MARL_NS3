"""Explicit preregistered execution profiles; no automatic profile selection."""
import json
from pathlib import Path

PROFILE_FILES={
    "pace500-clock100-q10ms":"EXECUTION_PROFILE_PACE500_CLOCK100_Q10MS.json",
    "original1000-clock100-q10ms":"EXECUTION_PROFILE_ORIGINAL1000_CLOCK100_Q10MS.json",
    "controlled1000-clock100-q10ms":"EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS.json",
    "controlled1000-clock100-q10ms-pace10":"EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE10.json",
    "controlled1000-clock100-q10ms-pace10-clocklane":"EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE10_CLOCKLANE.json",
    "controlled1000-clock100-q10ms-pace10-clocklane-raster":"EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE10_CLOCKLANE_RASTER.json",
    "controlled1000-clock100-q10ms-pace10-raster":"EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE10_RASTER.json",
    "controlled1000-clock100-q10ms-pace10-raster-simhealth":"EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE10_RASTER_SIMHEALTH.json",
    "controlled1000-clock100-q10ms-pace20-raster-simhealth":"EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE20_RASTER_SIMHEALTH.json",
}
CONTROLLED_PROFILE_IDS=("controlled1000-clock100-q10ms","controlled1000-clock100-q10ms-pace10",
    "controlled1000-clock100-q10ms-pace10-clocklane",
    "controlled1000-clock100-q10ms-pace10-clocklane-raster",
    "controlled1000-clock100-q10ms-pace10-raster",
    "controlled1000-clock100-q10ms-pace10-raster-simhealth",
    "controlled1000-clock100-q10ms-pace20-raster-simhealth")

def load_profile(identifier):
    if identifier is None:return None
    if identifier not in PROFILE_FILES:raise ValueError("Unknown NET01 execution profile: "+identifier)
    return json.loads((Path(__file__).with_name("config")/PROFILE_FILES[identifier]).read_text())
