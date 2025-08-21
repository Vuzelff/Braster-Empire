# bot.py  — Braster Empire Multi‑Strategy Bot (Kraken / ccxt)
import os, time, math
from datetime import datetime
import ccxt

def env(name, default=None, cast=str):
    v = os.getenv(name, default)
    if v is None: raise RuntimeError(f"ENV {name} ontbreekt")
    if cast is bool:
        return str(v).lower() in ("1","true","yes","y","on")
    return cast(v)

# ====== CONFIG ======
API_KEY      = env("KRAKEN_API_KEY")
API_SECRET   = env("KRAKEN_API_SECRET")
PAIR         = env("PAIR",        "XRP/USDT")
STRATEGY     = env("STRATEGY",    "long").lower()  # long/short/scalp/swing/breakout/highlev
FUTURES      = env("FUTURES",     "false", bool)   # true = krakenfutures, false = spot
LEVERAGE     = env("LEVERAGE",    "1", float)
BASE_SIZE_USD= env("BASE_SIZE_USD","50", float)    # ordergrootte in USD
TP_PCT       = env("TP_PCT",      "1.0", float)    # +% vanaf entry
SL_PCT       = env("SL_PCT",      "0.5", float)    # -% vanaf entry
TRAIL_PCT    = env("TRAIL_PCT",   "0.0", float)    # trailing afstand in %
ORDER_TYPE   = env("ORDER_TYPE",  "limit")         # 'limit' of 'market'
LIMIT_OFF_PCT= env("LIMIT_OFFSET_PCT","0.05", float)  # limiet-bettering voor entry (bv. 0.05% = 0.0005)
COOLDOWN_S   = env("COOLDOWN_S",  "60", int)
DRY_RUN      = env("DRY_RUN",     "true", bool)

# ====== EXCHANGE ======
ex = ccxt.krakenfutures({'apiKey':API_KEY,'secret':API_SECRET}) if FUTURES \
   else ccxt.kraken({'apiKey':API_KEY,'secret':API_SECRET,'enableRateLimit':True})

def now(): return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def mkt_price(symbol):
    return float(ex.fetch_ticker(symbol)['last'])

def usd_to_amount(symbol, usd):
    px = mkt_price(symbol)
    # afronden op 4 decimals (pas desnoods aan per pair)
    return max(round(usd/px, 4), 0.0001)

def side_and_sign(strategy):
    """return (side, dir) waarbij dir=+1 voor long en -1 voor short"""
    if strategy in ("long","scalp","swing","breakout","highlev"):
        return "buy", +1
    if strategy=="short":
        return "sell", -1
    raise ValueError("Onbekende strategy")

def defaults_for(strategy):
    """Handige default‑instellingen per strategie (worden alleen gebruikt als je ze niet in .env overschrijft)."""
    presets = {
        "long":     dict(tp=2.0,  sl=1.0,  trail=0.0),
        "short":    dict(tp=2.0,  sl=1.0,  trail=0.0),
        "scalp":    dict(tp=1.0,  sl=0.5,  trail=0.1),
        "swing":    dict(tp=5.0,  sl=2.0,  trail=0.7),
        "breakout": dict(tp=2.5,  sl=1.0,  trail=0.4),
        "highlev":  dict(tp=1.5,  sl=0.7,  trail=0.2),
    }
    return presets.get(strategy, presets["long"])

def place_bracket(symbol, entry_side, dir_sign, entry_px):
    """
    Plaats entry + OCO (TP & SL). Trailing beheren we ‘software‑matig’ door de SL te verhogen/verlagen.
    """
    amount = usd_to_amount(symbol, BASE_SIZE_USD)
    tp_px = round(entry_px * (1 + dir_sign*TP_PCT/100.0), 6)
    sl_px = round(entry_px * (1 - dir_sign*SL_PCT/100.0), 6)

    print(f"[{now()}] ENTRY {entry_side} {amount} {symbol} @ {entry_px}  TP={tp_px}  SL={sl_px}  trail={TRAIL_PCT}%")
    if DRY_RUN:
        return {"entry_px": entry_px, "tp_px": tp_px, "sl_px": sl_px, "amount": amount, "ids":{}}

    # ---- Entry
    params = {}
    if FUTURES: params['leverage'] = LEVERAGE
    if ORDER_TYPE == "limit":
        order = ex.create_order(symbol, 'limit', entry_side, amount,
                                entry_px * (1 - dir_sign*LIMIT_OFF_PCT/100.0), params)
    else:
        order = ex.create_order(symbol, 'market', entry_side, amount, None, params)

    # ---- SL + TP: Kraken spot kent geen “unified” OCO via ccxt; we plaatsen 2 reduce‑only orders.
    reduce = {'reduceOnly': True} if FUTURES else {}
    tp = ex.create_order(symbol, 'limit', 'sell' if dir_sign>0 else 'buy', amount, tp_px, reduce)
    sl = ex.create_order(symbol, 'stop',  'sell' if dir_sign>0 else 'buy', amount, sl_px, {**reduce, 'triggerPrice': sl_px})

    return {"entry_px": entry_px, "tp_px": tp_px, "sl_px": sl_px, "amount": amount, "ids":{"entry":order["id"],"tp":tp["id"],"sl":sl["id"]} if not DRY_RUN else {}}

