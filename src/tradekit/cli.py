"""CLI entry point for tradekit."""

import logging
import sys

import click
from rich.console import Console

from tradekit.config import get_settings, now_et

console = Console(force_terminal=True)
logger = logging.getLogger("tradekit")

source_option = click.option(
    "--source",
    type=click.Choice(["yahoo", "massive", "backtest"], case_sensitive=False),
    default=None,
    help="Data source: yahoo (default), massive, or backtest.",
)


def get_provider(source: str | None = None):
    """Return the appropriate data provider based on source name."""
    settings = get_settings()
    source = source or settings.data_source
    if source == "massive":
        from tradekit.data.massive import MassiveProvider

        return MassiveProvider()
    elif source == "backtest":
        from tradekit.data.backtest import BacktestProvider

        return BacktestProvider()
    else:
        from tradekit.data.yahoo import YahooProvider

        return YahooProvider()


def _market_session() -> str:
    """Return a description of the current market session in ET."""
    t = now_et()
    hour, minute = t.hour, t.minute
    mins = hour * 60 + minute

    if mins < 4 * 60:
        return "Overnight (market closed)"
    elif mins < 9 * 60 + 30:
        return "Pre-market"
    elif mins < 16 * 60:
        return "Market open"
    elif mins < 20 * 60:
        return "After-hours"
    else:
        return "Overnight (market closed)"


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging.")
def cli(verbose: bool):
    """tradekit — Pre-market screening and technical analysis toolkit."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    et = now_et()
    console.print(f"[dim]{et.strftime('%a %b %d, %I:%M %p')} ET — {_market_session()}[/dim]")


@cli.command()
@click.option("--preset", default="premarket_gap", help="Screener preset name.")
@click.option("--min-gap", type=float, default=None, help="Override minimum gap %.")
@click.option("--min-volume", type=int, default=None, help="Override minimum avg daily volume.")
@click.option("--max-price", type=float, default=None, help="Override maximum price.")
@source_option
def scan(
    preset: str, min_gap: float | None, min_volume: int | None,
    max_price: float | None, source: str | None,
):
    """Run the pre-market stock scanner."""
    from tradekit.reports.terminal import print_scan_results
    from tradekit.screener.premarket import scan_premarket

    settings = get_settings()
    provider = get_provider(source)

    # Apply CLI overrides to screener settings
    if min_gap is not None:
        settings.screener.min_gap_pct = min_gap
    if min_volume is not None:
        settings.screener.min_avg_volume = min_volume
    if max_price is not None:
        settings.screener.max_price = max_price

    console.print("[bold]Running pre-market scan...[/bold]")
    df = scan_premarket(settings=settings, preset=preset, provider=provider)
    print_scan_results(df)

    if not df.empty:
        tickers = df["ticker"].tolist()
        console.print(f"\n[dim]Tickers: {', '.join(tickers)}[/dim]")


@cli.command()
@click.argument("ticker")
@click.option("--period", default="3mo", help="History period (e.g. 1mo, 3mo, 6mo, 1y).")
@source_option
def analyze(ticker: str, period: str, source: str | None):
    """Run deep technical analysis on a ticker."""
    from tradekit.analysis.indicators import compute_all_indicators
    from tradekit.analysis.levels import find_support_resistance, get_nearest_levels
    from tradekit.analysis.scoring import compute_composite_score
    from tradekit.analysis.volume import add_volume_indicators
    from tradekit.reports.terminal import print_analysis

    settings = get_settings()
    presets = settings.load_indicator_presets()
    provider = get_provider(source)

    ticker = ticker.upper()
    console.print(f"[bold]Analyzing {ticker}...[/bold]")

    # Fetch data
    quote = provider.get_quote(ticker)
    df = provider.get_history(ticker, period=period)
    if df.empty:
        console.print(f"[red]No data available for {ticker}[/red]")
        return

    # Compute indicators
    df = compute_all_indicators(df, presets=presets)
    df = add_volume_indicators(df)

    # Score
    latest = df.iloc[-1]
    score = compute_composite_score(latest, presets.get("scoring_weights"))

    # Levels
    sr_levels = find_support_resistance(df)
    current_price = quote.get("price", latest.get("close", 0))
    nearest = get_nearest_levels(current_price, sr_levels)

    print_analysis(ticker, score, nearest, quote)

    # Print RVOL and ATR prominently
    console.print("[bold]Volatility & Volume:[/bold]")
    rvol = latest.get("relative_volume")
    if rvol is not None:
        rvol_style = "bold green" if rvol >= 2.0 else "green" if rvol >= 1.5 else "yellow" if rvol >= 1.0 else "red"
        console.print(f"  RVOL: [{rvol_style}]{rvol:.2f}x[/{rvol_style}]", end="")
        if rvol >= 3.0:
            console.print("  [bold magenta]EXTREME[/bold magenta]")
        elif rvol >= 2.0:
            console.print("  [bold green]HIGH[/bold green]")
        elif rvol >= 1.5:
            console.print("  [green]ABOVE AVG[/green]")
        elif rvol >= 1.0:
            console.print("  [yellow]NORMAL[/yellow]")
        else:
            console.print("  [red]BELOW AVG[/red]")

    atr = latest.get("atr")
    atr_pct = latest.get("atr_pct")
    if atr is not None:
        console.print(f"  ATR(14): ${atr:.2f}  ({atr_pct:.1f}% of price)")

    vwap = latest.get("vwap")
    if vwap is not None:
        current = quote.get("price", latest.get("close", 0))
        vwap_dist = ((current - vwap) / vwap * 100) if vwap else 0
        vwap_style = "green" if vwap_dist > 0 else "red"
        console.print(f"  VWAP: ${vwap:.2f}  [{vwap_style}]({vwap_dist:+.1f}%)[/{vwap_style}]")

    console.print()

    # Print indicator snapshot
    console.print("[bold]Indicator Snapshot:[/bold]")
    rsi = latest.get("rsi")
    if rsi is not None:
        rsi_style = "red" if rsi > 70 else "green" if rsi < 30 else "white"
        console.print(f"  RSI(14): [{rsi_style}]{rsi:.1f}[/{rsi_style}]")

    macd_h = latest.get("macd_histogram")
    if macd_h is not None:
        macd_style = "green" if macd_h > 0 else "red"
        console.print(f"  MACD Hist: [{macd_style}]{macd_h:.3f}[/{macd_style}]")

    stoch_k = latest.get("stoch_k")
    stoch_d = latest.get("stoch_d")
    if stoch_k is not None:
        console.print(f"  Stochastic: %K={stoch_k:.1f}  %D={stoch_d:.1f}")

    console.print()


@cli.command()
@click.argument("ticker")
@click.option("--period", default="3mo", help="History period for level detection.")
@source_option
def levels(ticker: str, period: str, source: str | None):
    """Show support and resistance levels for a ticker."""
    from tradekit.analysis.levels import find_support_resistance, get_nearest_levels
    from tradekit.analysis.volume import find_high_volume_nodes

    provider = get_provider(source)
    ticker = ticker.upper()

    console.print(f"[bold]Support/Resistance for {ticker}...[/bold]")
    quote = provider.get_quote(ticker)
    df = provider.get_history(ticker, period=period)

    if df.empty:
        console.print(f"[red]No data for {ticker}[/red]")
        return

    sr = find_support_resistance(df)
    current_price = quote.get("price", df["close"].iloc[-1])
    nearest = get_nearest_levels(current_price, sr)

    console.print(f"\n  Current: [bold]${current_price:.2f}[/bold]\n")

    for r in nearest.get("resistance", []):
        dist = (r["level"] - current_price) / current_price * 100
        console.print(f"  [red]R ${r['level']:.2f}[/red]  (+{dist:.1f}%)  strength: {r['strength']}")

    console.print(f"  [bold cyan]→ ${current_price:.2f}[/bold cyan]")

    for s in nearest.get("support", []):
        dist = (current_price - s["level"]) / current_price * 100
        console.print(f"  [green]S ${s['level']:.2f}[/green]  (-{dist:.1f}%)  strength: {s['strength']}")

    # High volume nodes
    hvn = find_high_volume_nodes(df["close"], df["volume"])
    if hvn:
        console.print(f"\n  [yellow]High Volume Nodes:[/yellow] " + "  ".join(f"${p:.2f}" for p in hvn))

    console.print()


@cli.command()
@click.option("--name", default="default", help="Watchlist name from config.")
@source_option
def watchlist(name: str, source: str | None):
    """Review watchlist tickers with pre-market data."""
    from tradekit.reports.terminal import print_scan_results
    from tradekit.screener.premarket import scan_watchlist

    settings = get_settings()
    provider = get_provider(source)
    console.print(f"[bold]Scanning watchlist '{name}'...[/bold]")

    df = scan_watchlist(settings=settings, watchlist_name=name, provider=provider)
    print_scan_results(df, title=f"Watchlist: {name}")


@cli.command()
@source_option
def regime(source: str | None):
    """Show market regime summary: SPY/QQQ/VIX + sector breadth."""
    from rich.table import Table

    from tradekit.analysis.indicators import compute_all_indicators, compute_rsi
    from tradekit.analysis.levels import find_support_resistance, get_nearest_levels

    provider = get_provider(source)

    # --- Index + VIX overview ---
    index_table = Table(title="Market Regime", show_lines=True, pad_edge=True)
    index_table.add_column("Symbol", style="bold cyan", width=6)
    index_table.add_column("Price", justify="right", width=10)
    index_table.add_column("Chg%", justify="right", width=8)
    index_table.add_column("vs SMA20", justify="right", width=9)
    index_table.add_column("vs SMA50", justify="right", width=9)
    index_table.add_column("vs SMA200", justify="right", width=9)
    index_table.add_column("RSI", justify="right", width=6)
    index_table.add_column("Label", width=12)

    for sym in ("SPY", "QQQ", "^VIX"):
        display = sym.replace("^", "")
        try:
            quote = provider.get_quote(sym)
            price = quote.get("price", 0)
            prev = quote.get("prev_close", 0)
            chg_pct = ((price - prev) / prev * 100) if prev else 0
            chg_style = "green" if chg_pct >= 0 else "red"

            df = provider.get_history(sym, period="1y")
            if df.empty:
                index_table.add_row(display, f"${price:.2f}", f"[{chg_style}]{chg_pct:+.2f}%[/{chg_style}]",
                                    "-", "-", "-", "-", "-")
                continue

            df = compute_all_indicators(df)
            latest = df.iloc[-1]
            rsi = latest.get("rsi", 0)

            sma20 = latest.get("ema_20") or latest.get("sma_20", 0)
            sma50 = latest.get("sma_50", 0)
            sma200 = latest.get("sma_200", 0)

            def _vs(sma):
                if not sma:
                    return "-"
                d = (price - sma) / sma * 100
                s = "green" if d >= 0 else "red"
                return f"[{s}]{d:+.1f}%[/{s}]"

            # Label
            if display == "VIX":
                if price < 15:
                    label = "[green]Low[/green]"
                elif price < 20:
                    label = "[green]Normal[/green]"
                elif price < 25:
                    label = "[yellow]Elevated[/yellow]"
                elif price < 30:
                    label = "[red]High[/red]"
                else:
                    label = "[bold red]Extreme[/bold red]"
            else:
                if price > sma50 and price > sma200:
                    label = "[green]Uptrend[/green]"
                elif price > sma200:
                    label = "[yellow]Pullback[/yellow]"
                else:
                    label = "[red]Downtrend[/red]"

            rsi_style = "red" if rsi > 70 else "green" if rsi < 30 else "white"
            index_table.add_row(
                display,
                f"${price:.2f}",
                f"[{chg_style}]{chg_pct:+.2f}%[/{chg_style}]",
                _vs(sma20), _vs(sma50), _vs(sma200),
                f"[{rsi_style}]{rsi:.0f}[/{rsi_style}]",
                label,
            )
        except Exception as e:
            index_table.add_row(display, "-", "-", "-", "-", "-", "-", f"[red]err[/red]")
            logger.warning("Failed to fetch %s: %s", sym, e)

    console.print(index_table)

    # --- SPY key levels ---
    try:
        spy_df = provider.get_history("SPY", period="3mo")
        if not spy_df.empty:
            sr = find_support_resistance(spy_df)
            spy_price = provider.get_quote("SPY").get("price", spy_df["close"].iloc[-1])
            nearest = get_nearest_levels(spy_price, sr, n=2)
            r_str = "  ".join(f"${r['level']:.2f}" for r in nearest.get("resistance", []))
            s_str = "  ".join(f"${s['level']:.2f}" for s in nearest.get("support", []))
            console.print(f"\n[bold]SPY Key Levels:[/bold]  [red]R: {r_str}[/red]  >  ${spy_price:.2f}  >  [green]S: {s_str}[/green]")
    except Exception as e:
        logger.warning("Failed to compute SPY levels: %s", e)

    # --- Sector breadth ---
    sector_etfs = {
        "XLK": "Tech", "XLF": "Financials", "XLE": "Energy", "XLV": "Health",
        "XLI": "Industrials", "XLC": "Comms", "XLY": "Cons Disc", "XLP": "Cons Staples",
        "XLU": "Utilities", "XLRE": "Real Estate", "XLB": "Materials",
    }

    console.print("\n[bold]Sector Breadth:[/bold]")
    breadth_table = Table(show_lines=False, pad_edge=True)
    breadth_table.add_column("ETF", style="bold", width=5)
    breadth_table.add_column("Sector", width=12)
    breadth_table.add_column("Chg%", justify="right", width=8)

    green_count = 0
    sector_data = []
    for etf, name in sector_etfs.items():
        try:
            q = provider.get_quote(etf)
            price = q.get("price", 0)
            prev = q.get("prev_close", 0)
            chg = ((price - prev) / prev * 100) if prev else 0
            sector_data.append((etf, name, chg))
            if chg >= 0:
                green_count += 1
        except Exception:
            sector_data.append((etf, name, 0))

    sector_data.sort(key=lambda x: x[2], reverse=True)
    for etf, name, chg in sector_data:
        style = "green" if chg >= 0 else "red"
        breadth_table.add_row(etf, name, f"[{style}]{chg:+.2f}%[/{style}]")

    console.print(breadth_table)

    total = len(sector_etfs)
    pct_green = green_count / total * 100 if total else 0
    breadth_style = "green" if pct_green >= 60 else "yellow" if pct_green >= 40 else "red"
    console.print(f"\n  [{breadth_style}]Breadth: {green_count}/{total} green ({pct_green:.0f}%)[/{breadth_style}]")
    if sector_data:
        console.print(f"  [green]Strongest:[/green] {sector_data[0][0]} ({sector_data[0][1]}) {sector_data[0][2]:+.2f}%")
        console.print(f"  [red]Weakest:[/red]   {sector_data[-1][0]} ({sector_data[-1][1]}) {sector_data[-1][2]:+.2f}%")
    console.print()


@cli.command("second-day")
@click.option("--min-change", type=float, default=5.0, help="Minimum yesterday move %.")
@click.option("--min-vol-ratio", type=float, default=1.5, help="Minimum volume ratio vs avg.")
@source_option
def second_day(min_change: float, min_vol_ratio: float, source: str | None):
    """Find 2nd-day play candidates from yesterday's big movers."""
    from rich.table import Table

    from tradekit.screener.premarket import scan_previous_movers

    provider = get_provider(source)

    console.print("[bold]Scanning for 2nd-day play candidates...[/bold]")
    df = scan_previous_movers(
        provider=provider,
        min_change_pct=min_change,
        min_volume_ratio=min_vol_ratio,
    )

    if df.empty:
        console.print("[yellow]No 2nd-day candidates found. Try lowering --min-change or --min-vol-ratio.[/yellow]")
        return

    table = Table(title="2nd Day Play Candidates", show_lines=False, pad_edge=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Ticker", style="bold cyan", width=8)
    table.add_column("Name", width=18, no_wrap=True)
    table.add_column("Price", justify="right", width=8)
    table.add_column("Prev Chg%", justify="right", width=10)
    table.add_column("Vol Ratio", justify="right", width=10)
    table.add_column("Pre-Mkt", justify="right", width=8)
    table.add_column("Pre Gap%", justify="right", width=9)

    for i, row in df.iterrows():
        chg = row["prev_change_pct"]
        chg_style = "green" if chg > 0 else "red"
        pre_gap = row.get("pre_gap_pct", 0)
        pre_style = "green" if pre_gap > 0 else "red" if pre_gap < 0 else "white"

        vol_ratio = row.get("volume_ratio", 0)
        vol_style = "bold green" if vol_ratio >= 3 else "green" if vol_ratio >= 2 else "yellow"

        pre_price = row.get("pre_price", 0)
        pre_str = f"${pre_price:.2f}" if pre_price else "-"

        table.add_row(
            str(int(i) + 1),
            row["ticker"],
            str(row.get("name", ""))[:18],
            f"${row['price']:.2f}",
            f"[{chg_style}]{chg:+.1f}%[/{chg_style}]",
            f"[{vol_style}]{vol_ratio:.1f}x[/{vol_style}]",
            pre_str,
            f"[{pre_style}]{pre_gap:+.1f}%[/{pre_style}]" if pre_price else "-",
        )

    console.print(table)
    tickers = df["ticker"].tolist()
    console.print(f"\n[dim]Tickers: {', '.join(tickers)}[/dim]")
    console.print()


@cli.command()
@click.option("--preset", default="premarket_gap", help="Screener preset.")
@click.option("--top-n", default=5, help="Number of top picks to analyze in detail.")
@source_option
def morning(preset: str, top_n: int, source: str | None):
    """Full morning pre-market workflow: scan + analyze top picks."""
    from tradekit.analysis.indicators import compute_all_indicators
    from tradekit.analysis.levels import find_support_resistance, get_nearest_levels
    from tradekit.analysis.scoring import compute_composite_score
    from tradekit.analysis.volume import add_volume_indicators
    from tradekit.reports.terminal import print_analysis, print_scan_results
    from tradekit.screener.premarket import scan_premarket

    settings = get_settings()
    presets = settings.load_indicator_presets()
    provider = get_provider(source)

    # Step 1: Scan
    console.print("[bold]Step 1: Pre-Market Scan[/bold]")
    scan_df = scan_premarket(settings=settings, preset=preset, provider=provider)
    print_scan_results(scan_df)

    if scan_df.empty:
        console.print("[yellow]No candidates found. Check back closer to market open.[/yellow]")
        return

    # Step 2: Analyze top picks
    tickers = scan_df["ticker"].tolist()[:top_n]
    console.print(f"\n[bold]Step 2: Analyzing Top {len(tickers)} Picks[/bold]")

    for ticker in tickers:
        try:
            quote = provider.get_quote(ticker)
            df = provider.get_history(ticker, period="3mo")
            if df.empty:
                console.print(f"[yellow]  Skipping {ticker} — no data[/yellow]")
                continue

            df = compute_all_indicators(df, presets=presets)
            df = add_volume_indicators(df)
            latest = df.iloc[-1]
            score = compute_composite_score(latest, presets.get("scoring_weights"))

            sr = find_support_resistance(df)
            price = quote.get("price", latest.get("close", 0))
            nearest = get_nearest_levels(price, sr)

            print_analysis(ticker, score, nearest, quote)
        except Exception as e:
            console.print(f"[red]  Error analyzing {ticker}: {e}[/red]")

    console.print("[bold green]Morning workflow complete.[/bold green]")


@cli.command()
@click.option("--preset", default="premarket_gap", help="Screener preset.")
@click.option("--output-dir", default=None, help="Report output directory.")
@source_option
def report(preset: str, output_dir: str | None, source: str | None):
    """Generate and save a daily report."""
    from pathlib import Path

    from tradekit.reports.markdown import generate_daily_report, save_report
    from tradekit.screener.premarket import scan_premarket
    from tradekit.screener.ranking import rank_candidates

    settings = get_settings()
    provider = get_provider(source)

    console.print("[bold]Generating daily report...[/bold]")

    scan_df = scan_premarket(settings=settings, preset=preset, provider=provider)

    ranked_df = None
    if not scan_df.empty:
        tickers = scan_df["ticker"].tolist()[:10]
        console.print(f"  Ranking top {len(tickers)} candidates...")
        presets = settings.load_indicator_presets()
        ranked_df = rank_candidates(
            tickers,
            weights=presets.get("scoring_weights"),
            indicator_presets=presets,
            provider=provider,
        )

    content = generate_daily_report(scan_df, ranked_df)
    out_dir = Path(output_dir) if output_dir else None
    path = save_report(content, output_dir=out_dir)

    console.print(f"[green]Report saved: {path}[/green]")
    console.print(content)
