import os, time, math
from datetime import datetime
import ccxt

# --------- ENV VARS (vul je secrets in via Render/Replit, NIET in code) ----------
API_KEY       = os.getenv("KRAKEN_API_KEY")
API_SECRET    = os.getenv("KRAKEN_API_SECRET")
PAIR          = os.getenv("PAIR", "XRP/USDT")     # bijv: "ETH/USDT", "XRP/USD"
LEVERAGE      = float(os.getenv("LEVERAGE", "3"))# 1..5 voor spot-margin of 1 voor spot
BASE_SIZE_USD = float(os.getenv("BASE_SIZE_USD", "50"))  # inzet per trade in USD
TP_PCT        = float(os.getenv("TP_PCT", "1.0")) # take‑profit +1.0% vanaf entry
SL_PCT        = float(os.getenv("SL_PCT", "0.6")) # stop‑loss   −0.6% vanaf entry
COOLDOWN_S    = int(os.getenv("COOLDOWN_S", "60")) # wachttijd tussen cycli
DRY_RUN       = os.getenv("DRY_RUN", "true").lower() == "true" # geen echte orders

assert API_KEY and API_SECRET, "ENV KRAKEN_API_KEY en KRAKEN_API_SECRET ontbreken"

# --------- EXCHANGE ----------
kraken = ccxt.kraken({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True,
})

def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def market_price(symbol):
    t = kraken.fetch_ticker(symbol)
    return float(t["last"])

def usd_to_amount(symbol, usd):
    px = market_price(symbol)
    # minimale hoeveelheid afronden op 4 decimalen (veilig voor de meeste pairs)
    return max(round(usd/px, 4), 0.0001)

def place_bracket_long(symbol, usd_size, tp_pct, sl_pct):
    entry_px = market_price(symbol)
    amount   = usd_to_amount(symbol, usd_size)

    print(f"[{now()}] ENTRY long {symbol} @ ~{entry_px:.6f} size≈{amount}")
    if DRY_RUN:
        return {"entry": entry_px, "tp": entry_px*(1+tp_pct/100), "sl": entry_px*(1-sl_pct/100), "dry": True}

    # market buy
    o = kraken.create_order(symbol, type="market", side="buy", amount=amount)
    entry_px = float(o["info"].get("price", entry_px))

    tp_px = round(entry_px*(1+tp_pct/100), 6)
    sl_px = round(entry_px*(1-sl_pct/100), 6)

    # plaats OCO (take profit + stop loss). Kraken ondersteunt conditional orders via params
    # Als OCO niet wordt geaccepteerd, vallen we terug naar twee losse orders.
    try:
        kraken.create_order(symbol, "limit", "sell", amount, tp_px, params={"oco": True, "stopPrice": sl_px})
    except Exception:
        # fallback
        kraken.create_order(symbol, "limit", "sell", amount, tp_px)
        kraken.create_order(symbol, "stop-loss", "sell", amount, None, params={"stopPrice": sl_px})

    return {"entry": entry_px, "tp": tp_px, "sl": sl_px, "dry": False}

def main():
    print(f"=== Braster Empire Bot • DRY_RUN={DRY_RUN} • Pair={PAIR} ===")
    last_trade_ts = 0
    while True:
        try:
            px = market_price(PAIR)
            print(f"[{now()}] {PAIR} price: {px}")
            # heel simpele regel: koop wanneer 1m candle boven 50‑MA breekt (placeholder)
            # (om simpel te houden gebruiken we slechts prijs‑momentopname)
            if time.time() - last_trade_ts > COOLDOWN_S:
                r = place_bracket_long(PAIR, BASE_SIZE_USD, TP_PCT, SL_PCT)
                print("Order:", r)
                last_trade_ts = time.time()
        except Exception as e:
            print("Fout:", e)
        time.sleep(COOLDOWN_S)

if __name__ == "__main__":
    main()