import requests
import time
from datetime import datetime
import logging
import os

class CryptoSignalBot:
    def __init__(self):
        self.token = os.getenv("BOT_TOKEN")
        self.chat_id = os.getenv("CHAT_ID")
        self.session = requests.Session()
        self.coins = [
            "bitcoin", "ethereum", "bnb", "solana",
            "ripple", "dogecoin", "cardano", "avalanche"
        ]

    def get_price_data(self, coin_id):
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'false',
                'developer_data': 'false',
                'sparkline': 'false'
            }

            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            return {
                'name': data['name'],
                'symbol': data['symbol'].upper(),
                'price': data['market_data']['current_price']['usd'],
                'change_24h': data['market_data']['price_change_percentage_24h'],
                'volume_24h': data['market_data']['total_volume']['usd'],
                'market_cap': data['market_data']['market_cap']['usd'],
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            logging.error(f"[{coin_id}] خطا در دریافت داده: {e}")
            return None

    def format_message(self, coin_data_list):
        lines = ["🚀 *وضعیت ۸ ارز اول بازار* (Coingecko)"]
        for coin in coin_data_list:
            if coin:
                lines.append(
                    f"\n🔹 *{coin['name']} ({coin['symbol']})*\n"
                    f"💵 قیمت: `${coin['price']:.2f}`\n"
                    f"📊 تغییر ۲۴ساعته: `{coin['change_24h']:.2f}%`\n"
                    f"📈 مارکت کپ: `${coin['market_cap'] / 1e9:.2f}B`\n"
                    f"🕐 {coin['timestamp']}"
                )
        return "\n".join(lines)

    def send_telegram_message(self, message):
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            res = self.session.post(url, json=payload, timeout=15)
            res.raise_for_status()
            logging.info("پیام با موفقیت ارسال شد.")
        except Exception as e:
            logging.error(f"ارسال پیام به تلگرام شکست خورد: {e}")

    def run(self):
        while True:
            logging.info("دریافت داده جدید...")
            results = [self.get_price_data(c) for c in self.coins]
            message = self.format_message(results)
            self.send_telegram_message(message)
            time.sleep(900)  # 15 دقیقه
