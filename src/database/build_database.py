"""Build the local database and optionally import the tactical workbook."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DEPENDENCIES_DIR = Path(__file__).resolve().parent / "dependencies"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Encounter Forge's database.")
    parser.add_argument(
        "--tactical-workbook",
        type=Path,
        help="Optional path to Encounter_Forge_Tactical_Dataset_v0_3_book_anchored.xlsx",
    )
    return parser.parse_args()


def run(script: Path, *arguments: str) -> None:
    print(f"Running: {script.relative_to(ROOT_DIR)}")
    subprocess.run([sys.executable, str(script), *arguments], cwd=ROOT_DIR, check=True)


def main() -> None:
    args = parse_args()
    run(DEPENDENCIES_DIR / "database_setup.py")
    run(DEPENDENCIES_DIR / "open5e_import.py")
    run(DEPENDENCIES_DIR / "environment_enrichment.py")
    if args.tactical_workbook:
        run(DEPENDENCIES_DIR / "tactical_dataset_import.py", str(args.tactical_workbook))
    print("Database build complete.")


if __name__ == "__main__":
    main()