def manage_trailing(symbol, dir_sign, state):
    """Eenvoudige trailing: schuif SL mee zodra de move > TRAIL_PCT is. (Periodiek aanroepen)"""
    if TRAIL_PCT <= 0 or DRY_RUN: return
    best = state.get("best", state["entry_px"])
    px = mkt_price(symbol)
    moved_pct = (px/best - 1.0)*100.0 if dir_sign>0 else (best/px - 1.0)*100.0
    if (dir_sign>0 and px>best) or (dir_sign<0 and px<best):
        best = px
        # nieuwe SL
        new_sl = round(best*(1 - dir_sign*TRAIL_PCT/100.0), 6)
        if (dir_sign>0 and new_sl>state["sl_px"]) or (dir_sign<0 and new_sl<state["sl_px"]):
            print(f"[{now()}] TRAIL: update SL {state['sl_px']} → {new_sl}")
            state["sl_px"] = new_sl
            # In productie: cancel oude SL‑order en maak nieuwe (ids in state['ids'])
            # (Hier laten we de daadwerkelijke cancel/replace weg om het kort te houden)
    state["best"] = best

def choose_params_by_strategy():
    d = defaults_for(STRATEGY)
    # alleen overschrijven als je niets in .env meegaf
    tp = TP_PCT if "TP_PCT" in os.environ else d["tp"]
    sl = SL_PCT if "SL_PCT" in os.environ else d["sl"]
    tr = TRAIL_PCT if "TRAIL_PCT" in os.environ else d["trail"]
    return tp, sl, tr

def main():
    global TP_PCT, SL_PCT, TRAIL_PCT
    TP_PCT, SL_PCT, TRAIL_PCT = choose_params_by_strategy()

    entry_side, dir_sign = side_and_sign(STRATEGY)
    print(f"=== {now()} • Strategy={STRATEGY} • Pair={PAIR} • Futures={FUTURES} • Lev={LEVERAGE}x • DRY_RUN={DRY_RUN}")

    last_trade_ts = 0
    while True:
        try:
            px = mkt_price(PAIR)

            # ---- ENTRY LOGICA PER STRATEGIE (heel compact gehouden)
            go = False
            if STRATEGY == "long":      go = True
            elif STRATEGY == "short":   go = FUTURES  # short vereist futures
            elif STRATEGY == "scalp":   go = True
            elif STRATEGY == "swing":   go = True
            elif STRATEGY == "breakout":# simpele breakout: als prijs > 15m high (demo)
                ohlc = ex.fetch_ohlcv(PAIR, timeframe='15m', limit=20)
                high15 = max(h for _,_,h,_,_,_ in ohlc[:-1])
                go = px > high15*0.999 if dir_sign>0 else px < high15*1.001
            elif STRATEGY == "highlev": go = FUTURES and LEVERAGE>=10
            else:                        go = True

            if go and (time.time()-last_trade_ts) > COOLDOWN_S:
                state = place_bracket(PAIR, entry_side, dir_sign, px)
                last_trade_ts = time.time()

                # very light trailing demo loop (een paar ticks)
                for _ in range(30):
                    manage_trailing(PAIR, dir_sign, state)
                    time.sleep(2)

            time.sleep(2)
        except Exception as e:
            print(f"[{now()}] Fout: {e}")
            time.sleep(COOLDOWN_S)

if __name__ == "__main__":
    main()