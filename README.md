# Trading agent (daily report)

Free end-of-day report that suggests long-term buys/exits and next-day intraday levels for NSE stocks.
Suggestion-only: it never places orders. **Not financial advice.**

## What it does

Every weekday at 5:00 PM IST a GitHub Actions job:

1. Downloads 2 years of daily prices from Yahoo Finance (free) for about 250 stocks: the Nifty 100 (large caps,
   `config/largecap.txt`), the Nifty Midcap 150 (mid caps, `config/midcap.txt`) and anything extra in
   `config/watchlist.txt`. The index lists refresh every Sunday from NSE. Every idea is tagged Large / Mid / Watch.
2. Scores each stock with simple rules (`agent/signals.py`):
   - **Long-term BUY**: price and 50-day average above the 200-day average, pulled back near the 20/50-day
     average, RSI 45-65 and turning up. Stop below the 50-day average / 2x ATR, target 2x the risk.
   - **Long-term SELL/EXIT**: closed below the 200-day average, or 50-day crossed below 200-day.
   - **Intraday next session**: after a narrow-range (NR7), inside day or 2x volume day, a "BUY above" or
     "SELL below" level in the direction of the trend, stop 1x ATR, target 1.5x the risk.
3. Checks your positions and past BUY ideas against their stop-loss and target.
4. Writes `reports/YYYY-MM-DD.md` and `reports/latest.md`, and sends a summary to Telegram.

## 10 AM market check

`run_morning.py` runs at 10:00 AM IST on weekdays and sends one Telegram message with:

- **Market mood** (Bullish / Bearish / Mixed) from Nifty 50 and Bank Nifty vs yesterday's close, India VIX,
  and how many watchlist stocks are up vs down.
- **Setups now**: stocks that broke out of their 9:15-10:00 range, on the right side of VWAP and their daily
  trend, and not against the market mood. Entry is the current price, stop is the other side of the range or
  VWAP, target 1.5x the risk. Stocks already too far from their stop are skipped.
- **Yesterday's levels triggered**: which "buy above / sell below" levels from last evening's report were hit.

On market holidays there is no data for the day, so nothing is sent.

## Baskets, capital and quantity

The report builds **baskets** that aim for a combined profit of about ₹5,000 at target using at most ₹50,000:

- **Long-term basket**: the 3 best large caps + 2 best mid caps. Paid in full (delivery), so it must fit in ₹50,000.
- **Intraday basket**: the 5 best next-session levels. Intraday (MIS) only needs margin, assumed ~5x, so ₹50,000
  of margin covers up to ₹2.5L of exposure. The 10 AM check builds its own intraday basket the same way.
- Baskets are **buy-only**: every pick reads `BUY` or `BUY above <level> | SL | T`. Short-sell ("SELL below") ideas
  still appear in the full intraday list of the report, but never in a basket.

The goal is split equally across the picks: each stock's quantity is `(goal / picks) / (target - entry)`, rounded
up. If that needs more than the capital allows, all quantities are scaled down to fit and the report says the goal
is out of reach with that capital (⚠️). Ties in score go to stocks with bigger % targets, which need less capital.

Change the numbers with repository variables (Settings > Secrets and variables > Actions > Variables):
`PROFIT_GOAL` (default 5000), `CAPITAL` (default 50000), `INTRADAY_LEVERAGE` (default 5).

## 8 AM Telegram planner

At 8:00 AM on weekdays the bot asks how much you want to trade and what profit you want. Reply in Telegram with
two numbers, e.g. `50000 5000` (also `50k 5k`, `1.5L 10k long`, `50000 5000 intraday`). Until about 9:25 AM the bot
listens live and answers within seconds with the long-term and intraday
baskets sized for your numbers, from the previous evening's ideas. Only messages from your own chat are answered.

## Basket Planner page

`docs/index.html` is a small web page (served by GitHub Pages) where you type your capital and profit goal, pick
long-term / intraday / 10 AM, large or mid caps and how many stocks, and it builds the basket with quantities from
the latest ideas in `docs/ideas.json` (written by the evening report and the 10 AM check).

Turn it on once: Settings > Pages > Build and deployment > Source: **Deploy from a branch**, Branch: **main**,
folder **/docs**. The page is then at `https://<your-username>.github.io/trading-agent/`.

## Stop-loss alerts

- List your holdings in `config/positions.csv` (`symbol,entry,stop,target,side`). Leave `stop` blank for a
  trailing stop 2x ATR below the highest close of the last 20 days. If the repo is public and you'd rather
  keep holdings private, put the same CSV text in a `POSITIONS_CSV` Actions secret instead.
- Every BUY idea from the daily report is tracked automatically until its stop or target is hit.
- During market hours (9:15 AM-3:30 PM IST) `check_stops.py` runs every ~10 minutes and sends a Telegram alert
  the first time a price crosses a stop (🔴), a target (🟢), or comes within 1% of the stop (🟠, once a day).
  Yahoo prices and GitHub's scheduler can lag by several minutes, so treat these as reminders, not tick-level
  alerts. Always keep a real stop-loss order (e.g. GTT) in Groww.

## Setup

1. **Telegram bot**: message [@BotFather](https://t.me/BotFather), `/newbot`, copy the token. Send your bot any
   message, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id`.
2. In the GitHub repo: Settings > Secrets and variables > Actions, add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
3. Actions tab > Daily report > Run workflow to test it now.

Edit `config/watchlist.txt` to change which stocks are scanned.

## Run locally

```bash
pip install -r requirements.txt
python run_daily.py --no-send
python -m pytest -q tests
```

## Next

Live intraday alerts via a free broker data feed (Angel One SmartAPI or Upstox).
