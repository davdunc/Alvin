---
name: Trading
description: SMB Capital-style intraday trading workflow. USE WHEN morning prep, scan stocks, analyze ticker, trade setup, log trade, ingest trades, import trades, session review, daily review, weekly review, playbook, stocks in play, game plan, risk management, position sizing, trade journal, how did I do.
---

# Trading Skill

Intraday trading discipline built on SMB Capital methodology (Bellafiore/Spencer). Covers the full daily cycle: morning prep, trade evaluation, trade logging via broker CSV ingestion, session review, weekly pattern analysis, and playbook management.

## Examples

**Example: Morning prep**
```
User: "morning prep"
→ Runs MorningPrep workflow
→ Scans pre-market, builds game plan with 2-4 stocks in play
```

**Example: Ingest today's trades**
```
User: "ingest trades"
→ Runs IngestTrades workflow
→ Parses Trade_Review CSVs, groups fills into round-trips, writes daily YAML
```

**Example: End of day review**
```
User: "session review"
→ Runs SessionReview workflow
→ Shows stats, best/worst trades, SMB reflection questions
```

---

## Workflow Routing

| Workflow | Triggers | File |
|----------|----------|------|
| **MorningPrep** | "morning prep", "game plan", "stocks in play", "big picture", "market regime", "second day plays", "2nd day plays", "in the news" | `Workflows/MorningPrep.md` |
| **TradeSetup** | "trade setup", "evaluate setup", "position size", "should I trade" | `Workflows/TradeSetup.md` |
| **IngestTrades** | "ingest trades", "import trades", "end of day import", "load today's trades" | `Workflows/IngestTrades.md` |
| **SessionReview** | "session review", "daily review", "how did I do", "end of day review" | `Workflows/SessionReview.md` |
| **WeeklyReview** | "weekly review", "week summary", "weekly stats" | `Workflows/WeeklyReview.md` |
| **Playbooks** | "playbook", "show setups", "list playbooks", "add setup" | `Workflows/Playbooks.md` |

---

## Tools

| Tool | Purpose |
|------|---------|
| `Tools/TradeLogger.ts` | Ingest broker CSVs, compute stats, generate reviews, manual trade entry |
| `Tools/ChartGen.ts` | Generate interactive candlestick charts with entry/exit markers |

### CLI Commands (`uv run tradekit`)

| Command | Purpose |
|---------|---------|
| `tradekit regime` | Market regime summary — SPY/QQQ/VIX, sector breadth, key levels |
| `tradekit second-day` | Scan for 2nd-day play candidates from yesterday's big movers |
| `tradekit scan` | Pre-market gap and volume scanner |
| `tradekit analyze <TICKER>` | Deep technical analysis on a single ticker |
| `tradekit levels <TICKER>` | Support and resistance levels |
| `tradekit watchlist` | Review personal watchlist with pre-market data |
| `tradekit morning` | Full morning workflow: scan + analyze top picks |
| `tradekit report` | Generate and save daily markdown report |

Both tools are Bun CLI scripts. Run via `bun run Tools/<tool>.ts <command> [options]`.

## Data

| File | Purpose |
|------|---------|
| `Data/Playbooks.yaml` | 5 SMB-style setups with criteria, entry/stop/target rules |
| `Data/RiskRules.yaml` | Account size, daily loss limits, position limits, behavioral rules |
| `Data/TradeLog/` | Daily YAML trade logs (one file per trading day) |

## Dependencies

- `tradekit` CLI (`uv run tradekit`) — pre-market scanning, analysis, levels
- `bun` runtime — for TradeLogger.ts and ChartGen.ts
- npm packages: `yaml`, `csv-parse`, `handlebars`
