"""Local research appendix; no network, personal data, mail delivery or orders."""
from pathlib import Path
from xml.sax.saxutils import escape


def render_report(table, prices, config, output, georgia_dir=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle

    output = Path(output)
    font = "Times-Roman"
    if georgia_dir:
        pdfmetrics.registerFont(TTFont("Georgia", str(Path(georgia_dir)/"georgia.ttf")))
        font = "Georgia"
    sectors = config["sectors"]
    names = lambda ticks: [sectors.get(t, {}).get("name", t) for t in ticks]
    ordered = table.sort_values("relative_3m")
    fig, ax = plt.subplots(figsize=(8, 3.2), layout="constrained")
    ax.barh(names(ordered.index), ordered.relative_3m*100,
            color=["#D04A02" if v else "#6D6E71" for v in ordered.selected])
    ax.axvline(0, color="#404040", linewidth=.7)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_xlabel("63-observation relative return vs benchmark (percentage points)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(output/"relative_strength.png", dpi=180)
    plt.close(fig)
    candidates = table.index[table.selected][:3].tolist()
    series = candidates+[config["benchmark"]]
    base = prices[series].iloc[-127:]
    base = base/base.iloc[0]*100
    fig, ax = plt.subplots(figsize=(8, 3.2), layout="constrained")
    for ticker in series:
        ax.plot(base.index, base[ticker], label=sectors.get(ticker, {}).get("name", ticker))
    ax.set_ylabel("Adjusted EUR, base 100")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(output/"candidate_history.png", dpi=180)
    plt.close(fig)

    pdf = canvas.Canvas(str(output/"sector_report.pdf"), pagesize=(595, 842))
    style = ParagraphStyle("body", fontName=font, fontSize=9.5, leading=13,
                           textColor=HexColor("#404040"))
    def text(value, y, size=9.5):
        p = Paragraph(escape(value), ParagraphStyle("p", parent=style, fontSize=size))
        _, height = p.wrap(507, 800)
        if y-height < 45:
            raise ValueError("Report text exceeds page; shorten the editorial content")
        p.drawOn(pdf, 44, y-height)
        return y-height-9
    def header(page):
        pdf.setFillColor(HexColor("#D04A02"))
        pdf.rect(44, 790, 507, 4, fill=1, stroke=0)
        text("Radar sectorial de ETF | Investigacion", 774, 20)
        text(f"Cierre: {prices.index[-1].date()} | EUR | {page}/2", 738)
        pdf.setFillColor(HexColor("#404040"))
        pdf.setFont(font, 8)
        pdf.drawString(44, 28, "Investigacion independiente. Sin autoria ni aprobacion de PwC.")
    header(1)
    pdf.drawImage(str(output/"relative_strength.png"), 44, 485, width=507, height=225)
    y = text("Comparativa de riesgo y tendencia", 468, 14)
    y = text("ETF (* baseline) | 3m / 6m | Vol. anual | Caida maxima 1a | Score", y)
    for ticker, row in table.head(8).iterrows():
        marker = " *" if sectors[ticker].get("baseline", False) else ""
        y = text(f"{ticker}{marker}: {row.return_3m:+.1%} / {row.return_6m:+.1%} | "
                 f"{row.volatility:.1%} | {row.drawdown_1y:.1%} | {row.score:.0f}/100", y)
    text(f"Tabla: {min(len(table), 8)} de {len(table)} ETF. Detalle completo en screen.csv. "
         "Ventanas de 63/126 intervalos comunes; volatilidad a 63 anualizada con 252. "
         "Score: 35% fuerza relativa 3m, 25% 6m, 20% menor volatilidad, 20% menor caida "
         "en 252 intervalos. Rangos (rango medio-1)/(n-1). No mide valoracion ni "
         "probabilidad de beneficio. Sin imputar precios.", y-8)
    pdf.showPage()
    header(2)
    pdf.drawImage(str(output/"candidate_history.png"), 44, 457, width=507, height=250)
    y = text("Prioridades de estudio", 438, 14)
    y = text(", ".join(names(candidates)) if candidates else "Ningun ETF supera el filtro.", y)
    y = text("Entrada score >=60; mantenimiento >=40, siempre con retorno 63 positivo, "
             "superior al benchmark y cierre sobre media de 200. Se conservan candidatos "
             "previos que cumplan el filtro. Las seis referencias baseline no implican "
             "asignacion obligatoria. Otros sectores pueden entrar y salir.", y)
    y = text("Ver changes.json para entradas, salidas y motivos, metadata.json para "
             "cobertura y exclusiones. Un sector ausente por falta de datos no constituye "
             "una senal bajista. Verificar ISIN, TER, liquidez, concentracion y "
             "disponibilidad UCITS con la gestora y el intermediario.", y)
    text("Apendice cuantitativo para acompanar de fuentes, tesis, riesgos e invalidacion "
         "y analisis cripto separado. Excluye corretaje, spread, cambio e impuestos. "
         "No se resta TER de nuevo a precios ajustados. El programa no puede verificar "
         "el proveedor ni la conversion a EUR declarada del CSV.", y)
    pdf.save()
