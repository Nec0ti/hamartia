"""Project-wide configuration for the Hamartia backend."""

import os
from pathlib import Path

# All persistent JSON lives here. HAMARTIA_DATA_DIR lets tests and portable
# installs use an isolated directory; the default stays under backend/.
DATA_DIR = Path(os.environ.get("HAMARTIA_DATA_DIR", Path(__file__).resolve().parent.parent.parent / "data"))

# Allowed mistake-tag taxonomy shared by the API, the AI service, and the UI.
HAMARTIA_TAGS = [
    "[Distractor Trap]",
    "[Knowledge Gap]",
    "[Reading Slip]",
    "[Time Panic]",
]

# Cosmos sector identifiers (fog-of-war map zones).
COSMOS_SECTORS = ["sector_0", "sector_1", "sector_2", "sector_3"]
