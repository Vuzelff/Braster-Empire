#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Braster-Empire Bot
Strategy: EMA(20/50) cross met 200-EMA filter + TP/SL + Trailing Stop
Spot trading (buy/sell de coin), meerdere paren, cooldown-loop.
Werkt met Kraken via CCXT. 'Dry run' mogelijk voor veilig testen.
"""

import os
import time
import math
from typing import Dict, Optional

import ccxt
import pandas as pd
from dotenv import load_dotenv

# ========= .env laden (lokaal); op Render gebruikt hij dashboard envs =========
load_dotenv()

# ========= ENVIRONMENT VARIABELEN =========
API_KEY        = os.getenv("KRAKEN_API_KEY", "")
API_SECRET     = os.getenv("KRAKEN_API_SECRET", "")
PAIRS_RAW      = os.getenv("PAIRS", "BTC/USD,ETH/USD,ADA/USD")
TIMEFRAME      = os.getenv("TIMEFRAME", "15m")
FAST_EMA       = int(os.getenv("FAST_EMA", 20))
SLOW_EMA       = int(os.getenv("SLOW_EMA", 50))
REQUIRE_EMA200 = os.getenv("REQUIRE_EMA200", "true").lower() == "true"
BASE_SIZE_USD  = float(os.getenv("BASE_SIZE_USD", 25))
TP_PCT         = float(os.getenv("TP_PCT", 1.5)) / 100.0     # 1.5 => 0.015
SL_PCT         = float(os.getenv("SL_PCT", 0.5)) / 100.0     # 0.5 => 0.005
TRAIL_PCT      = float(os.getenv("TRAIL_PCT", 0.3)) / 100.0  # 0.3 => 0.003
COOLDOWN_S     = int(os.getenv("COOLDOWN_S", 90))
DRY_RUN        = os.getenv("DRY_RUN", "false").lower() == "true"

PAIRS = [p.strip().upper() for p in PAIRS_RAW.split(",") if p.strip()]

# ========= HELPERS =========
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def fetch_ohlcv_dataframe(ex: ccxt.Exchange, symbol: str, tf: str, limit: int = 300) -> Optional[pd.DataFrame]:
    try:
        ohlcv = ex.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
        if not ohlcv or len(ohlcv) < max(SLOW_EMA, 200) + 5:
            return None
        df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        return df
    except Exception as e:
        print(f"[{symbol}] Fout bij ophalen OHLCV: {e}")
        return None

def position_size_in_base(base_usd: float, price: float) -> float:
    if price <= 0:
        return 0.0
    # rond af naar 6 decimalen om te passen bij de meeste kraken paren
    amt = base_usd / price
    return max(0.0, round(amt, 6))

# ========== EXCHANGE ==========
def make_exchange() -> ccxt.Exchange:
    kraken = ccxt.kraken({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        # Kraken verlangt 'USD' of 'USDT' afhankelijk van het paar; we gebruiken 'USD' zoals gevraagd
    })
    return kraken

# ========== STATE (in-memory) ==========
class TradeState:
    def __init__(self):
        self.in_pos: Dict[str, bool] = {}
        self.entry_price: Dict[str, float] = {}
        self.highest_since_entry: Dict[str, float] = {}

STATE = TradeState()

# ========== SIGNALS ==========
def compute_signals(df: pd.DataFrame) -> Dict[str, float]:
    """Retourneert laatste waarden die we nodig hebben."""
    df["ema_fast"]  = ema(df["close"], FAST_EMA)
    df["ema_slow"]  = ema(df["close"], SLOW_EMA)
    df["ema_200"]   = ema(df["close"], 200)

    # Cross: fast boven/onder slow (laatste twee candles voor 'confirm')
    fast_prev, fast_now = df["ema_fast"].iloc[-2], df["ema_fast"].iloc[-1]
    slow_prev, slow_now = df["ema_slow"].iloc[-2], df["ema_slow"].iloc[-1]

    cross_up   = (fast_prev <= slow_prev) and (fast_now > slow_now)
    cross_down = (fast_prev >= slow_prev) and (fast_now < slow_now)

    last_close   = float(df["close"].iloc[-1])
    ema200_now   = float(df["ema_200"].iloc[-1])

    return {
        "last_close": last_close,
        "ema200": ema200_now,
        "cross_up": cross_up,
        "cross_down": cross_down
    }

# ========== ORDER FUNCTIES ==========
def buy(ex: ccxt.Exchange, symbol: str, price: float):
    amount = position_size_in_base(BASE_SIZE_USD, price)
    if amount <= 0:
        print(f"[{symbol}] Geen geldige amount berekend, skip.")
        return

    if DRY_RUN:
        print(f"[{symbol}] (DRY) BUY market amount={amount}")
    else:
        try:
            ex.create_order(symbol, "market", "buy", amount)
            print(f"[{symbol}] BUY market amount={amount}")
        except Exception as e:
            print(f"[{symbol}] Fout bij BUY: {e}")
            return

    STATE.in_pos[symbol] = True
    STATE.entry_price[symbol] = price
    STATE.highest_since_entry[symbol] = price

def sell_all(ex: ccxt.Exchange, symbol: str):
    """Verkoop volledige positie (spot). We vragen balance op en verkopen base-asset."""
    try:
        base = symbol.split("/")[0]
        bal  = ex.fetch_balance()
        free = float(bal.get(base, {}).get("free", 0.0))
    except Exception as e:
        print(f"[{symbol}] Fout balance ophalen: {e}")
        free = 0.0

    if free <= 0:
        # fallback: schat amount op basis van entry (niet perfect, maar voorkomt stilstand)
        print(f"[{symbol}] Geen free balance gevonden; fallback naar geschatte amount.")
        price = STATE.entry_price.get(symbol, 0) or 0
        amount = position_size_in_base(BASE_SIZE_USD, price)
    else:
        amount = round(free, 6)

    if amount <= 0:
        print(f"[{symbol}] Geen amount om te verkopen.")
        return

    if DRY_RUN:
        print(f"[{symbol}] (DRY) SELL market amount={amount}")
    else:
        try:
            ex.create_order(symbol, "market", "sell", amount)
            print(f"[{symbol}] SELL market amount={amount}")
        except Exception as e:
            print(f"[{symbol}] Fout bij SELL: {e}")
            return

    STATE.in_pos[symbol] = False
    STATE.entry_price[symbol] = 0.0
    STATE.highest_since_entry[symbol] = 0.0

# ========== MAIN LOOP ==========
def run():
    print("=== Braster-Empire bot gestart ===")
    print(f"Pairs   : {', '.join(PAIRS)}")
    print(f"TF      : {TIMEFRAME} | EMA {FAST_EMA}/{SLOW_EMA} | Filter 200-EMA={REQUIRE_EMA200}")
    print(f"TP={TP_PCT*100:.2f}% SL={SL_PCT*100:.2f}% Trail={TRAIL_PCT*100:.2f}% | DryRun={DRY_RUN}")
    print(f"Base per trade: ${BASE_SIZE_USD} | Cooldown: {COOLDOWN_S}s")
    ex = make_exchange()

    # Kraken marktsymbolen kunnen andere weergaven hebben; forceer laad van markets
    try:
        ex.load_markets()
    except Exception as e:
        print(f"Fout load_markets: {e}")

    # init state
    for s in PAIRS:
        STATE.in_pos.setdefault(s, False)
        STATE.entry_price.setdefault(s, 0.0)
        STATE.highest_since_entry.setdefault(s, 0.0)

    while True:
        cycle_start = time.time()

        for symbol in PAIRS:
            try:
                df = fetch_ohlcv_dataframe(ex, symbol, TIMEFRAME)
                if df is None:
                    print(f"[{symbol}] Onvoldoende candles, skip.")
                    continue

                sig = compute_signals(df)
                price = sig["last_close"]

                # update trailing high als we in positie zijn
                if STATE.in_pos.get(symbol, False):
                    STATE.highest_since_entry[symbol] = max(
                        STATE.highest_since_entry.get(symbol, price), price
                    )

                # BUY-LOGICA
                if not STATE.in_pos.get(symbol, False):
                    cond_cross = sig["cross_up"]
                    cond_filter = True if not REQUIRE_EMA200 else (price > sig["ema200"])
                    if cond_cross and cond_filter:
                        print(f"[{symbol}] BUY-signaal: cross_up en filter={cond_filter} @ {price}")
                        buy(ex, symbol, price)
                    else:
                        # geen koop, enkel loggen
                        pass

                # SELL-LOGICA
                else:
                    entry = STATE.entry_price.get(symbol, 0.0)
                    if entry <= 0:
                        # fail-safe
                        STATE.in_pos[symbol] = False
                        continue

                    take_profit = price >= entry * (1 + TP_PCT)
                    stop_loss   = price <= entry * (1 - SL_PCT)

                    # trailing: verkoop als we X% onder hoogste sinds entry komen
                    h = STATE.highest_since_entry.get(symbol, entry)
                    trail_hit = (price <= h * (1 - TRAIL_PCT)) and (h > entry)

                    cross_down = sig["cross_down"]

                    if take_profit or stop_loss or trail_hit or cross_down:
                        reason = []
                        if take_profit: reason.append("TP")
                        if stop_loss:   reason.append("SL")
                        if trail_hit:   reason.append("TRAIL")
                        if cross_down:  reason.append("CROSS_DOWN")
                        print(f"[{symbol}] SELL-signaal ({'+'.join(reason)}) @ {price} (entry {entry})")
                        sell_all(ex, symbol)

            except Exception as e:
                print(f"[{symbol}] Onverwachte fout: {e}")

        # Cooldown tot volgende cyclus
        elapsed = time.time() - cycle_start
        sleep_for = max(1, COOLDOWN_S - int(elapsed))
        time.sleep(sleep_for)

# ========== ENTRYPOINT ==========
if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("Stop door gebruiker.")
