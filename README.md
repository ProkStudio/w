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
- `CRYPTOBOT_TOKEN`
- `CRYPTOBOT_ASSET` (default `USDT`)
- `REFERRAL_PERCENT` (default `10`)
- `STARS_TITLE`

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
