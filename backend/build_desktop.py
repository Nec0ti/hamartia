"""Build the platform-native desktop API sidecar with PyInstaller."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_INDEX = ROOT / "frontend" / "dist" / "index.html"
SPEC = ROOT / "backend" / "hamartia-backend.spec"


def main():
    if not FRONTEND_INDEX.is_file():
        raise SystemExit("Build the frontend first: cd frontend && npm run build")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(ROOT / "backend" / "dist"),
            "--workpath",
            str(ROOT / "backend" / "build"),
            str(SPEC),
        ],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
