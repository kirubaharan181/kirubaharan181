import importlib.util
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("updater", ROOT / "scripts" / "update_readme_activity.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)

SAMPLE = json.loads((ROOT / "tests" / "fixtures" / "public_repos.json").read_text(encoding="utf-8"))
USER = "kirubaharan181"
EXCLUDE = set(updater.DEFAULT_EXCLUDE)


def repo(name, pushed_at="2026-01-01T00:00:00Z", **extra):
    base = {"name": name, "pushed_at": pushed_at, "fork": False, "archived": False, "private": False}
    base.update(extra)
    return base


class SelectTests(unittest.TestCase):
    def test_sorted_newest_first_and_limited(self):
        chosen = updater.select(SAMPLE, EXCLUDE, 5)
        self.assertEqual(
            [r["name"] for r in chosen],
            [
                "sdlc-agentic-skills",
                "Scoodemy__An-E-Learning-Platform",
                "buildwithgemini-tn-workout-coach",
                "Wool_Management",
                "kiruba-portfolio",
            ],
        )

    def test_filters_forks_archived_private_and_excluded(self):
        repos = [
            repo("keep-me", "2026-02-01T00:00:00Z"),
            repo("a-fork", "2026-03-01T00:00:00Z", fork=True),
            repo("old", "2026-03-02T00:00:00Z", archived=True),
            repo("secret", "2026-03-03T00:00:00Z", private=True),
            repo("SK", "2026-03-04T00:00:00Z"),
            repo("never-pushed", None),
        ]
        self.assertEqual([r["name"] for r in updater.select(repos, EXCLUDE, 10)], ["keep-me"])


class RenderTests(unittest.TestCase):
    def test_date_format_is_plain_and_has_no_placeholders(self):
        self.assertEqual(updater.format_date("2026-11-03T10:31:29Z"), "03 Nov 2026")
        table = updater.render(updater.select(SAMPLE, EXCLUDE, 5), USER)
        self.assertNotRegex(table, r"\bYYYY\b|\$date|\{\{|MMM")

    def test_links_point_at_the_owner(self):
        table = updater.render([repo("demo")], USER)
        self.assertIn("[demo](https://github.com/kirubaharan181/demo)", table)


class ReplaceTests(unittest.TestCase):
    def test_replaces_only_between_markers_and_is_idempotent(self):
        text = f"before\n{updater.START}\nold\n{updater.END}\nafter\n"
        once = updater.replace_section(text, "NEW")
        self.assertEqual(once, f"before\n{updater.START}\nNEW\n{updater.END}\nafter\n")
        self.assertEqual(updater.replace_section(once, "NEW"), once)

    def test_missing_markers_raise(self):
        with self.assertRaises(ValueError):
            updater.replace_section("no markers here", "x")


class ReadmeConsistencyTests(unittest.TestCase):
    def test_committed_table_matches_what_the_script_renders(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        committed = re.search(re.escape(updater.START) + r"\n(.*?)\n" + re.escape(updater.END), readme, re.DOTALL).group(1)
        self.assertEqual(committed, updater.render(updater.select(SAMPLE, EXCLUDE, 5), USER))


if __name__ == "__main__":
    unittest.main()
