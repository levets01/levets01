"""Refresh a public GitHub snapshot, retaining the last good data on failure."""
import argparse
from collections import Counter
from datetime import date
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = "levets01"
API = "https://api.github.com"
SNAPSHOT = ROOT / "data/github_stats.json"
FEATURED = {
    "backeng_node": ("Backend API with a PostgreSQL database.", "TypeScript · Express · PostgreSQL · Docker"),
    "CONTROL_IVENTARIO-RIWI": ("Inventory management exercise from Riwi.", "Python"),
    "SALES-CONTROL_Riwi": ("Sales management exercise from Riwi.", "Python"),
}


def download(url: str) -> str:
    headers = {"User-Agent": "levets01-profile-generator"}
    if url.startswith(API + "/"):
        headers["Accept"] = "application/vnd.github+json"
        if token := os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                return response.read().decode("utf-8")
        except HTTPError as error:
            retry = error.code >= 500 or error.code == 429
            if not retry or attempt == 2:
                raise
            delay = error.headers.get("Retry-After", "")
            time.sleep(min(int(delay), 10) if delay.isdigit() else 2 ** attempt)
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("GitHub request exhausted retries")


class CalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: dict[str, int] = {}
        self.total: int | None = None
        self.capture = False
        self.heading: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "td" and values.get("data-date") and values.get("data-level"):
            day = date.fromisoformat(values["data-date"]).isoformat()
            level = int(values["data-level"])
            if not 0 <= level <= 4:
                raise ValueError("Unexpected GitHub calendar level")
            self.days[day] = level
        if tag == "h2" and values.get("id") in {
            "contribution-graph-heading", "js-contribution-activity-description"
        }:
            self.capture = True
            self.heading.clear()

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self.capture:
            self.capture = False
            if match := re.search(r"([\d,]+)\s+contributions?\b", " ".join(self.heading)):
                self.total = int(match[1].replace(",", ""))

    def handle_data(self, content: str) -> None:
        if self.capture:
            self.heading.append(content)


def calendar_snapshot(html: str) -> dict:
    parser = CalendarParser()
    parser.feed(html)
    if not 350 <= len(parser.days) <= 371:
        raise ValueError("GitHub contribution calendar is incomplete")
    first, last = (date.fromisoformat(day) for day in (min(parser.days), max(parser.days)))
    if (last - first).days + 1 != len(parser.days):
        raise ValueError("GitHub contribution calendar has missing dates")
    return {"days": dict(sorted(parser.days.items())), "total": parser.total}


def repository_snapshot(user: dict, repos: list[dict]) -> dict:
    owned = [repo for repo in repos if not repo["fork"]]
    languages = Counter(repo["language"] for repo in owned if repo["language"])
    by_name = {repo["name"]: repo for repo in repos}
    return {
        "public_repos": user["public_repos"],
        "followers": user["followers"],
        "stars": sum(repo["stargazers_count"] for repo in owned),
        "languages": dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
        "projects": [
            {"name": name, "description": description, "stack": stack,
             "url": by_name[name]["html_url"], "stars": by_name[name]["stargazers_count"]}
            for name, (description, stack) in FEATURED.items() if name in by_name
        ],
    }


def activity_snapshot(events: list[dict]) -> list[dict]:
    return [{"type": event["type"], "repo": event["repo"]["name"],
             "date": event["created_at"][:10]} for event in events[:3]]


def refresh(snapshot: dict) -> dict:
    prefix = f"{API}/users/{ACCOUNT}"

    def repositories() -> dict:
        user = json.loads(download(prefix))
        repos = []
        for page in range(1, 101):
            batch = json.loads(download(f"{prefix}/repos?type=owner&per_page=100&page={page}"))
            repos.extend(batch)
            if len(batch) < 100:
                return repository_snapshot(user, repos)
        raise ValueError("GitHub repository pagination limit reached")

    sources = {
        "repositories": repositories,
        "activity": lambda: activity_snapshot(json.loads(download(f"{prefix}/events/public?per_page=10"))),
        "calendar": lambda: calendar_snapshot(download(f"https://github.com/users/{ACCOUNT}/contributions")),
    }
    for key, loader in sources.items():
        try:
            snapshot[key] = loader()
        except (URLError, TimeoutError, ValueError, KeyError, TypeError) as error:
            print(f"{key}: {error}; retaining last available snapshot", file=sys.stderr)
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, help="Import verified HTTP responses from a local folder")
    args = parser.parse_args()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
    if args.seed:
        def read(name: str) -> str:
            return (args.seed / name).read_text(encoding="utf-8")

        snapshot = {
            "repositories": repository_snapshot(json.loads(read("github-user.tmp.json")),
                                                json.loads(read("github-repos.tmp.json"))),
            "activity": activity_snapshot(json.loads(read("github-events.tmp.json"))),
            "calendar": calendar_snapshot(read("github-calendar.tmp.html")),
        }
    else:
        snapshot = refresh(snapshot)
    SNAPSHOT.parent.mkdir(exist_ok=True)
    replacement = SNAPSHOT.with_suffix(".tmp.json")
    replacement.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    replacement.replace(SNAPSHOT)


if __name__ == "__main__":
    main()
