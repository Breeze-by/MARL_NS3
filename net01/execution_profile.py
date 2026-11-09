"""The one preregistered NET01 wall/clock execution profile; old default retained."""
import json
from pathlib import Path

PROFILE_ID="pace500-clock100-q10ms"

def load_profile(identifier):
    if identifier is None:return None
    if identifier!=PROFILE_ID:raise ValueError("Unknown NET01 execution profile: "+identifier)
    return json.loads((Path(__file__).with_name("config")/"EXECUTION_PROFILE_PACE500_CLOCK100_Q10MS.json").read_text())
