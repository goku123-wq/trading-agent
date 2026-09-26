# Trading agent (daily report)

Free end-of-day report that suggests long-term buys/exits and next-day intraday levels for NSE stocks.
Suggestion-only: it never places orders. **Not financial advice.**

## What it does

Every weekday at 5:00 PM IST a GitHub Actions job:

1. Downloads 2 years of daily prices for `config/watchlist.txt` from Yahoo Finance (free).
2. Scores each stock with simple rules (`agent/signals.py`):
   - **Long-term BUY**: price and 50-day average above the 200-day average, pulled back near the 20/50-day
     average, RSI 45-65 and turning up. Stop below the 50-day average / 2x ATR, target 2x the risk.
   - **Long-term SELL/EXIT**: closed below the 200-day average, or 50-day crossed below 200-day.
   - **Intraday next session**: after a narrow-range (NR7), inside day or 2x volume day, a "BUY above" or
     "SELL below" level in the direction of the trend, stop 1x ATR, target 1.5x the risk.
3. Checks your positions and past BUY ideas against their stop-loss and target.
4. Writes `reports/YYYY-MM-DD.md` and `reports/latest.md`, and sends a summary to Telegram.

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
