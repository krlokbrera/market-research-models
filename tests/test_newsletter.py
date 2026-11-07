"""Synthetic editorial fixtures: no prices, addresses or investment evidence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from market_models.newsletter import (
    SECTIONS, earnings_window, edition_blocks, validate_brief, write_newsletter,
)


def sample():
    return {
        "title": "Edición de prueba",
        "edition_date": "2026-11-09",
        "calendar_anchor": "2026-11-09",
        "cutoff_note": "Ejemplo ficticio; no contiene información de inversión.",
        "sections": {
            key: [{"type": "paragraph", "text": "Texto de prueba para " + label}]
            for key, label in SECTIONS
        },
        "news": [{
            "date": "2026-11-06", "title": "Noticia ficticia",
            "summary": "Hecho de ejemplo.", "reading": "Interpretación de ejemplo.",
            "source_url": "https://example.org/news",
        }],
        "earnings": [{
            "date": day, "company": "Empresa ficticia " + day,
            "period": "Periodo de prueba", "status": "confirmed",
            "focus": "Comprobar hechos y expectativas por separado.",
            "source_url": "https://example.org/results",
        } for day in ("2026-11-09", "2026-11-16", "2026-11-22")],
        "recent_earnings": [],
    }


class NewsletterTests(unittest.TestCase):
    def test_fourteen_inclusive_days_and_two_week_tables(self):
        brief = sample()
        start, end = earnings_window(brief["calendar_anchor"])
        self.assertEqual((end - start).days, 13)
        blocks = list(edition_blocks(brief))
        tables = [b["rows"] for b in blocks if b["type"] == "table"]
        self.assertEqual([len(t) for t in tables], [2, 3])
        self.assertEqual(tables[-1][-1][0], "2026-11-22")
        with self.assertRaises(ValueError):
            earnings_window("2026-11-10")

    def test_thursday_keeps_monday_horizon_and_marks_published(self):
        brief = sample()
        brief["edition_date"] = "2026-11-12"
        brief["earnings"][0]["status"] = "published"
        validate_brief(brief, ".")
        brief["calendar_anchor"] = "2026-11-16"
        with self.assertRaises(ValueError):
            validate_brief(brief, ".")

    def test_weekend_can_preview_the_next_monday(self):
        brief = sample()
        brief["edition_date"] = "2026-11-07"
        validate_brief(brief, ".")
        brief["calendar_anchor"] = "2026-11-23"
        with self.assertRaises(ValueError):
            validate_brief(brief, ".")

    def test_rejects_out_of_horizon_and_future_published_results(self):
        for update in (
            {"date": "2026-11-23"}, {"date": "2026-11-08"},
            {"date": "2026-11-16", "status": "published"},
            {"status": "guessed"},
        ):
            brief = sample()
            brief["earnings"][0].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_brief(brief, ".")
        brief = sample()
        brief["recent_earnings"] = [copy.deepcopy(brief["earnings"][0])]
        brief["recent_earnings"][0].update(date="2026-11-06", status="published")
        validate_brief(brief, ".")
        brief["recent_earnings"][0]["status"] = "provisional"
        with self.assertRaises(ValueError):
            validate_brief(brief, ".")

    def test_required_sections_bounded_lists_and_rectangular_tables(self):
        mutations = [
            lambda b: b["sections"].pop("crypto"),
            lambda b: b.update(news="invalid"),
            lambda b: b.update(earnings=[None]),
            lambda b: b["sections"]["stocks"].append(
                {"type": "table", "rows": [["A", "B"], ["one"]]}),
            lambda b: b["sections"]["stocks"].append(
                {"type": "paragraph", "text": "x", "pdf_only": "yes"}),
        ]
        for change in mutations:
            brief = sample()
            change(brief)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_brief(brief, ".")
        brief = sample()
        brief["news"][0]["date"] = "2026-11-10"
        with self.assertRaises(ValueError):
            validate_brief(brief, ".")

    def test_html_escapes_editorial_text_and_omits_pdf_expansion(self):
        brief = sample()
        brief["sections"]["summary"] = [
            {"type": "paragraph", "text": '<script>alert("x")</script> & texto'},
            {"type": "paragraph", "text": "Detalle exclusivo", "pdf_only": True},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            first = write_newsletter(brief, tmp, Path(tmp) / "outputs")
            second = write_newsletter(brief, tmp, Path(tmp) / "outputs")
            self.assertNotEqual(first, second)
            html = (first / "newsletter.html").read_text(encoding="utf-8")
            self.assertIn("&lt;script&gt;", html)
            self.assertNotIn("<script>", html)
            self.assertNotIn("Detalle exclusivo", html)
            for _, heading in SECTIONS:
                self.assertIn(heading, html)
            self.assertIn("2026-11-22", html)
            manifest = json.loads((first / "manifest.json").read_text())
            self.assertIsNone(manifest["pdf"])
            self.assertNotIn(tmp, json.dumps(manifest))

    def test_rejects_unsafe_sources_and_chart_traversal(self):
        for url in ("javascript:alert(1)", "http://example.org", "https://user:pass@example.org"):
            brief = sample()
            brief["news"][0]["source_url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_brief(brief, ".")
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            (parent / "outside.png").write_bytes(b"placeholder")
            base = parent / "brief"
            base.mkdir()
            brief = sample()
            brief["sections"]["sectors"].append({
                "type": "chart", "path": "../outside.png", "caption": "Fuera de la carpeta",
            })
            with self.assertRaises(ValueError):
                validate_brief(brief, base)


if __name__ == "__main__":
    unittest.main()
