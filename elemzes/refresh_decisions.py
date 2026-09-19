"""Refresh old candidates and combine with screen_current.py output.

PYTHONPATH=. python elemzes/refresh_decisions.py
Then rebuild via build_decision_report.py. Uses the normal six-hour cache.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from porcelan.httpclient import HttpClient
from porcelan.parsing import parse_listing


def main():
    target = Path("riport/decision-evidence.json")
    evidence = json.loads(target.read_text())
    client = HttpClient()
    for row in evidence["previous_candidates"]:
        html = client.get(row["url"])
        row["fresh"] = parse_listing(row["url"], html or "")
        if html:
            text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
            desc = re.search(r"Eladó leírása a termékről (.*?) Szállítási feltételek", text)
            if desc:
                row["fresh"]["description"] = desc.group(1)[:2000]
            cache = client._cache_path(row["url"])
            row["fetched_at"] = datetime.fromtimestamp(cache.stat().st_mtime, timezone.utc).isoformat()
            row["html_sha256"] = hashlib.sha256(html.encode()).hexdigest()
        else:
            row["fetched_at"] = None
            row["html_sha256"] = None
    evidence["screen"] = json.loads(Path("out/review/screened.json").read_text())
    evidence["checked_at"] = datetime.now(timezone.utc).isoformat()
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
