"""Project-wide configuration for the Hamartia backend."""

from pathlib import Path

# All persistent JSON lives here. Kept in one place so routers and services
# always point at the same datastore.
# Datastore lives directly under backend/ (per the project layout), not under app/.
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Allowed mistake-tag taxonomy shared by the API, the AI service, and the UI.
HAMARTIA_TAGS = [
    "[Distractor Trap]",
    "[Knowledge Gap]",
    "[Reading Slip]",
    "[Time Panic]",
]

# Cosmos sector identifiers (fog-of-war map zones).
COSMOS_SECTORS = ["sector_0", "sector_1", "sector_2", "sector_3"]
