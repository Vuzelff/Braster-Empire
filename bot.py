# bot.py — Donchian + EMA200 + ATR Trailing (Kraken / ccxt)
import os, time, math
from datetime import datetime
import ccxt

# ---------- helpers ----------
def env(name, default=None, cast=str):
    v = os.getenv(name, default)
    if v is None:
        raise RuntimeError(f"ENV {name} ontbreekt")
    if cast is bool:
        return str(v).lower() in ("1","true","yes","y","on")
    return cast(v)

def now(): return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def ema(vals, n):
    k = 2.0/(n+1.0)
    out, prev = [], None
    for x in vals:
        prev = x if prev is None else (prev + k*(x-prev))
        out.append(prev)
    return out

def atr_from_ohlcv(high, low, close, period=14):
    trs = []
    prev = close[0]
    for h,l,c in zip(high, low, close):
        tr = max(h-l, abs(h-prev), abs(l-prev))
        trs.append(tr)
        prev = c
    return ema(trs, period)

def donchian(hi, lo, n):
    n = int(n)
    return max(hi[-n:]), min(lo[-n:])

# ---------- config ----------
API_KEY       = env("KRAKEN_API_KEY")
API_SECRET    = env("KRAKEN_API_SECRET")
FUTURES       = env("FUTURES", "true", bool)          # true=futures, false=spot
PAIR          = env("PAIR", "ETH/USD")                # bv. ETH/USD (spot) of ETH/USD:USD (futures)
TIMEFRAME     = env("TIMEFRAME", "15m")
EMA_N         = env("EMA_N", "200", int)
DONCHIAN_N    = env("DONCHIAN_N", "55", int)
ATR_N         = env("ATR_N", "14", int)
ATR_MULT      = env("ATR_MULT", "3.0", float)         # trailing afstand in ATR's (3.0 is klassiek)
ORDER_TYPE    = env("ORDER_TYPE", "market")           # market|limit
LIMIT_BPS     = env("LIMIT_BPS", "5", float)          # 5 bps = 0.05% betere prijs bij limit
BASE_SIZE_USD = env("BASE_SIZE_USD", "50", float)     # doel-ordergrootte in USD
MAX_LOSS_USD  = env("MAX_LOSS_USD", "25", float)      # harde cap verlies per trade
COOLDOWN_S    = env("COOLDOWN_S", "60", int)
DRY_RUN       = env("DRY_RUN", "true", bool)

# ---------- exchange ----------
ex = ccxt.krakenfutures({'apiKey':API_KEY,'secret':API_SECRET}) if FUTURES \
   else ccxt.kraken({'apiKey':API_KEY,'secret':API_SECRET,'enableRateLimit':True})
ex.load_markets()

# normaliseer pair voor futures (Kraken Futures gebruikt :USD)
if FUTURES and (":USD" not in PAIR):
    base, quote = PAIR.split("/")
    PAIR = f"{base}/USD:USD"

def fetch_ohlcv(symbol, tf, limit=200):
    ohlc = ex.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
    o,h,l,c,v = zip(*ohlc)
    return list(o), list(h), list(l), list(c), list(v)

def price(symbol):
    return float(ex.fetch_ticker(symbol)['last'])

def usd_to_amount(symbol, usd):
    px = price(symbol)
    amt = max(round(usd / px, 6), 0.000001)
    return amt

def cap_amount_by_risk(symbol, amt, atr_val):
    px = price(symbol)
    # afstand tot initial SL (ATR_MULT * ATR) in prijs-termen
    risk_per_unit = ATR_MULT * atr_val
    # verlies in USD ≈ risk_per_unit * amt (in base) * px/base?
    # risk_per_unit is in "prijs" (USD), dus verlies ≈ amt * risk_per_unit
    # (amt is base; risk_per_unit al in USD => verlies in USD = amt * risk_per_unit)
    if amt * risk_per_unit > MAX_LOSS_USD:
        amt = MAX_LOSS_USD / max(risk_per_unit, 1e-12)
    return round(max(amt, 0.000001), 6)

def place_entry(side, amt, px=None):
    params = {}
    if FUTURES: params['reduceOnly'] = False
    if ORDER_TYPE == "limit":
        if side=="buy":
            limit_px = px * (1 - LIMIT_BPS/10000.0)
        else:
            limit_px = px * (1 + LIMIT_BPS/10000.0)
        order = {"id":"dry"} if DRY_RUN else ex.create_order(PAIR, 'limit', side, amt, round(limit_px, 6), params)
        return order, limit_px
    else:
        order = {"id":"dry"} if DRY_RUN else ex.create_order(PAIR, 'market', side, amt, None, params)
        return order, px

