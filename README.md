
# Braster Empire Bot (Kraken + ccxt)

Eenvoudige, robuuste momentum‑bot met **EMA(50) > EMA(200)** als signaal, 
+ **TP/SL** en **trailing stop** in software. Werkt op **Kraken spot**.

## ENV variabelen
- `KRAKEN_API_KEY` / `KRAKEN_API_SECRET`
- `PAIRS`  (bv. `BTC/USD,ETH/USD`)
- `BASE_SIZE_USD` (bv. 25)
- `TP_PCT` (bv. 1.2)
- `SL_PCT` (bv. 0.6)
- `TRAIL_PCT` (bv. 0.3)
- `COOLDOWN_S` (bv. 60)
- `DRY_RUN` (`true` of `false`)

> Start altijd met `DRY_RUN=true`. Zet naar `false` wanneer je live wil.

## Starten