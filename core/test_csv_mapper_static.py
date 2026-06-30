from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CsvMapperStaticTests(SimpleTestCase):
    def test_header_toggle_rechecks_saved_profiles(self) -> None:
        mapper_js = (PROJECT_ROOT / "static/js/csv_mapper.js").read_text(encoding="utf-8")

        self.assertIn("async _onHeaderToggle(card)", mapper_js)
        self.assertIn("await this._checkProfiles();", mapper_js)
