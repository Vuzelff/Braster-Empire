# 🚀 Braster Empire Futures Trading Bot

Deze bot handelt **automatisch op Kraken Futures** met meerdere pairs en gebruikt indicatoren zoals **EMA, RSI, ADX en ATR**.  
Alle instellingen worden gedaan via **environment variables** (Render) zodat je geen code hoeft te veranderen.

---

## ⚙️ Functies
- ✅ Ondersteuning voor meerdere pairs tegelijk  
- ✅ Futures trading met leverage  
- ✅ Dynamische stop-loss (ATR)  
- ✅ Take profit, trailing stop en cooldowns  
- ✅ Optioneel Telegram notificaties  
- ✅ Volledig te configureren via Render

---

## 📦 Deploy instructies (Render)

1. Fork deze repo naar je eigen GitHub.  
2. Maak een nieuwe **Web Service** aan op [Render](https://dashboard.render.com/).  
3. Kies branch `main`.  
4. Stel in:
   - **Build Command:**
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```bash
     python bot.py
     ```
5. Voeg de **environment variables** toe (zie hieronder).  
6. Deploy en bekijk de logs om te zien of de bot draait.  

---

## 🔑 Environment Variables

| Variable              | Beschrijving |
|------------------------|--------------|
| `KRAKEN_API_KEY`      | Je Kraken Futures API key |
| `KRAKEN_API_SECRET`   | Je Kraken Futures API secret |
| `TELEGRAM_BOT_TOKEN`  | (Optioneel) Telegram bot token voor meldingen |
| `TELEGRAM_CHAT_ID`    | (Optioneel) Telegram chat ID voor meldingen |
| `EXCHANGE`            | Altijd `krakenfutures` |
| `PAIRS`               | De coins die je wilt traden (zie voorbeeld) |
| `TIMEFRAME`           | Candle timeframe, bv `15m` of `1h` |
| `BASE_SIZE_USD`       | Basis ordergrootte in USD |
| `LEVERAGE`            | Leverage, bv `10` |
| `TP_PCT`              | Take Profit percentage, bv `1.0` |
| `SL_PCT`              | Stop Loss percentage, bv `0.5` |
| `TRAIL_PCT`           | Trailing stop percentage, bv `0.3` |
| `TRAIL_AMOUNT_USD`    | Minimale winst in USD voordat trailing ingaat |
| `ATR_MULT_STOP`       | ATR multiplier voor dynamische stop loss |
| `CANDLES_LIMIT`       | Aantal candles op te halen, bv `500` |
| `FAST_EMA`            | Snelle EMA, bv `20` |
| `SLOW_EMA`            | Trage EMA, bv `50` |
| `USE_EMA200_FILTER`   | `True/False`, filter voor lange trend |
| `SLEEP_SECONDS`       | Hoe vaak de bot de markt checkt (bv `60`) |
| `COOLDOWN_S`          | Wachtperiode tussen trades (bv `90`) |
| `MAX_LOSS_USD`        | Max verlies per trade |
| `PROFIT_TRIGGER_USD`  | Minimale winst voordat TP/trailing wordt geactiveerd |
| `DRY_RUN`             | `True` = testen zonder echte orders, `False` = live traden |

---

## 📊 Voorbeeld configuratie (Render)

```env
EXCHANGE=krakenfutures
PAIRS=BTC/USD,XRP/USD,ETH/USD,SOL/USD,LINK/USD,ADA/USD,DOGE/USD,SUI/USD,FIL/USD
TIMEFRAME=15m
BASE_SIZE_USD=25
LEVERAGE=10
TP_PCT=1.0
SL_PCT=0.5
TRAIL_PCT=0.3
TRAIL_AMOUNT_USD=5
ATR_MULT_STOP=2
CANDLES_LIMIT=500
FAST_EMA=20
SLOW_EMA=50
USE_EMA200_FILTER=True
SLEEP_SECONDS=60
COOLDOWN_S=90
MAX_LOSS_USD=50
PROFIT_TRIGGER_USD=10
DRY_RUN=False
