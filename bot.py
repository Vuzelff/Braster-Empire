import os
import time
import ccxt
import pandas as pd

# === ENVIRONMENT VARIABELEN ===
API_KEY = os.getenv("KRAKEN_API_KEY")
API_SECRET = os.getenv("KRAKEN_API_SECRET")
PAIRS = os.getenv("PAIRS", "BTC/USD,ETH/USD,ADA/USD").split(",")
TIMEFRAME = os.getenv("TIMEFRAME", "15m")
FAST_EMA = int(os.getenv("FAST_EMA", 20))
SLOW_EMA = int(os.getenv("SLOW_EMA", 50))
REQUIRE_EMA200 = os.getenv("REQUIRE_EMA200", "true").lower() == "true"
BASE_SIZE_USD = float(os.getenv("BASE_SIZE_USD", 25))
TP_PCT = float(os.getenv("TP_PCT", 1.5)) / 100
SL_PCT = float(os.getenv("SL_PCT", 0.5)) / 100
TRAIL_PCT = float(os.getenv("TRAIL_PCT", 0.3)) / 100
COOLDOWN_S = int(os.getenv("COOLDOWN_S", 90))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# === KRAKEN API ===
exchange = ccxt.kraken({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "enableRateLimit": True
})

def fetch_ohlcv(pair):
    data = exchange.fetch_ohlcv(pair, TIMEFRAME, limit=200)
    df = pd.DataFrame(data, columns=["ts", "o", "h", "l", "c", "v"])
    df["ema_fast"] = df["c"].ewm(span=FAST_EMA).mean()
    df["ema_slow"] = df["c"].ewm(span=SLOW_EMA).mean()
    df["ema_200"] = df["c"].ewm(span=200).mean()
    return df

def check_signal(df):
    last = df.iloc[-1]
    if last["ema_fast"] > last["ema_slow"]:
        if not REQUIRE_EMA200 or last["c"] > last["ema_200"]:
            return "long"
    elif last["ema_fast"] < last["ema_slow"]:
        if not REQUIRE_EMA200 or last["c"] < last["ema_200"]:
            return "short"
    return None

def place_trade(pair, signal):
    ticker = exchange.fetch_ticker(pair)
    price = ticker["last"]
    amount = BASE_SIZE_USD / price

    if DRY_RUN:
        print(f"[DRY-RUN] {signal.upper()} {amount:.4f} {pair} @ {price}")
        return

    if signal == "long":
        order = exchange.create_market_buy_order(pair, amount)
    else:
        order = exchange.create_market_sell_order(pair, amount)

    entry = price
    tp = entry * (1 + TP_PCT if signal == "long" else 1 - TP_PCT)
    sl = entry * (1 - SL_PCT if signal == "long" else 1 + SL_PCT)

    print(f"TRADE {signal.upper()} {pair}: entry={entry}, tp={tp}, sl={sl} trail={TRAIL_PCT*100}%")
    return order

def run_bot():
    while True:
        for pair in PAIRS:
            try:
                df = fetch_ohlcv(pair)
                signal = check_signal(df)
                if signal:
                    place_trade(pair, signal)
            except Exception as e:
                print(f"Error {pair}: {e}")
        time.sleep(COOLDOWN_S)

if __name__ == "__main__":
    run_bot()
