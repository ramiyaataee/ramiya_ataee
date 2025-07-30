import requests
import time
from datetime import datetime
import logging
import os
import telegram

logging.basicConfig(level=logging.INFO)

class CryptoDataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
        })
        self.coins = [
            'bitcoin',      # BTC
            'ethereum',     # ETH
            'binancecoin',  # BNB
            'solana',       # SOL
            'ripple',       # XRP
            'cardano',      # ADA
            'dogecoin',     # DOGE
            'toncoin',      # TON
        ]

    def get_top_coin_data(self):
        try:
            ids = ','.join(self.coins)
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                'vs_currency': 'usd',
                'ids': ids,
                'order': 'market_cap_desc',
                'per_page': len(self.coins),
                'page': 1,
                'sparkline': 'false',
                'price_change_percentage': '24h'
            }
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            result = []
            for item in data:
                result.append({
                    'symbol': item['symbol'].upper(),
                    'name': item['name'],
                    'price': item['current_price'],
                    'change_24h': item['price_change_percentage_24h_in_currency'],
                    'market_cap': item['market_cap'],
                })
            return result
        except Exception as e:
            logging.error(f"خطا در دریافت داده از CoinGecko: {e}")
            return None

def send_telegram_message(message):
    token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id:
        logging.warning("توکن یا Chat ID مشخص نشده")
        return

    try:
        bot = telegram.Bot(token=token)
        bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
        logging.info("پیام به تلگرام ارسال شد")
    except Exception as e:
        logging.error(f"خطا در ارسال پیام به تلگرام: {e}")

def format_message(data):
    msg = f"<b>🔝 قیمت لحظه‌ای ۸ ارز برتر بازار</b>\n"
    msg += f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    for coin in data:
        msg += f"• <b>{coin['symbol']}</b> - ${coin['price']:.2f} ({coin['change_24h']:+.2f}%)\n"
    return msg

def main_bot_loop():
    fetcher = CryptoDataFetcher()
    while True:
        try:
            data = fetcher.get_top_coin_data()
            if data:
                message = format_message(data)
                send_telegram_message(message)
            else:
                logging.warning("داده‌ای دریافت نشد.")
        except Exception as e:
            logging.error(f"خطا در اجرای بات: {e}")
        time.sleep(900)  # 15 دقیقه
