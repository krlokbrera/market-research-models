"""Private editorial briefs -> consistent newsletter HTML and paginated PDF.

No market-data fetching, email transport, scheduling, or investment orders.
"""
import argparse
import html
import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

SECTIONS = (
    ("summary", "Resumen ejecutivo"),
    ("market", "01 / Panorama y cambios"),
    ("flows", "02 / Flujos y posicionamiento"),
    ("sectors", "03 / ETF y rotación sectorial"),
    ("stocks", "04 / Acciones en seguimiento"),
    ("simulations", "05 / Simulaciones de modelo"),
    ("crypto", "06 / Criptoactivos y custodia"),
    ("agenda", "07 / Agenda y riesgos"),
    ("news", "08 / Noticias relevantes"),
    ("earnings", "09 / Resultados publicados y próximos 14 días"),
)
STATUSES = {"confirmed": "Confirmada", "provisional": "Provisional",
            "published": "Publicada"}


def parse_date(value):
    if not isinstance(value, str):
        raise ValueError("Dates must be YYYY-MM-DD strings")
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError("Dates must use YYYY-MM-DD")
    return result


def earnings_window(monday):
    """Fourteen calendar days, including the anchor Monday and next Sunday."""
    start = parse_date(monday)
    if start.weekday() != 0:
        raise ValueError("The earnings anchor must be a Monday")
    return start, start + timedelta(days=13)


def text(value, maximum=16000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("Expected bounded, nonempty editorial text")
    return value


def source_url(value):
    parsed = urlsplit(text(value, 2048))
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or any(c.isspace() for c in value)):
        raise ValueError("Sources must be HTTPS URLs without credentials")
    return value


def chart_path(value, base):
    root = Path(base).resolve()
    candidate = (root / text(value, 500)).resolve(strict=True)
    if (not candidate.is_relative_to(root) or not candidate.is_file()
            or candidate.suffix.lower() not in {".png", ".jpg", ".jpeg"}):
        raise ValueError("Charts must be local PNG/JPEG files inside the brief directory")
    return candidate


def cell_text(value):
    if isinstance(value, dict) and set(value) <= {"text", "url"}:
        result = text(value.get("text"), 2000)
        if "url" in value:
            source_url(value["url"])
        return result
    return text(value, 2000)


def validate_brief(brief, base):
    if not isinstance(brief, dict):
        raise ValueError("The brief must be an object")
    asof = parse_date(brief.get("edition_date"))
    start, end = earnings_window(brief.get("calendar_anchor"))
    current = asof - timedelta(days=asof.weekday())
    preview = asof.weekday() >= 5 and start == current + timedelta(days=7)
    if start != current and not preview:
        raise ValueError("Anchor must be this week's Monday, or next Monday for weekend previews")
    text(brief.get("title"), 180)
    text(brief.get("cutoff_note"), 1000)
    sections = brief.get("sections")
    if not isinstance(sections, dict) or set(sections) != {k for k, _ in SECTIONS}:
        raise ValueError("All ten fixed section keys are required")
    for blocks in sections.values():
        if not isinstance(blocks, list) or len(blocks) > 100:
            raise ValueError("Each section must contain a bounded block list")
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") not in {
                    "paragraph", "subheading", "table", "chart"}:
                raise ValueError("Unknown editorial block")
            if not isinstance(block.get("pdf_only", False), bool):
                raise ValueError("pdf_only must be boolean")
            kind = block["type"]
            if kind in {"paragraph", "subheading"}:
                text(block.get("text"))
                if "source_url" in block:
                    source_url(block["source_url"])
            elif kind == "chart":
                chart_path(block.get("path"), base)
                text(block.get("caption"), 2000)
            else:
                rows = block.get("rows")
                if (not isinstance(rows, list) or not 2 <= len(rows) <= 101
                        or not isinstance(rows[0], list) or not 1 <= len(rows[0]) <= 8):
                    raise ValueError("Tables need a header and 1..100 data rows, with 1..8 columns")
                for row in rows:
                    if not isinstance(row, list) or len(row) != len(rows[0]):
                        raise ValueError("Tables must be rectangular")
                    for value in row:
                        cell_text(value)
    news = brief.get("news", [])
    if not isinstance(news, list) or len(news) > 100:
        raise ValueError("News must be a bounded list")
    for item in news:
        if not isinstance(item, dict):
            raise ValueError("Each news item must be an object")
        if parse_date(item.get("date")) > asof:
            raise ValueError("News cannot describe future events as published facts")
        for key in ("title", "summary", "reading"):
            text(item.get(key))
        source_url(item.get("source_url"))
    for key in ("earnings", "recent_earnings"):
        items = brief.get(key, [])
        if not isinstance(items, list) or len(items) > 100:
            raise ValueError("Earnings must be a bounded list")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Each earnings item must be an object")
            event_date = parse_date(item.get("date"))
            if key == "earnings" and not start <= event_date <= end:
                raise ValueError("Earnings date outside the 14-day horizon")
            if key == "recent_earnings" and not start - timedelta(days=14) <= event_date < start:
                raise ValueError("Recent results must precede the anchor, within 14 days")
            if item.get("status") not in STATUSES:
                raise ValueError("Unrecognized earnings status")
            if item["status"] == "published" and event_date > asof:
                raise ValueError("Future results cannot be labelled published")
            if key == "recent_earnings" and item["status"] != "published":
                raise ValueError("Recent results require published status")
            for field in ("company", "period", "focus"):
                text(item.get(field), 2000)
            source_url(item["source_url"])
    return brief


