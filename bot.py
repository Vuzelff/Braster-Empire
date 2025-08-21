# -*- coding: utf-8 -*-
# Kraken USD-only Multi‑Pair Bot • ccxt
# - scant USD paren (NO USDT)
# - 15m breakout + EMA(12/26) trendfilter
# - TP/SL + ALTijd‑aan trailing stop (softwarematig)
# - DRY_RUN standaard aan (veilig testen)
import os, time
from datetime import datetime
import ccxt

def env(k, d=None, cast=str):
    v = os.getenv(k, d)
    if v is None: raise RuntimeError(f"ENV {k} ontbreekt")
    if cast is bool:  return str(v).lower() in ("1","true","yes","y","on")
    if cast is int:   return int(float(v))
    if cast is float: return float(v)
    return v

def now(): return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def ema(vals, n):
    k = 2.0/(n+1.0); out=[]; prev=None
    for x in vals:
        prev = x if prev is None else prev + k*(x-prev)
        out.append(prev)
    return out

# -------- ENV --------
API_KEY        = env("KRAKEN_API_KEY")
API_SECRET     = env("KRAKEN_API_SECRET")
PAIR           = env("PAIR", "all")             # "all" of bv "BTC/USD,ETH/USD"
FUTURES        = env("FUTURES", "false", bool)
LEVERAGE       = env("LEVERAGE", "1", float)
BASE_SIZE_USD  = env("BASE_SIZE_USD", "50", float)

TIMEFRAME      = env("TIMEFRAME", "15m")
TP_PCT         = env("TP_PCT", "1.5", float)    # take profit %
SL_PCT         = env("SL_PCT", "0.7", float)    # stop loss %
TRAIL_PCT      = env("TRAIL_PCT", "0.3", float) # trailing afstand %
ORDER_TYPE     = env("ORDER_TYPE", "limit")     # limit/market
LIMIT_OFF_PCT  = env("LIMIT_OFFSET_PCT", "0.03", float)  # limit beter dan last
COOLDOWN_S     = env("COOLDOWN_S", "60", int)
DRY_RUN        = env("DRY_RUN", "true", bool)

# -------- Exchange --------
ex = ccxt.krakenfutures({'apiKey':API_KEY,'secret':API_SECRET,'enableRateLimit':True}) if FUTURES else \
     ccxt.kraken({'apiKey':API_KEY,'secret':API_SECRET,'enableRateLimit':True})

# -------- Utils --------
def load_symbols():
    markets = ex.load_markets()
    if PAIR.strip().lower() == "all":
        return [s for s in markets if "/USD" in s and markets[s].get("active", True)]
    if "," in PAIR:
        wanted = [x.strip() for x in PAIR.split(",")]
        return [s for s in wanted if s in markets]
    return [PAIR] if PAIR in markets else []

def last_price(sym): return float(ex.fetch_ticker(sym)["last"])

def usd_to_amount(sym, usd):
    px = last_price(sym)
    qty = usd / px
    try:
        m = ex.market(sym)
        prec = m.get("precision", {}).get("amount")
        if prec is not None: qty = round(qty, prec)
        else: qty = round(qty, 4)
        min_amt = m.get("limits", {}).get("amount", {}).get("min", 0.0) or 0.0
        if min_amt: qty = max(qty, float(min_amt))
    except Exception:
        qty = max(round(qty, 4), 0.0001)
    return float(qty)

# -------- Signal: 15m breakout + EMA filter --------
def breakout_signal(sym):
    ohlc = ex.fetch_ohlcv(sym, timeframe=TIMEFRAME, limit=60)
    closes = [c[4] for c in ohlc]
    if len(closes) < 40: return False
    ema_fast = ema(closes, 12)
    ema_slow = ema(closes, 26)
    last_close = closes[-1]
    prev_high = max(c[2] for c in ohlc[-21:-1])  # high van vorige 20 candles
    trend_ok = ema_fast[-1] > ema_slow[-1]
    return last_close > prev_high and trend_ok

# -------- Orders + trailing --------
def place_orders(sym, side, entry_px, amount):
    tp_px = round(entry_px * (1 + TP_PCT/100.0), 6)
    sl_px = round(entry_px * (1 - SL_PCT/100.0), 6)
    print(f"[{now()}] ENTRY {side} {amount} {sym} @ {entry_px} | TP={tp_px} SL={sl_px} trail={TRAIL_PCT}%")
    if DRY_RUN:
        return {"entry_px":entry_px,"tp_px":tp_px,"sl_px":sl_px,"amount":amount,"best":entry_px,"ids":{}}

    params = {}
    if FUTURES: params["leverage"] = LEVERAGE
    if ORDER_TYPE == "limit":
        px = entry_px * (1 - LIMIT_OFF_PCT/100.0)
        entry = ex.create_order(sym, "limit", side, amount, px, {**params,"postOnly":True})
    else:
        entry = ex.create_order(sym, "market", side, amount, None, params)

    reduce = {"reduceOnly": True} if FUTURES else {}
    close_side = "sell" if side=="buy" else "buy"
    tp = ex.create_order(sym, "limit", close_side, amount, tp_px, {**reduce})
    sl = ex.create_order(sym, "stop",  close_side, amount, sl_px, {**reduce, "triggerPrice": sl_px})

    return {"entry_px":entry_px,"tp_px":tp_px,"sl_px":sl_px,"amount":amount,"best":entry_px,
            "ids":{"entry":entry.get("id"),"tp":tp.get("id"),"sl":sl.get("id")}}

def manage_trailing(sym, state):
    px = last_price(sym)
    if px > state["best"]:
        state["best"] = px
        new_sl = round(state["best"] * (1 - TRAIL_PCT/100.0), 6)
        if new_sl > state["sl_px"]:
            print(f"[{now()}] TRAIL {sym}: SL {state['sl_px']} → {new_sl}")
            state["sl_px"] = new_sl
            if not DRY_RUN:
                try:
                    if state["ids"].get("sl"):
                        ex.cancel_order(state["ids"]["sl"], sym)
                except Exception:
                    pass
                sl_side = "sell"  # long only (spot)
                sl = ex.create_order(sym, "stop", sl_side, state["amount"], new_sl,
                                     {"triggerPrice": new_sl, **({"reduceOnly": True} if FUTURES else {})})
                state["ids"]["sl"] = sl.get("id")

# -------- Main loop --------
def run():
    symbols = load_symbols()
    if not symbols: raise RuntimeError("Geen USD‑pairs gevonden. Check PAIR/env.")
    print(f"=== {now()} • Kraken • Pairs={symbols} • Futures={FUTURES} • Lev={LEVERAGE}x • DRY_RUN={DRY_RUN}")
    last_trade = {s:0 for s in symbols}
    active = {s:None for s in symbols}

    while True:
        try:
            for s in symbols:
                # trailing beheren
                if active[s]: manage_trailing(s, active[s])

                # cooldown
                if time.time()-last_trade[s] < COOLDOWN_S: continue

                # alleen LONG breakout (veilig voor spot)
                if breakout_signal(s):
                    px = last_price(s)
                    amt = usd_to_amount(s, BASE_SIZE_USD)
                    state = place_orders(s, "buy", px, amt)
                    active[s] = state
                    last_trade[s] = time.time()
            time.sleep(3)
        except Exception as e:
            print(f"[{now()}] Fout: {e}")
            time.sleep(COOLDOWN_S)

if __name__ == "__main__":
    run()