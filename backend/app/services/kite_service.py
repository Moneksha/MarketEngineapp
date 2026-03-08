"""
Zerodha Kite Connect Service
Wraps the kiteconnect library with async support, caching, and safety guards.
PAPER TRADING ONLY — no order placement APIs exposed.
"""
import asyncio
import math
import random
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from cachetools import TTLCache
from kiteconnect import KiteConnect
from loguru import logger
from app.config.settings import settings

# Instrument token map for key symbols
INSTRUMENT_TOKENS = {
    "NIFTY 50": 256265,
    "INDIA VIX": 264969,
    "RELIANCE": 738561,
    "HDFCBANK": 341249,
    "ICICIBANK": 1270529,
    "INFY": 408065,
    "TCS": 2953217,
}

# NSE F&O symbol map
NSE_SYMBOLS = {
    "NIFTY 50":  "NSE:NIFTY 50",
    "RELIANCE":  "NSE:RELIANCE",
    "HDFCBANK":  "NSE:HDFCBANK",
    "ICICIBANK": "NSE:ICICIBANK",
    "INFY":      "NSE:INFY",
    "TCS":       "NSE:TCS",
}

# NIFTY heavyweight weights (approx % weight)
NIFTY_WEIGHTS = {
    "RELIANCE":  9.8,
    "HDFCBANK":  12.2,
    "ICICIBANK": 7.5,
    "INFY":      5.8,
    "TCS":       5.2,
}

# Cache: LTP data 1 second (aligned with broadcast interval), OHLC 60 seconds
_quote_cache: TTLCache = TTLCache(maxsize=50, ttl=1)
_ohlc_cache: TTLCache = TTLCache(maxsize=100, ttl=60)
_hist_cache: TTLCache = TTLCache(maxsize=50, ttl=300)


