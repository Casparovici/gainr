"""Fails when a service module's test coverage drops below the floor (CLAUDE.md: financial
calculation code stays above 80%). Reads the JSON report pytest-cov writes, run in CI:

    pytest --cov=app/services --cov-report=json
    python -m scripts.check_coverage coverage.json

Every app/services module counts, so a new one is covered by the rule the day it's added. The
`*_provider.py` adapters don't: they wrap outside services (Yahoo, banks, Picnic) whose responses
are recorded fixtures at best, and hold no calculation of their own.
"""

import json
import sys
from pathlib import PurePosixPath

FLOOR = 80.0
EXEMPT_SUFFIX = "_provider.py"


def below_floor(report: dict, floor: float = FLOOR) -> list[tuple[str, float]]:
    shortfalls = []
    for path, data in report.get("files", {}).items():
        name = PurePosixPath(path.replace("\\", "/"))
        if "services" not in name.parts or name.name == "__init__.py" or name.name.endswith(EXEMPT_SUFFIX):
            continue
        percent = data["summary"]["percent_covered"]
        if percent < floor:
            shortfalls.append((str(name), percent))
    return sorted(shortfalls)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[0], encoding="utf-8") as f:
        shortfalls = below_floor(json.load(f))
    for name, percent in shortfalls:
        print(f"{name}: {percent:.1f}% covered, below the {FLOOR:.0f}% floor")
    if not shortfalls:
        print(f"Every service module is at least {FLOOR:.0f}% covered (providers exempt).")
    return 1 if shortfalls else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
