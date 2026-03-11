# Morning Prep Workflow

**Trigger:** "morning prep", "game plan", "stocks in play", "big picture", "market regime"

This is the daily entry point. Run before market open to build a focused game plan with 2-4 stocks in play, entry/stop/target for each, and a risk budget.

---

## Steps

### 1. Big Picture — Market Regime

Assess the overall market environment before picking individual stocks:

```bash
uv run tradekit regime
```

From the output:
- **SPY/QQQ trend**: Are we above or below key SMAs? Uptrend, pullback, or downtrend?
- **VIX level**: Low/Normal = full size, Elevated = reduce size, High/Extreme = defensive or sit out
- **Sector breadth**: How many sectors green vs red? Which are leading?
- **SPY key levels**: Nearest support/resistance — these act as market inflection points
- **Set daily bias**: Bullish, bearish, or neutral. This frames all trade decisions today.

### 2. In The News — Catalysts

Research today's catalysts that could drive individual stock movement:

- Check earnings calendar (pre-market and after-hours reporters)
- Macro events: Fed speakers, economic data releases (CPI, jobs, etc.)
- Sector news: regulation, upgrades/downgrades, sector rotation themes
- Breaking news: M&A, FDA decisions, geopolitical events

Output a bullet list:
- **TICKER** — catalyst description (e.g., "NVDA — earnings beat, raised guidance")
- Note which catalysts are fresh (today) vs continuation (multi-day theme)

### 3. 2nd Day Plays

Scan for stocks that had big moves yesterday and may offer follow-through today:

```bash
uv run tradekit second-day
```

For each candidate:
- Review yesterday's chart: Was the move clean or choppy? Did it close near highs/lows?
- Check pre-market action: Is there continuation or a fade?
- Note key levels from yesterday (VWAP, high/low of day, opening range)
- Expected patterns: gap-and-go, morning pullback to VWAP, red-to-green

### 4. Pre-Market Scan

Run the tradekit scanner to find stocks with catalysts and volume:

```bash
uv run tradekit morning --top-n 5
```

This returns the top gap movers with pre-market volume, float, and catalyst data.

### 5. Load Watchlist

Check the personal watchlist for tickers David is already tracking:

```bash
uv run tradekit watchlist
```

### 6. Load Risk Rules

Read `Data/RiskRules.yaml` for:
- Account size and max daily loss
- Max risk per trade and position limits
- Time rules (best trading window, avoid periods)

### 7. Evaluate Each Candidate

For each top pick from the scan + watchlist + 2nd-day plays (max 4-5 tickers):

1. Run analysis: `uv run tradekit analyze <TICKER>`
2. Run levels: `uv run tradekit levels <TICKER>`
3. Identify the catalyst (earnings, news, sector move, technical)
4. Match to a playbook setup in `Data/Playbooks.yaml`:
   - ORB, VWAP Reclaim, First Pullback, Red to Green, Breakdown Short
5. Plan entry price, stop price, target price
6. Calculate position size:
   - Risk per share = |entry - stop|
   - Shares = max_risk_per_trade / risk_per_share
   - Validate: shares × entry ≤ max_position_size
   - Validate: concurrent positions ≤ max_concurrent_positions

### 8. Present Game Plan

Use the `Templates/GamePlan.hbs` template to format:
- Big picture summary with market bias
- In the news catalysts
- 2nd day play candidates
- Stocks in play table with ticker, catalyst, setup, entry/stop/target, risk, shares
- Risk budget showing remaining daily risk capacity
- Pre-market checklist

### 9. Confirm with David

Ask David to:
- Confirm or adjust the stocks in play
- Add any tickers he's been watching independently
- Confirm his mental state / readiness

---

## Output

A formatted game plan ready for the trading day. David should reference this throughout the session.

## Notes

- Run this between 8:30-9:25 AM ET
- Focus on 2-4 high-conviction setups, not 10 mediocre ones
- "If you don't have a plan, you don't have a trade" — Mike Bellafiore
