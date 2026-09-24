import subprocess
import sys


scripts = [
    "src/database_setup.py",
    "src/open5e_import.py",
    "src/environment_enrichment.py"
]


for script in scripts:

    print()
    print("=" * 60)
    print(f"Running: {script}")
    print("=" * 60)
    print()

    result = subprocess.run(
        [sys.executable, script]
    )

    if result.returncode != 0:

        print()
        print(f"FAILED: {script}")
        print("Database build stopped.")

        sys.exit(result.returncode)


print()
print("=" * 60)
print("DATABASE BUILD COMPLETE")
print("=" * 60)