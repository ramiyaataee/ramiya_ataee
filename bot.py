import os
import requests
from telegram import Bot

def fetch_crypto_prices():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum,binancecoin,ripple,solana,dogecoin,cardano,toncoin",
        "vs_currencies": "usd",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"خطا در دریافت قیمت‌ها: {e}")
        return {}

def format_message(prices):
    symbols = {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "binancecoin": "BNB",
        "ripple": "XRP",
        "solana": "SOL",
        "dogecoin": "DOGE",
        "cardano": "ADA",
        "toncoin": "TON"
    }
    msg = "💰 قیمت لحظه‌ای رمزارزها:\n\n"
    for coin, symbol in symbols.items():
        price = prices.get(coin, {}).get("usd")
        if price:
            msg += f"{symbol}: ${price:,.2f}\n"
    return msg

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    if not TOKEN or not CHAT_ID:
        print("❌ توکن یا Chat ID تنظیم نشده.")
        return

    bot = Bot(token=TOKEN)
    prices = fetch_crypto_prices()
    if prices:
        message = format_message(prices)
        bot.send_message(chat_id=CHAT_ID, text=message)
        print("✅ پیام ارسال شد.")
    else:
        print("❌ ارسال پیام به دلیل نبود داده انجام نشد.")
