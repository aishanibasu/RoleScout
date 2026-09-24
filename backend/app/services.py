"""Generate macOS login agents for the refresh worker and daily backups."""

import argparse
import plistlib
import sys
from pathlib import Path


def write_agents(destination, backend=None, python=None):
    backend = Path(backend or Path(__file__).resolve().parents[1]).resolve()
    python = str(python or sys.executable)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    logs = backend / "data" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    result = []
    for name, module in (("scheduler", "app.scheduler"), ("backup", "app.backup")):
        label = f"local.rolesearcher.{name}"
        config = {
            "Label": label,
            "ProgramArguments": [python, "-m", module],
            "WorkingDirectory": str(backend),
            "RunAtLoad": True,
            "ProcessType": "Background",
            "Umask": 0o077,
            "StandardOutPath": str(logs / f"{name}.log"),
            "StandardErrorPath": str(logs / f"{name}.error.log"),
        }
        if name == "scheduler":
            config.update(KeepAlive=True, ThrottleInterval=60)
        else:
            config["StartCalendarInterval"] = {"Hour": 10, "Minute": 0}
        target = destination / f"{label}.plist"
        target.write_bytes(plistlib.dumps(config))
        result.append(target)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    for path in write_agents(args.destination):
        print(path)
