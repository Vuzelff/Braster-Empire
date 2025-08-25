#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Braster-Empire Bot (maker-only)
Strategy: EMA(20/50) cross met 200-EMA filter + TP/SL + Trailing Stop
Spot trading (buy/sell de coin), meerdere paren, cooldown-loop.
Kraken via CCXT. 'Dry run' mogelijk.
BUY = limit @ best BID (maker) | SELL = limit @ best ASK (maker)
Ongevulde orders worden na ORDER_REFRESH_S geannuleerd en herplaatst.
"""

import os
import time
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
ORDER_REFRESH_S= int(os.getenv("ORDER_REFRESH_S", 30))       # NIEUW: herprijs-interval
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

# --- Orderbook & precisie helpers ---
def get_market_limits(ex, symbol):
    m = ex.market(symbol)
    amount_min = m.get("limits", {}).get("amount", {}).get("min", 0) or 0
    cost_min   = m.get("limits", {}).get("cost", {}).get("min", 0) or 0
    amt_prec   = m.get("precision", {}).get("amount", 6) or 6
    price_prec = m.get("precision", {}).get("price", 2) or 2
    return amount_min, cost_min, amt_prec, price_prec

def round_amount(amount: float, prec: int) -> float:
    q = 10 ** prec
    return max(0.0, (int(amount * q)) / q)

def round_price(price: float, prec: int) -> float:
    q = 10 ** prec
    return (int(price * q)) / q

def best_bid_ask(ex: ccxt.Exchange, symbol: str):
    ob = ex.fetch_order_book(symbol, limit=5)
    bid = ob['bids'][0][0] if ob['bids'] else None
    ask = ob['asks'][0][0] if ob['asks'] else None
    return bid, ask

def position_size_limit(ex: ccxt.Exchange, symbol: str, price: float) -> float:
    """base USD -> amount, rekening houdend met min cost/amount & precisie"""
    if price <= 0:
        return 0.0
    amount_min, cost_min, amt_prec, _ = get_market_limits(ex, symbol)
    amt = BASE_SIZE_USD / price
    if cost_min and amt * price < cost_min:
        amt = cost_min / price
    if amount_min and amt < amount_min:
        amt = amount_min
    return round_amount(amt, amt_prec)

# ========== EXCHANGE ==========
def make_exchange() -> ccxt.Exchange:
    kraken = ccxt.kraken({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
    })
    return kraken

# ========== STATE (in-memory) ==========
class TradeState:
    def __init__(self):
        self.in_pos: Dict[str, bool] = {}
        self.entry_price: Dict[str, float] = {}
        self.highest_since_entry: Dict[str, float] = {}
        # open order tracking (maker)
        self.open_order_id: Dict[str, Optional[str]] = {}
        self.open_order_side: Dict[str, Optional[str]] = {}
        self.order_ts: Dict[str, float] = {}

STATE = TradeState()

# ========== SIGNALS ==========
def compute_signals(df: pd.DataFrame):
    df["ema_fast"]  = ema(df["close"], FAST_EMA)
    df["ema_slow"]  = ema(df["close"], SLOW_EMA)
    df["ema_200"]   = ema(df["close"], 200)

    fast_prev, fast_now = df["ema_fast"].iloc[-2], df["ema_fast"].iloc[-1]
    slow_prev, slow_now = df["ema_slow"].iloc[-2], df["ema_slow"].iloc[-1]

    cross_up   = (fast_prev <= slow_prev) and (fast_now > slow_now)
    cross_down = (fast_prev >= slow_prev) and (fast_now < slow_now)

    last_close   = float(df["close"].iloc[-1])
    ema200_now   = float(df["ema_200"].iloc[-1])

    return {"last_close": last_close, "ema200": ema200_now, "cross_up": cross_up, "cross_down": cross_down}

# ========== ORDER FUNCTIES (maker-only) ==========
def buy(ex: ccxt.Exchange, symbol: str):
    """LIMIT BUY @ best bid (maker)."""
    try:
        bid, _ = best_bid_ask(ex, symbol)
        if bid is None:
            print(f"[{symbol}] Geen bid in orderboek.")
            return
        _, _, amt_prec, price_prec = get_market_limits(ex, symbol)
        price = round_price(bid, price_prec)
        amt = position_size_limit(ex, symbol, price)
        if amt <= 0:
            print(f"[{symbol}] Amount=0 bij price={price}")
            return

        if DRY_RUN:
            print(f"[{symbol}] (DRY) LIMIT BUY {amt} @ {price}")
            oid = f"dry-{time.time()}"
        else:
            o = ex.create_limit_buy_order(symbol, amt, price)
            oid = o.get("id")

        STATE.open_order_id[symbol] = oid
        STATE.open_order_side[symbol] = "buy"
        STATE.order_ts[symbol] = time.time()
        print(f"[{symbol}] LIMIT BUY geplaatst id={oid} {amt}@{price}")

    except Exception as e:
        print(f"[{symbol}] Fout bij LIMIT BUY: {e}")

def sell_all(ex: ccxt.Exchange, symbol: str):
    """LIMIT SELL @ best ask (maker) voor volledige positie."""
    try:
        base = symbol.split("/")[0]
        bal  = ex.fetch_balance()
        free = float(bal.get(base, {}).get("free", 0.0))
    except Exception as e:
        print(f"[{symbol}] Balance fout: {e}")
        free = 0.0

    if free <= 0:
        print(f"[{symbol}] Geen vrij saldo om te verkopen.")
        return

    try:
        _, ask = best_bid_ask(ex, symbol)
        if ask is None:
            print(f"[{symbol}] Geen ask in orderboek.")
            return
        _, _, amt_prec, price_prec = get_market_limits(ex, symbol)
        amount = round_amount(free, amt_prec)
        price = round_price(ask, price_prec)

        if DRY_RUN:
            print(f"[{symbol}] (DRY) LIMIT SELL {amount} @ {price}")
            oid = f"dry-{time.time()}"
        else:
            o = ex.create_limit_sell_order(symbol, amount, price)
            oid = o.get("id")

        STATE.open_order_id[symbol] = oid
        STATE.open_order_side[symbol] = "sell"
        STATE.order_ts[symbol] = time.time()
        print(f"[{symbol}] LIMIT SELL geplaatst id={oid} {amount}@{price}")
    except Exception as e:
        print(f"[{symbol}] Fout bij LIMIT SELL: {e}")

# ========== MAIN LOOP ==========
def run():
    print("=== Braster-Empire bot (maker) gestart ===")
    print(f"Pairs   : {', '.join(PAIRS)}")
    print(f"TF      : {TIMEFRAME} | EMA {FAST_EMA}/{SLOW_EMA} | Filter 200-EMA={REQUIRE_EMA200}")
    print(f"TP={TP_PCT*100:.2f}% SL={SL_PCT*100:.2f}% Trail={TRAIL_PCT*100:.2f}% | DryRun={DRY_RUN}")
    print(f"Base per trade: ${BASE_SIZE_USD} | Cooldown: {COOLDOWN_S}s | Refresh: {ORDER_REFRESH_S}s")
    ex = make_exchange()

    try:
        ex.load_markets()
    except Exception as e:
        print(f"Fout load_markets: {e}")

    for s in PAIRS:
        STATE.in_pos.setdefault(s, False)
        STATE.entry_price.setdefault(s, 0.0)
        STATE.highest_since_entry.setdefault(s, 0.0)
        STATE.open_order_id.setdefault(s, None)
        STATE.open_order_side.setdefault(s, None)
        STATE.order_ts.setdefault(s, 0.0)

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

                # ===== Order manager (check open orders, reprice indien nodig) =====
                oid = STATE.open_order_id.get(symbol)
                if oid:
                    try:
                        o = ex.fetch_order(oid, symbol) if not DRY_RUN else {"status": "open", "price": price}
                        status = (o.get("status") or "").lower()
                        if status in ("closed", "filled"):
                            print(f"[{symbol}] Order {oid} filled.")
                            if STATE.open_order_side.get(symbol) == "buy":
                                STATE.in_pos[symbol] = True
                                got_price = float(o.get("price") or 0.0) or price
                                STATE.entry_price[symbol] = got_price
                                STATE.highest_since_entry[symbol] = got_price
                            else:
                                STATE.in_pos[symbol] = False
                                STATE.entry_price[symbol] = 0.0
                                STATE.highest_since_entry[symbol] = 0.0
                            STATE.open_order_id[symbol] = None
                            STATE.open_order_side[symbol] = None
                            STATE.order_ts[symbol] = 0.0
                        else:
                            if time.time() - STATE.order_ts.get(symbol, 0) >= ORDER_REFRESH_S:
                                print(f"[{symbol}] Order {oid} niet gevuld -> herprijzen.")
                                if not DRY_RUN:
                                    try:
                                        ex.cancel_order(oid, symbol)
                                    except Exception as ce:
                                        print(f"[{symbol}] Cancel fout: {ce}")
                                STATE.open_order_id[symbol] = None
                                STATE.open_order_side[symbol] = None
                                # opnieuw plaatsen volgens huidige side/positie
                                if STATE.in_pos.get(symbol, False):
                                    sell_all(ex, symbol)
                                else:
                                    buy(ex, symbol)
                    except Exception as oe:
                        print(f"[{symbol}] Order check fout: {oe}")

                # ===== Signalen & trade-logica =====
                if not STATE.in_pos.get(symbol, False) and not STATE.open_order_id.get(symbol):
                    cond_cross  = sig["cross_up"]
                    cond_filter = True if not REQUIRE_EMA200 else (price > sig["ema200"])
                    if cond_cross and cond_filter:
                        print(f"[{symbol}] BUY-signaal: cross_up en filter={cond_filter}")
                        buy(ex, symbol)

                elif STATE.in_pos.get(symbol, False) and not STATE.open_order_id.get(symbol):
                    entry = STATE.entry_price.get(symbol, 0.0)
                    if entry > 0:
                        # update trailing high
                        STATE.highest_since_entry[symbol] = max(
                            STATE.highest_since_entry.get(symbol, entry), price
                        )
                        take_profit = price >= entry * (1 + TP_PCT)
                        stop_loss   = price <= entry * (1 - SL_PCT)

                        h = STATE.highest_since_entry.get(symbol, entry)
                        trail_hit = (price <= h * (1 - TRAIL_PCT)) and (h > entry)

                        cross_down = sig["cross_down"]

                        if take_profit or stop_loss or trail_hit or cross_down:
                            reason = []
                            if take_profit: reason.append("TP")
                            if stop_loss:   reason.append("SL")
                            if trail_hit:   reason.append("TRAIL")
                            if cross_down:  reason.append("CROSS_DOWN")
                            print(f"[{symbol}] SELL-signaal ({'+'.join(reason)})")
                            sell_all(ex, symbol)
                    else:
                        # fail-safe
                        STATE.in_pos[symbol] = False

            except Exception as e:
                print(f"[{symbol}] Onverwachte fout: {e}")

        # Cooldown
        elapsed = time.time() - cycle_start
        sleep_for = max(1, COOLDOWN_S - int(elapsed))
        time.sleep(sleep_for)

# ========== ENTRYPOINT ==========
if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("Stop door gebruiker.")