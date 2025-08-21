# === EMA / ATR / Chandelier helpers ===
def ema(values, period):
    k = 2.0/(period+1.0)
    out, prev = [], None
    for x in values:
        prev = x if prev is None else x*k + prev*(1-k)
        out.append(prev)
    return out

def atr_from_ohlcv(high, low, close, period=14):
    trs = []
    prev_close = close[0]
    for h, l, c in zip(high, low, close):
        tr = max(h-l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
        prev_close = c
    return ema(trs, period)

def chandelier_stop(side, highest, lowest, atr_val, k):
    # side: "buy" (long) of "sell" (short)
    if side == "buy":
        return highest - k*atr_val
    else:
        return lowest + k*atr_val

def fetch_ohlcv(symbol, timeframe="15m", limit=200):
    ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    ts, o, h, l, c, v = zip(*ohlcv)
    return list(o), list(h), list(l), list(c)

def compute_atr(symbol, timeframe="15m", period=14):
    o, h, l, c = fetch_ohlcv(symbol, timeframe=timeframe, limit=max(200, period+10))
    atr_series = atr_from_ohlcv(h, l, c, period=period)
    return c[-1], atr_series[-1]  # last close, last ATR