def calendar_rows(items):
    rows = [["Fecha", "Empresa", "Periodo fiscal", "Estado", "Qué observar"]]
    for item in sorted(items, key=lambda r: (r["date"], r["company"])):
        rows.append([item["date"],
                     {"text": item["company"], "url": item["source_url"]},
                     item["period"], STATUSES[item["status"]], item["focus"]])
    return rows


def edition_blocks(brief):
    start, end = earnings_window(brief["calendar_anchor"])
    yield {"type": "title", "text": brief["title"]}
    yield {"type": "paragraph", "text": brief["edition_date"] + " | " + brief["cutoff_note"]}
    for key, heading in SECTIONS:
        yield {"type": "section", "text": heading}
        yield from brief["sections"][key]
        if key == "news":
            for item in brief.get("news", []):
                yield {"type": "subheading", "text": item["date"] + " | " + item["title"],
                       "source_url": item["source_url"]}
                yield {"type": "paragraph", "text": item["summary"]}
                yield {"type": "paragraph", "text": "Lectura: " + item["reading"]}
        if key == "earnings":
            yield {"type": "paragraph", "text": (
                f"Horizonte: {start.isoformat()} a {end.isoformat()}, ambos inclusive. "
                "Publicaciones previstas; las fechas provisionales pueden cambiar.")}
            recent = brief.get("recent_earnings", [])
            if recent:
                yield {"type": "subheading", "text": "Resultados ya publicados"}
                yield {"type": "table", "rows": calendar_rows(recent)}
            for offset in (0, 7):
                first = start + timedelta(days=offset)
                last = first + timedelta(days=6)
                yield {"type": "subheading", "text": f"Semana {first} a {last}"}
                items = [r for r in brief.get("earnings", [])
                         if first <= parse_date(r["date"]) <= last]
                if items:
                    yield {"type": "table", "rows": calendar_rows(items)}
                else:
                    yield {"type": "paragraph", "text": (
                        "No hay publicaciones verificadas incluidas para esta semana; "
                        "la ausencia no demuestra que no existan otras.")}


def markup_cell(value):
    value_text = html.escape(cell_text(value))
    if isinstance(value, dict) and "url" in value:
        return f'<a href="{html.escape(value["url"], quote=True)}">{value_text}</a>'
    return value_text


def render_html(brief, assets):
    pieces = ['<!doctype html><html lang="es"><meta charset="utf-8"><body '
              'style="margin:0;background:#F3F3F3"><main style="max-width:760px;'
              'margin:auto;padding:30px;background:white;font-family:Georgia,serif;'
              'font-size:16px;line-height:1.65;color:#404040">']
    chart = 0
    for block in edition_blocks(brief):
        if block.get("pdf_only"):
            continue
        kind = block["type"]
        if kind == "table":
            pieces.append('<table style="width:100%;border-collapse:collapse;font-size:13px">')
            for i, row in enumerate(block["rows"]):
                tag = "th" if i == 0 else "td"
                color = "background:#D04A02;color:white" if i == 0 else "border-bottom:1px solid #DDD"
                pieces.append("<tr>" + "".join(
                    f'<{tag} style="padding:8px;text-align:left;vertical-align:top;{color}">'
                    + markup_cell(c) + f"</{tag}>" for c in row) + "</tr>")
            pieces.append("</table>")
        elif kind == "chart":
            asset = assets[chart]
            chart += 1
            pieces.append(f'<img src="cid:{asset["content_id"]}" alt="{html.escape(block["caption"], quote=True)}" '
                          'style="width:100%;height:auto">')
            pieces.append("<p>" + html.escape(block["caption"]) + "</p>")
        else:
            tag = {"title": "h1", "section": "h2", "subheading": "h3"}.get(kind, "p")
            value = html.escape(block["text"]).replace("\n", "<br>")
            if "source_url" in block:
                value = f'<a href="{html.escape(block["source_url"], quote=True)}">{value}</a>'
            style = ' style="color:#D04A02"' if kind in {"title", "section"} else ""
            pieces.append(f"<{tag}{style}>{value}</{tag}>")
    return "".join(pieces) + "</main></body></html>"


