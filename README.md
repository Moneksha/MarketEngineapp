# MarketEngine 📈

An institutional-grade NIFTY paper-trading dashboard built with **FastAPI + React**, powered by **Zerodha Kite Connect**.

## Features

- **Live Market Data** — Real-time NIFTY & heavyweight stock quotes via Kite WebSocket
- **Strategy Engine** — Pluggable paper-trading strategies (EMA crossover, credit spreads, short straddles)
- **Live PnL Dashboard** — Real-time MTM with equity curves per strategy
- **Today's Trades** — Full trade history with instrument symbols and status
- **Authentication** — OAuth2 Zerodha login flow

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 · FastAPI · SQLAlchemy (async) · PostgreSQL |
| Frontend | React 18 · Vite · Tailwind CSS |
| Market Data | Zerodha Kite Connect REST + WebSocket |
| Realtime | FastAPI WebSocket broadcaster (1s cadence) |

## Strategies Included

| Strategy | Description |
|---|---|
| **EMA 9 Crossover Option Selling** | Sells ATM options on EMA 9 crossover signals |
| **EMA 9/21 Credit Spread** | Builds bull/bear spreads on EMA crossovers |
| **Straddle 2A (Vanilla)** | Intraday ATM short straddle on NIFTY weekly options |

## Setup

### 1. Clone
```bash
git clone https://github.com/Moneksha/MarketEngine.git
cd MarketEngine
```

### 2. Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Fill in your Kite API keys & DB URL
uvicorn app.main:app --reload
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 4. Environment Variables
Copy `backend/.env.example` → `backend/.env` and fill in:
- `KITE_API_KEY` / `KITE_API_SECRET` — from [Kite Developer Console](https://developers.kite.trade/)
- `DATABASE_URL` — PostgreSQL connection string
- `KITE_ACCESS_TOKEN` — refreshed daily after login

## Project Structure
```
MarketEngine/
├── backend/
│   ├── app/
│   │   ├── api/            # REST endpoints
│   │   ├── services/       # Kite service, PnL engine, paper trading
│   │   ├── strategies/     # Pluggable strategy classes
│   │   ├── websocket/      # WebSocket broadcaster
│   │   └── database/       # SQLAlchemy models
│   ├── .env.example
│   └── requirements.txt
└── frontend/
    └── src/
        ├── components/     # React components
        └── services/       # API & WebSocket clients
```

## Disclaimer
This is a **paper-trading** platform only. No real orders are placed.

---
Built by [@Moneksha](https://github.com/Moneksha)
