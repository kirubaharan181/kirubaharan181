#!/usr/bin/env python3
"""Refresh the "recently updated repositories" table in README.md.

Only public, non-fork, non-archived repositories are listed, taken from the
GitHub REST API and sorted by last push. Standard library only.

    GITHUB_USER=kirubaharan181 python3 scripts/update_readme_activity.py
    python3 scripts/update_readme_activity.py --input-json tests/fixtures/public_repos.json --dry-run

If the API call fails or the markers are missing, README.md is left untouched
and the script exits non-zero, so the workflow fails visibly instead of
publishing a broken section.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime

START = "<!--START_SECTION:recent-repos-->"
END = "<!--END_SECTION:recent-repos-->"
DEFAULT_EXCLUDE = ("kirubaharan181", "kirubaharan181.github.io", "sk")
DEFAULT_LIMIT = 5


def fetch_repos(user: str, token: str | None = None) -> list[dict]:
    url = f"https://api.github.com/users/{user}/repos?per_page=100&sort=pushed&type=owner"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (fixed https URL)
        return json.load(response)


def select(repos: list[dict], exclude: set[str], limit: int) -> list[dict]:
    excluded = {name.lower() for name in exclude}
    keep = [
        repo
        for repo in repos
        if not repo.get("fork")
        and not repo.get("archived")
        and not repo.get("private")
        and repo.get("name", "").lower() not in excluded
        and repo.get("pushed_at")
    ]
    keep.sort(key=lambda repo: repo["pushed_at"], reverse=True)
    return keep[:limit]


def format_date(timestamp: str) -> str:
    return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").strftime("%d %b %Y")


def render(repos: list[dict], user: str) -> str:
    lines = ["| Repository | Last updated |", "|---|---|"]
    for repo in repos:
        name = repo["name"]
        lines.append(f"| [{name}](https://github.com/{user}/{name}) | {format_date(repo['pushed_at'])} |")
    return "\n".join(lines)


def replace_section(text: str, body: str) -> str:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"markers {START} / {END} not found in README")
    return pattern.sub(lambda _match: f"{START}\n{body}\n{END}", text, count=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--readme", default="README.md")
    parser.add_argument("--user", default=os.environ.get("GITHUB_USER", "kirubaharan181"))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--input-json", help="read repositories from a JSON file instead of the API (tests)")
    parser.add_argument("--dry-run", action="store_true", help="print the table, do not write README")
    args = parser.parse_args(argv)

    exclude = set(filter(None, os.environ.get("RECENT_REPOS_EXCLUDE", "").split(","))) or set(DEFAULT_EXCLUDE)

    try:
        if args.input_json:
            with open(args.input_json, encoding="utf-8") as handle:
                repos = json.load(handle)
        else:
            repos = fetch_repos(args.user, os.environ.get("GITHUB_TOKEN"))
    except Exception as error:  # network, HTTP or JSON problem: fail loudly, change nothing
        print(f"error: could not load repositories: {error}", file=sys.stderr)
        return 1

    chosen = select(repos, exclude, args.limit)
    if not chosen:
        print("error: no eligible repositories found; README left unchanged", file=sys.stderr)
        return 1

    table = render(chosen, args.user)
    if args.dry_run:
        print(table)
        return 0

    with open(args.readme, encoding="utf-8") as handle:
        original = handle.read()
    try:
        updated = replace_section(original, table)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if updated == original:
        print("README already up to date")
        return 0
    with open(args.readme, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
    print(f"README updated with {len(chosen)} repositories")
    return 0


if __name__ == "__main__":
    sys.exit(main())
