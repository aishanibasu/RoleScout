"""Run a real API with a disposable database, never the user's job index."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn

from app.collect import collect
from app.main import create_app
from app.point72 import normalize


def main():
    with tempfile.TemporaryDirectory(prefix="role-searcher-e2e-") as directory:
        path = Path(directory) / "jobs.sqlite3"
        jobs = [
            normalize(
                {
                    "job": {
                        "Job_Code__c": f"E2E-{i}",
                        "Name": f"Research Analyst {i:02d}",
                        "Job_Description_External__c": (
                            "<p>Bachelor's degree in Mathematics required.</p>"
                            if i == 3
                            else "<p>Bachelor's degree in Neuroscience required.</p>"
                            if i == 4
                            else "<p>Research investments. Bachelor's degree in Economics required.</p>"
                        ),
                        "Apply_Now_URL__c": f"https://example.com/jobs/{i}",
                    },
                    "formattedLocation": "New York",
                }
            )
            for i in range(240)
        ]
        today = datetime.now(timezone.utc).date()
        for index, days in ((0, 3), (1, 30), (2, -2)):
            jobs[index]["description"] += f" Applications close on {today + timedelta(days=days)}."
        gs_job = dict(
            jobs.pop(5),
            company="Goldman Sachs",
            external_id="183697_GS_MID_CAREER",
            url="https://higher.gs.com/roles/183697_GS_MID_CAREER",
            locations=[
                {
                    "city": "New York",
                    "region": "NY",
                    "country": "United States",
                    "raw": "New York, NY",
                }
            ],
        )
        collect(path, lambda: jobs)
        collect(path, lambda: [gs_job], source_id="gs")
        uvicorn.run(create_app(path), host="127.0.0.1", port=8011)


if __name__ == "__main__":
    main()