class KiteService:
    """Async-friendly Zerodha Kite Connect wrapper."""

    def __init__(self):
        self._kite: Optional[KiteConnect] = None
        self._access_token: Optional[str] = settings.kite_access_token or None
        self._initialized = False
        self._mock_start_price = {
            "NSE:NIFTY 50": 22000.0,
            "NSE:RELIANCE": 2900.0,
            "NSE:HDFCBANK": 1450.0,
            "NSE:ICICIBANK": 1050.0,
            "NSE:INFY": 1600.0,
            "NSE:TCS": 4000.0,
        }

        self._master_nfo = []
        self._last_nfo_load = None

    def _get_kite(self) -> KiteConnect:
        if self._kite is None:
            self._kite = KiteConnect(api_key=settings.kite_api_key)
        if self._access_token:
            self._kite.set_access_token(self._access_token)
        return self._kite

    async def load_instruments(self):
        """Load NFO instruments on startup."""
        if self._master_nfo and self._last_nfo_load and (datetime.now() - self._last_nfo_load).days < 1:
            return

        if not self.is_authenticated() and not settings.mock_mode:
            logger.warning("Cannot load instruments: Not authenticated")
            return

        loop = asyncio.get_event_loop()
        try:
            logger.info("Downloading NFO instruments master...")
            if settings.mock_mode:
                # Mock minimal master
                self._master_nfo = [
                    {"instrument_token": 1001, "exchange": "NFO", "tradingsymbol": "NIFTY24FEB22000CE", "name": "NIFTY", "instrument_type": "CE", "strike": 22000, "expiry": date(2024, 2, 29), "lot_size": 50},
                    {"instrument_token": 1002, "exchange": "NFO", "tradingsymbol": "NIFTY24FEB22000PE", "name": "NIFTY", "instrument_type": "PE", "strike": 22000, "expiry": date(2024, 2, 29), "lot_size": 50},
                ]
            else:
                kite = self._get_kite()
                instruments = await loop.run_in_executor(None, kite.instruments, "NFO")
                # Filter strictly for NIFTY OPTIDX
                self._master_nfo = [
                    i for i in instruments 
                    if i["name"] == "NIFTY" and i["segment"] == "NFO-OPT"
                ]
            
            self._last_nfo_load = datetime.now()
            logger.info(f"Loaded {len(self._master_nfo)} NIFTY option instruments")
        except Exception as e:
            logger.error(f"Failed to load instruments: {e}")

    def _get_nearest_expiry(self) -> Optional[date]:
        """Find the nearest weekly expiry from loaded instruments."""
        if not self._master_nfo:
            return None
        
        today = date.today()
        expiries = sorted(list(set(i["expiry"] for i in self._master_nfo)))
        
        for exp in expiries:
            if exp >= today:
                return exp
        return None

    async def get_options_data(self) -> Dict[str, Any]:
        """Get live PCR and OI for ATM +/- strikes."""
        if not self._master_nfo:
            await self.load_instruments()

        # Get spot price
        nifty_quote = await self.get_nifty_quote()
        spot_price = nifty_quote.get("last_price", 0)
        if spot_price == 0:
            return {}

        # Round to nearest 50 for ATM
        atm_strike = round(spot_price / 50) * 50
        # Track ATM and +/- 5 strikes (total 11 strikes)
        strikes_to_track = [atm_strike + (i * 50) for i in range(-5, 6)]
        
        expiry = self._get_nearest_expiry()
        if not expiry:
            return {}

        # Find tokens
        needed_tokens = []
        token_map = {} # token -> type (CE/PE)

        for i in self._master_nfo:
            if i["expiry"] == expiry and i["strike"] in strikes_to_track:
                needed_tokens.append(int(i["instrument_token"]))
                # Key: token, Value: {type: CE/PE, strike: 22000}
                token_map[int(i["instrument_token"])] = {
                    "type": i["instrument_type"],
                    "strike": i["strike"],
                    "symbol": i["tradingsymbol"]
                }
        
        if not needed_tokens:
            return {}

        # Fetch quotes
        quotes = await self.get_quote([str(t) for t in needed_tokens])
        
        total_ce_oi = 0
        total_pe_oi = 0
        strike_data = {}

        for token_id, q in quotes.items():
            token_int = int(token_id)
            if token_int in token_map:
                meta = token_map[token_int]
                oi = q.get("oi", 0)
                
                if meta["type"] == "CE":
                    total_ce_oi += oi
                elif meta["type"] == "PE":
                    total_pe_oi += oi

                # Organize by strike
                strike = meta["strike"]
                if strike not in strike_data:
                    strike_data[strike] = {"strike": strike, "ce_oi": 0, "pe_oi": 0}
                
                if meta["type"] == "CE":
                    strike_data[strike]["ce_oi"] = oi
                else:
                    strike_data[strike]["pe_oi"] = oi

        pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0
        
        return {
            "pcr": pcr,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            "atm_strike": atm_strike,
            "expiry": str(expiry),
            "strikes": sorted(list(strike_data.values()), key=lambda x: x["strike"])
        }

    async def get_atm_option_quote(self, spot_price: float, opt_type: str) -> Dict[str, Any]:
        """Fetch the quote and symbol for the ATM option given current spot price."""
        if not self._master_nfo:
            await self.load_instruments()
            
        atm_strike = round(spot_price / 50) * 50
        expiry = self._get_nearest_expiry()
        if not expiry:
            return {}

        token = None
        symbol = None
        for i in self._master_nfo:
            if i["expiry"] == expiry and i["strike"] == atm_strike and i["instrument_type"] == opt_type:
                token = i["instrument_token"]
                symbol = f"{i['exchange']}:{i['tradingsymbol']}"
                break
                
        if not token:
            return {}
            
        quotes = await self.get_quote([symbol])
        q = quotes.get(symbol)
        if q:
            return {
                "symbol": symbol,
                "price": q.get("last_price", 0),
                "strike": atm_strike,
                "token": token
            }
        return {}

    async def get_straddle_quotes(self, spot_price: float, expiry: Optional[date] = None) -> Dict[str, Any]:
        """
        Fetch quotes for both ATM CE and ATM PE simultaneously to form a short straddle.
        Returns combined premium and leg details.
        """
        if not self._master_nfo:
            await self.load_instruments()
            
        atm_strike = round(spot_price / 50) * 50
        target_expiry = expiry or self.get_expiry_for_trade()
        if not target_expiry:
            return {}

        ce_sym = None
        pe_sym = None
        
        for i in self._master_nfo:
            if i["expiry"] == target_expiry and i["strike"] == atm_strike:
                if i["instrument_type"] == "CE":
                    ce_sym = f"{i['exchange']}:{i['tradingsymbol']}"
                elif i["instrument_type"] == "PE":
                    pe_sym = f"{i['exchange']}:{i['tradingsymbol']}"
                    
        if not ce_sym or not pe_sym:
            return {}
            
        quotes = await self.get_quote([ce_sym, pe_sym])
        q_ce = quotes.get(ce_sym, {})
        q_pe = quotes.get(pe_sym, {})
        
        ce_price = float(q_ce.get("last_price", 0))
        pe_price = float(q_pe.get("last_price", 0))

        if ce_price <= 0 or pe_price <= 0:
            return {}

        return {
            "strike": atm_strike,
            "expiry": target_expiry,
            "combined_premium": round(ce_price + pe_price, 2),
            "ce": {"symbol": ce_sym, "price": ce_price},
            "pe": {"symbol": pe_sym, "price": pe_price}
        }


    def get_expiry_for_trade(self) -> Optional[date]:
        """
        Return the correct weekly expiry for a new trade.

        Rule (Expiry-Day Risk Control §8):
          - On expiry day before 12:00 PM IST → use CURRENT weekly expiry (nearest)
          - On expiry day at/after 12:00 PM IST → use NEXT weekly expiry
          - All other days → nearest weekly expiry as usual
        """
        if not self._master_nfo:
            return None

        today = date.today()
        expiries = sorted(set(i["expiry"] for i in self._master_nfo if i["expiry"] >= today))
        if not expiries:
            return None

        nearest = expiries[0]

        # Check: is today an expiry day AND is it past noon?
        if nearest == today and datetime.now().hour >= 12:
            # On expiry day after noon → skip to the next weekly expiry
            if len(expiries) > 1:
                return expiries[1]
            return None  # no next expiry found

        return nearest

    def get_expiry_for_symbol(self, symbol: str) -> Optional[date]:
        """Return the expiry date for a given tradingsymbol."""
        if not self._master_nfo:
            return None
        
        # Remove exchange prefix if present, e.g., NFO:NIFTY26FEB22500CE -> NIFTY26FEB22500CE
        clean_symbol = symbol.split(':')[-1] if ':' in symbol else symbol
        
        for i in self._master_nfo:
            if i["tradingsymbol"] == clean_symbol:
                return i.get("expiry")
        return None

    async def find_option_by_premium(
        self,
        spot_price: float,
        opt_type: str,         # "PE" or "CE"
        target_premium: float, # e.g. 125 (sell leg) or 25 (buy/hedge leg)
        expiry: Optional[date] = None,
        min_otm_distance: int = 0,   # minimum distance from ATM (in strikes of 50)
    ) -> Dict[str, Any]:
        """
        Scan OTM strikes to find the one whose current LTP is closest to target_premium.

        Strategy:
          - Builds a list of up to 12 candidate OTM strikes (step 50)
          - For PE: strikes go DOWN from ATM  (OTM puts are below spot)
          - For CE: strikes go UP from ATM    (OTM calls are above spot)
          - For the buy/hedge leg (target~25): starts further OTM (min_otm_distance≥4)
          - Batch-fetches all candidate quotes in ONE get_quote() call
          - Returns the strike with abs(LTP - target_premium) minimized

        Returns:
          {"symbol": str, "price": float, "strike": int, "expiry": date}
          or {} on failure
        """
        if not self._master_nfo:
            await self.load_instruments()
            if not self._master_nfo:
                return {}

        target_expiry = expiry or self.get_expiry_for_trade()
        if not target_expiry:
            return {}

        atm_strike = round(spot_price / 50) * 50
        STEP = 50

        # Build candidate strikes (OTM for PE = lower strikes; OTM for CE = higher strikes)
        if opt_type == "PE":
            candidates = [
                atm_strike - (i * STEP)
                for i in range(min_otm_distance, min_otm_distance + 12)
            ]
        else:  # CE
            candidates = [
                atm_strike + (i * STEP)
                for i in range(min_otm_distance, min_otm_distance + 12)
            ]

        # Build symbol list for candidates that exist in master NFO
        symbol_to_meta: Dict[str, Dict] = {}
        for instr in self._master_nfo:
            if (
                instr["expiry"] == target_expiry
                and instr["instrument_type"] == opt_type
                and instr["strike"] in candidates
            ):
                sym = f"{instr['exchange']}:{instr['tradingsymbol']}"
                symbol_to_meta[sym] = {
                    "strike":  instr["strike"],
                    "expiry":  target_expiry,
                    "symbol":  sym,
                }

        if not symbol_to_meta:
            logger.warning(
                f"find_option_by_premium: no candidates for {opt_type} target={target_premium} "
                f"expiry={target_expiry} spot={spot_price}"
            )
            return {}

        # Batch-fetch quotes
        quotes = await self.get_quote(list(symbol_to_meta.keys()))

        # Find closest LTP to target_premium
        best_sym, best_ltp, best_diff = None, 0.0, float("inf")
        for sym, meta in symbol_to_meta.items():
            q = quotes.get(sym, {})
            ltp = float(q.get("last_price", 0))
            if ltp <= 0:
                continue
            diff = abs(ltp - target_premium)
            if diff < best_diff:
                best_diff = diff
                best_sym  = sym
                best_ltp  = ltp

        if not best_sym:
            logger.warning(
                f"find_option_by_premium: no valid LTP found for {opt_type} target={target_premium}"
            )
            return {}

        meta = symbol_to_meta[best_sym]
        logger.info(
            f"find_option_by_premium: {opt_type} target=₹{target_premium} → "
            f"{best_sym} LTP=₹{best_ltp:.2f} strike={meta['strike']}"
        )
        return {
            "symbol": best_sym,
            "price":  round(best_ltp, 2),
            "strike": meta["strike"],
            "expiry": str(target_expiry),
        }


    async def exchange_token(self, request_token: str) -> str:
        """Exchange request_token for access_token."""
        loop = asyncio.get_event_loop()
        kite = KiteConnect(api_key=settings.kite_api_key)

        def _exchange():
            data = kite.generate_session(request_token, api_secret=settings.kite_api_secret)
            return data["access_token"]

        access_token = await loop.run_in_executor(None, _exchange)
        self._access_token = access_token
        self._kite = kite
        self._kite.set_access_token(access_token)
        logger.info("Zerodha access token exchanged successfully")
        
        # Persist to .env
        try:
            self._save_token_to_env(access_token)
        except Exception as e:
            logger.error(f"Failed to save token to .env: {e}")
            
        return access_token

    def _save_token_to_env(self, token: str):
        """Update the .env file with the new access token."""
        import os
        env_path = os.path.join(os.getcwd(), ".env")
        with open(env_path, "r") as f:
            lines = f.readlines()
        
        with open(env_path, "w") as f:
            for line in lines:
                if line.startswith("KITE_ACCESS_TOKEN="):
                    f.write(f"KITE_ACCESS_TOKEN={token}\n")
                else:
                    f.write(line)
        logger.info("Updated .env with new access token")

    def set_access_token(self, token: str):
        self._access_token = token
        if self._kite:
            self._kite.set_access_token(token)
        logger.info("Access token updated")

    def is_authenticated(self) -> bool:
        if settings.mock_mode:
            return True
        return bool(self._access_token)

    def get_login_url(self) -> str:
        kite = KiteConnect(api_key=settings.kite_api_key)
        return kite.login_url()

    def _generate_mock_quote(self, symbols: list) -> Dict[str, Any]:
        """Generate fake sine-wave data for off-market testing."""
        data = {}
        t = datetime.now().timestamp()
        for symbol in symbols:
            base_price = self._mock_start_price.get(symbol, 100.0)
            # Sine wave + random noise
            variation = math.sin(t / 10) * (base_price * 0.002) + random.uniform(-1, 1)
            price = round(base_price + variation, 2)
            change = round(price - base_price, 2)
            pct_change = round((change / base_price) * 100, 2)
            
            data[symbol] = {
                "instrument_token": 0,
                "timestamp": datetime.now(),
                "last_price": price,
                "ohlc": {
                    "open": base_price,
                    "high": base_price * 1.01,
                    "low": base_price * 0.99,
                    "close": base_price
                },
                "net_change": pct_change,
                "change": change,
                "volume": int(t % 10000) * 10
            }
        return data

    async def get_quote(self, symbols: list) -> Dict[str, Any]:
        """Fetch live quotes for given symbols with TTL cache."""
        if settings.mock_mode:
            return self._generate_mock_quote(symbols)

        cache_key = ",".join(sorted(symbols))
        if cache_key in _quote_cache:
            return _quote_cache[cache_key]

        loop = asyncio.get_event_loop()
        kite = self._get_kite()

        def _fetch():
            return kite.quote(symbols)

        try:
            data = await loop.run_in_executor(None, _fetch)
            _quote_cache[cache_key] = data
            return data
        except Exception as e:
            logger.error(f"Quote fetch failed: {e}")
            return {}

    async def get_nifty_quote(self) -> Dict[str, Any]:
        """Get live NIFTY 50 quote."""
        data = await self.get_quote(["NSE:NIFTY 50"])
        return data.get("NSE:NIFTY 50", {})

    async def get_vix_quote(self) -> Dict[str, Any]:
        """Get live India VIX quote."""
        try:
            data = await self.get_quote(["NSE:INDIA VIX"])
            q = data.get("NSE:INDIA VIX", {})
            ltp = q.get("last_price", 0)
            prev_close = q.get("ohlc", {}).get("close", 0)
            change = round(ltp - prev_close, 2) if prev_close else 0
            change_pct = round((change / prev_close) * 100, 2) if prev_close else 0
            return {
                "ltp": round(ltp, 2),
                "change": change,
                "change_pct": change_pct,
            }
        except Exception as e:
            logger.warning(f"VIX quote failed: {e}")
            return {"ltp": 0, "change": 0, "change_pct": 0}

    async def get_heavyweight_quotes(self) -> Dict[str, Any]:
        """Get quotes for all 5 heavyweight stocks."""
        symbols = list(NSE_SYMBOLS.values())
        data = await self.get_quote(symbols)
        result = {}
        for name, symbol in NSE_SYMBOLS.items():
            if name != "NIFTY 50" and symbol in data:
                q = data[symbol]
                
                # Manual calculation for robustness
                ltp = q.get("last_price", 0)
                ohlc_close = q.get("ohlc", {}).get("close", 0)
                
                if ohlc_close and ohlc_close > 0:
                    change = ltp - ohlc_close
                    pct_change = (change / ohlc_close) * 100
                else:
                    change = q.get("net_change", 0) or 0
                    pct_change = 0
                    
                weight = NIFTY_WEIGHTS.get(name, 0)
                # Approximate NIFTY point contribution
                nifty_ltp = 0
                nifty_data = data.get("NSE:NIFTY 50", {})
                nifty_ltp = nifty_data.get("last_price", 22000)
                nifty_impact = (pct_change / 100) * (weight / 100) * nifty_ltp

                result[name] = {
                    "symbol": name,
                    "ltp": ltp,
                    "change": round(change, 2),
                    "change_pct": round(pct_change, 2),
                    "nifty_impact": round(nifty_impact, 2),
                    "weight_pct": weight,
                    "ohlc": q.get("ohlc", {}),
                    "volume": q.get("volume", 0),
                }
        return result

    async def get_historical(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "5minute",
        continuous: bool = False,
    ) -> List[Dict]:
        """Fetch historical OHLCV candles with caching."""
        if settings.mock_mode:
            # Return plausible mock candles
            candles = []
            current = from_date
            price = 22000.0 if instrument_token == INSTRUMENT_TOKENS["NIFTY 50"] else 1000.0
            while current <= to_date:
                op = price
                cl = price + random.uniform(-10, 10)
                hi = max(op, cl) + random.uniform(0, 5)
                lo = min(op, cl) - random.uniform(0, 5)
                candles.append({
                    "date": current.isoformat(),
                    "open": op, "high": hi, "low": lo, "close": cl, "volume": 1000
                })
                price = cl
                current += timedelta(minutes=5)
            return candles

        # We bypass cache entirely for 1minute active strategies to prevent staleness
        if interval != "minute":
            cache_key = f"{instrument_token}_{interval}_{from_date.date()}_{to_date.date()}"
            if cache_key in _hist_cache:
                return _hist_cache[cache_key]

        loop = asyncio.get_event_loop()
        kite = self._get_kite()

        def _fetch():
            return kite.historical_data(
                instrument_token, from_date, to_date, interval, continuous
            )

        try:
            data = await loop.run_in_executor(None, _fetch)

            # Zerodha's Historical API returns 'date' as a datetime object (not a string).
            # Normalize every candle's date to ISO string for consistency downstream.
            for candle in data:
                d = candle.get("date")
                if isinstance(d, datetime):
                    candle["date"] = d.isoformat()

            # Patch last candle gap with the live quote so the strategy always has fresh data
            if interval == "minute" and instrument_token == INSTRUMENT_TOKENS["NIFTY 50"] and data:
                last_candle_time = datetime.fromisoformat(str(data[-1]["date"])).replace(tzinfo=None)
                now_time = datetime.now()
                if (now_time - last_candle_time).total_seconds() > 60:
                    live_q = await self.get_nifty_quote()
                    if live_q:
                        # Append the synthetic forming candle
                        data.append({
                            "date": now_time.isoformat(),
                            "open": live_q.get("ohlc", {}).get("open", live_q.get("last_price")),
                            "high": live_q.get("ohlc", {}).get("high", live_q.get("last_price")),
                            "low": live_q.get("ohlc", {}).get("low", live_q.get("last_price")),
                            "close": live_q.get("last_price", 0),
                            "volume": 0
                        })

            if interval != "minute":
                _hist_cache[cache_key] = data
            logger.debug(f"Fetched {len(data)} candles for token {instrument_token} ({interval})")
            return data
        except Exception as e:
            logger.error(f"Historical data fetch failed: {e}")
            return []

    async def get_nifty_candles(self, interval: str = "5minute", days: int = 5) -> List[Dict]:
        """Get NIFTY historical candles for strategy computation.

        For 1-minute interval (intraday strategies), fetches from today 9:00 AM IST
        so today's completed candles are always present in the returned data.
        For other intervals, fetches from (now - days).
        """
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        now_ist = datetime.now(ist)
        to_dt = now_ist

        if interval == "minute":
            # Always start from this morning so today's intraday candles are included
            from_dt = ist.localize(datetime(now_ist.year, now_ist.month, now_ist.day, 9, 0, 0))
        else:
            from_dt = now_ist - timedelta(days=days)

        return await self.get_historical(
            INSTRUMENT_TOKENS["NIFTY 50"], from_dt, to_dt, interval
        )

    async def get_profile(self) -> Dict:
        """Get user profile (validates token)."""
        if settings.mock_mode:
            return {"user_id": "MOCK_USER", "user_name": "Mock Trader"}
            
        loop = asyncio.get_event_loop()
        kite = self._get_kite()
        return await loop.run_in_executor(None, kite.profile)


# Singleton instance
kite_service = KiteService()