def place_stop(side, amt, stop_px):
    # side hier is TEGENOVERGESTELD van entry om te sluiten
    params = {'reduceOnly': True} if FUTURES else {}
    typ = 'stop'  # krakenfutures: 'stop' met triggerPrice
    args = {**params, 'triggerPrice': round(stop_px, 6)}
    order = {"id":"dry"} if DRY_RUN else ex.create_order(PAIR, typ, side, amt, None, args)
    return order

def replace_stop(old_id, side, amt, new_px):
    if not DRY_RUN:
        try:
            ex.cancel_order(old_id, PAIR)
        except Exception:
            pass
    return place_stop(side, amt, new_px)

def run():
    print(f"=== {now()} • Start • Pair={PAIR} • Futures={FUTURES} • DRY_RUN={DRY_RUN}")
    in_position = False
    pos = {}  # entry_px, side, amt, stop_id, stop_px, best

    while True:
        try:
            # --------- data & indicatoren ----------
            _, H, L, C, _ = fetch_ohlcv(PAIR, TIMEFRAME, limit=max(EMA_N, DONCHIAN_N)+ATR_N+5)
            last = C[-1]
            ema200 = ema(C, EMA_N)[-1]
            atr = atr_from_ohlcv(H, L, C, ATR_N)[-1]
            d_high, d_low = donchian(H, L, DONCHIAN_N)

            want_long = (last > d_high) and (last > ema200)
            want_short = FUTURES and (last < d_low) and (last < ema200)

            # --------- entry ----------
            if not in_position and (want_long or want_short):
                side = "buy" if want_long else "sell"
                opp_side = "sell" if side=="buy" else "buy"

                # basisgrootte + risicocap
                amt = usd_to_amount(PAIR, BASE_SIZE_USD)
                amt = cap_amount_by_risk(PAIR, amt, atr)

                entry_px = price(PAIR)
                entry_order, eff_px = place_entry(side, amt, entry_px)

                # initial SL (Chandelier basis)
                if side == "buy":
                    stop_px = eff_px - ATR_MULT*atr
                    best_px = eff_px
                else:
                    stop_px = eff_px + ATR_MULT*atr
                    best_px = eff_px

                stop = place_stop(opp_side, amt, stop_px)

                pos = dict(entry_px=eff_px, side=side, amt=amt,
                           stop_id=stop["id"], stop_px=stop_px, best=best_px)
                in_position = True
                print(f"[{now()}] ENTRY {side} {amt} {PAIR} @ {round(eff_px,6)}  SL={round(stop_px,6)} (ATR={round(atr,6)})")

            # --------- trailing stop ----------
            if in_position:
                px = price(PAIR)
                side = pos["side"]
                opp  = "sell" if side=="buy" else "buy"

                moved = False
                if side=="buy":
                    if px > pos["best"]:
                        pos["best"] = px
                        moved = True
                    new_sl = pos["best"] - ATR_MULT*atr
                    if new_sl > pos["stop_px"] + 1e-6:
                        pos["stop_id"] = replace_stop(pos["stop_id"], opp, pos["amt"], new_sl)["id"]
                        print(f"[{now()}] TRAIL SL {round(pos['stop_px'],6)} -> {round(new_sl,6)}  (best={round(pos['best'],6)})")
                        pos["stop_px"] = new_sl
                else:
                    if px < pos["best"]:
                        pos["best"] = px
                        moved = True
                    new_sl = pos["best"] + ATR_MULT*atr
                    if new_sl < pos["stop_px"] - 1e-6:
                        pos["stop_id"] = replace_stop(pos["stop_id"], opp, pos["amt"], new_sl)["id"]
                        print(f"[{now()}] TRAIL SL {round(pos['stop_px'],6)} -> {round(new_sl,6)}  (best={round(pos['best'],6)})")
                        pos["stop_px"] = new_sl

                # simpele exit-detectie: als prijs SL raakt, ga uit positie (we poll'en, dus benaderen)
                hit = (side=="buy" and px <= pos["stop_px"]) or (side=="sell" and px >= pos["stop_px"])
                if hit:
                    print(f"[{now()}] EXIT by SL @~{round(pos['stop_px'],6)} (px={round(px,6)})")
                    in_position = False
                    pos = {}

            time.sleep(3)

        except Exception as e:
            print(f"[{now()}] Error: {e}")
            time.sleep(COOLDOWN_S)

if __name__ == "__main__":
    run()