def render_pdf(brief, base, target, fonts):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate,
                                   Spacer, Table, TableStyle)
    for label, path in zip(("ReportBody", "ReportBold", "ReportItalic"), fonts):
        pdfmetrics.registerFont(TTFont(label, str(path)))
    pdfmetrics.registerFontFamily("ReportBody", normal="ReportBody",
                                  bold="ReportBold", italic="ReportItalic")
    styles = {}
    for name, size, leading, font, color in (
        ("paragraph", 11.5, 15.5, "ReportBody", "#404040"),
        ("title", 23, 28, "ReportBold", "#D04A02"),
        ("section", 15, 19, "ReportBold", "#D04A02"),
        ("subheading", 12.5, 16, "ReportBold", "#404040"),
        ("caption", 9.5, 12, "ReportItalic", "#6D6E71"),
        ("cell", 10, 13, "ReportBody", "#404040"),
        ("head", 10, 13, "ReportBold", "#FFFFFF"),
    ):
        styles[name] = ParagraphStyle(name, fontName=font, fontSize=size, leading=leading,
                                      textColor=colors.HexColor(color), spaceAfter=8,
                                      keepWithNext=name in {"section", "subheading"})
    flow = []
    for block in edition_blocks(brief):
        kind = block["type"]
        if kind == "table":
            rows = [[Paragraph(markup_cell(c), styles["head" if i == 0 else "cell"])
                     for c in row] for i, row in enumerate(block["rows"])]
            count = len(rows[0])
            weights = {3: [160, 120, 243], 5: [55, 125, 75, 70, 198],
                       7: [175, 58, 58, 58, 58, 58, 58]}.get(count, [523/count]*count)
            table = Table(rows, colWidths=weights, repeatRows=1, splitByRow=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D04A02")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F3F3")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), .25, colors.HexColor("#DDDDDD")),
            ]))
            flow.append(table)
            flow.append(Spacer(1, 8))
        elif kind == "chart":
            path = chart_path(block["path"], base)
            width, height = ImageReader(str(path)).getSize()
            scale = min(523/width, 300/height)
            flow.append(KeepTogether([Image(str(path), width*scale, height*scale),
                                      Paragraph(html.escape(block["caption"]), styles["caption"])]))
        else:
            value = html.escape(block["text"]).replace("\n", "<br/>")
            if "source_url" in block:
                value = f'<link href="{html.escape(block["source_url"], quote=True)}" color="#B64302">{value}</link>'
            flow.append(Paragraph(value, styles[kind]))
    def footer(canvas, doc):
        canvas.setFont("ReportBody", 8)
        canvas.setFillColor(colors.HexColor("#6D6E71"))
        canvas.drawString(36, 20, "Investigación independiente | Edición privada")
        canvas.drawRightString(559, 20, str(doc.page))
    doc = SimpleDocTemplate(str(target), pagesize=(595.28, 841.89),
                            leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    doc.build(flow, onFirstPage=footer, onLaterPages=footer)


def write_newsletter(brief, base, output_root, fonts=None):
    validate_brief(brief, base)
    if fonts is not None:
        if len(fonts) != 3 or not all(Path(p).is_file() for p in fonts):
            raise ValueError("Supply regular, bold and italic local font files")
    output = Path(output_root) / ("newsletter_" + uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    assets = []
    for block in edition_blocks(brief):
        if block["type"] != "chart" or block.get("pdf_only"):
            continue
        source = chart_path(block["path"], base)
        name = f"figure-{len(assets)+1}"
        destination = output / "assets" / (name + source.suffix.lower())
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, destination)
        assets.append({"file": destination.relative_to(output).as_posix(),
                       "content_id": name,
                       "mime_type": "image/png" if source.suffix.lower() == ".png" else "image/jpeg"})
    (output / "newsletter.html").write_text(render_html(brief, assets), encoding="utf-8")
    if fonts is not None:
        render_pdf(brief, base, output / "newsletter.pdf", fonts)
    manifest = {"edition_date": brief["edition_date"], "html": "newsletter.html",
                "pdf": "newsletter.pdf" if fonts is not None else None, "inline": assets}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Private editorial JSON")
    parser.add_argument("--output", default="outputs")
    parser.add_argument("--font-regular")
    parser.add_argument("--font-bold")
    parser.add_argument("--font-italic")
    args = parser.parse_args()
    fonts = (args.font_regular, args.font_bold, args.font_italic)
    if any(fonts) and not all(fonts):
        parser.error("Supply all three local font files, or none for HTML only")
    path = Path(args.brief)
    brief = json.loads(path.read_text(encoding="utf-8-sig"))
    print(write_newsletter(brief, path.parent, args.output, fonts if all(fonts) else None))


if __name__ == "__main__":
    main()
