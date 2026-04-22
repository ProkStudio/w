# Telegram Shop Bot (aiogram 3)

Production-ready Telegram bot for selling digital goods with:
- `aiogram 3`
- PostgreSQL (`SQLAlchemy + asyncpg`)
- Alembic migrations
- Telegram Stars + CryptoBot payments
- referral system
- admin panel with FSM

## Project structure

```text
main.py
bot/
  handlers/
  keyboards/
  middlewares/
database/
  models.py
  db.py
services/
  payments.py
  referrals.py
  items.py
alembic/
alembic.ini
```

## Environment variables

Copy `.env.example` to `.env` and fill:

- `BOT_TOKEN`
- `DATABASE_URL`
- `ADMIN_ID`
- `ADMIN_PASSWORD`
- `CRYPTOBOT_TOKEN`
- `CRYPTOBOT_ASSET` (default `USDT`)
- `REFERRAL_PERCENT` (default `10`)
- `STARS_TITLE`
- `USD_RUB_FALLBACK` (default `95`) - fallback USD/RUB if rate API is unavailable
- `USD_PER_STAR` (default `0.013`) - estimated USD cost of 1 Telegram Star for pricing
- `RATE_CACHE_TTL_SEC` (default `600`) - rate cache lifetime in seconds

## Local run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run migrations:
   ```bash
   alembic upgrade head
   ```
3. Start bot:
   ```bash
   python main.py
   ```

## Railway deploy

1. Add PostgreSQL plugin.
2. Set all env vars from `.env.example`.
3. Ensure start command: `python main.py` (already in `Procfile`).
4. Run migrations once:
   ```bash
   alembic upgrade head
   ```

## Notes

- Bot prevents duplicate purchases (`user_id + item_id` unique constraint).
- Only active items (`expires_at > now`) appear in catalog.
- Payment callbacks validate payload and amount.
- Admin enters item price in RUB; bot auto-converts to Stars/USDT at payment time.
