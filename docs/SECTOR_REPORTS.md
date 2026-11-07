# Weekly sector ETF research

The starting universe contains 13 UCITS ETF representatives. Six baseline
sectors are observed in every edition: digital security/cyber, industrials,
healthcare/pharma, financials, energy and semiconductors. Baseline means permanent
comparison, not a mandatory investment. Other sectors may enter or leave the
highlighted watchlist: utilities, materials, staples, discretionary consumption,
communications, broad technology and listed real estate.

Review coverage weekly, using a stable broad taxonomy rather than adding only
recent winners. Verify issuer documents, ISIN, trading currency, UCITS status,
TER, liquidity and broker availability. LOCK covers digital security broadly;
WHEA covers healthcare broadly. Technology and semiconductors overlap. SMH.L is
the London UCITS line, not the US fund. The configuration is not an exhaustive
fund list and does not assert suitability for an investor.

## Local execution

Install Python 3.11+ and the package. Reporting dependencies are optional.

    python -m pip install -e ".[reports]"
    python -m market_models.sectors --prices private/eur_adjusted.csv --config config/sectors.json --asof YYYY-MM-DD --output outputs --pdf --georgia-dir C:/Windows/Fonts

Use today's date as the exclusive cutoff and complete adjusted daily closes
converted consistently to EUR. CSV schema: date,IWDA.L,<configured ETF tickers>.
The benchmark and at least two sector ETFs are required, with at least 253
complete common observations. Missing configured columns are explicitly recorded
in metadata.json; never present a partial sample as all 13 sectors. Missing
cells, duplicates, invalid prices, stale prices and gaps exceeding seven days
fail. No ETF prices are imputed. This basic gap check is not a full exchange
calendar validator. Investigate holidays, corporate actions and FX alignment.

Record the data provider, adjustment convention and FX source privately. The
program cannot prove input authenticity or infer the economic currency from the
CSV. An EUR trading line does not eliminate underlying foreign-currency risk.

## Score and selection

Three/six months mean 63/126 common observation intervals. Volatility uses the
last 63 returns and sqrt(252) annualization. One-year maximum drawdown uses the
last 253 prices. The relative score weights are 35% relative 3m return, 25%
relative 6m return, 20% low volatility and 20% low drawdown. Each component
uses (average rank - 1)/(sector count - 1). Ties receive average ranks. Scores
depend on the universe and are not calibrated probabilities or valuations.

An entry requires score >=60, positive 3m return, positive 3m return relative to
IWDA and price above its 200-observation moving average. Retain previously
selected sectors while they meet the trend filter and score >=40; fill remaining
places with eligible entrants. Maximum three candidates, with no forced picks.
Incumbents may therefore remain ahead of new higher-score candidates; this
deliberate hysteresis reduces marginal turnover and is not an optimized rule.
A broken trend filter or score below 40 removes an incumbent at the weekly review.

Pass --previous path/to/selection.json from the preceding weekly decision.
Without it, this is an initial screen, not evidence of an entry from a prior
portfolio. The state records selected tickers, last close and ranked universe;
same/future-close state is rejected. The legacy JSON ticker-list format is also
accepted for compatibility, with no timestamp check available. Keep state private.

Review the full universe on Monday; Thursday refreshes evidence and risks without
forcing a second weekly rotation or replacing Monday's decision state. Show
entered/exited/retained/initial names and reasons. An exclusion caused by missing
data is a data issue, not an economic sell signal. Disclose changes of universe
and compare raw relative returns as well as scores. Historical tests need
point-in-time universes and delisted products where possible to limit survivorship bias.

## Outputs and privacy

Each execution creates a new directory with screen.csv, selection.json,
changes.json and metadata.json. Metadata records coverage, exclusions, cutoff
and an input hash without publishing the input path. --pdf adds two chart PNGs
and a two-page quantitative appendix. Georgia is embedded when supplied locally;
without --georgia-dir the appendix falls back to Times. Font files are not published.

The appendix needs current editorial sources, issuer verification, theses, risks,
invalidation conditions and separate crypto analysis before use as a newsletter.
Use the local composer described in [NEWSLETTER.md](NEWSLETTER.md) for the full
editorial PDF and newsletter HTML, including the same ten sections and the
Monday-anchored 14-day earnings calendar. The sector PDF remains a quantitative
appendix. It is independent of older momentum/Ridge backtest signals. Adjusted prices
already reflect fund expenses; do not subtract TER a second time. Transaction
costs, spreads, FX, taxes and suitability require separate assessment.

Keep inputs, raw data, results, PDFs, charts, editorial briefs, recipient addresses,
selection state and credentials outside the public repository. The code makes no
network calls, sends no email, and places no investment orders.
