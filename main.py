import requests
import time
import json
import os
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Optional

# تنظیمات لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# تنظیمات کلی پروژه
class Config:
    TELEGRAM_BOT_TOKEN = "8136421090:AAFrb8RI6BQ2tH49YXX_5S32_W0yWfT04Cg"
    TELEGRAM_USER_ID = 570096331
    SYMBOL = "SOLUSDT"
    INTERVAL = "15m"
    DATA_LIMIT = 100
    ENTRY_FILE = "entry_exit.json"
    LOOP_INTERVAL = 900  # 15 دقیقه به ثانیه
    ERROR_RETRY_DELAY = 60  # در صورت خطا 1 دقیقه صبر کن

    EMA_FAST = 9
    EMA_SLOW = 21
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9

# کلاس کار با API بایننس
class BinanceAPI:
    BASE_URL = "https://api.binance.com/api/v3"

    @staticmethod
    def get_klines(symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
        try:
            url = f"{BinanceAPI.BASE_URL}/klines"
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "num_trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            numeric_cols = ["open", "high", "low", "close", "volume"]
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df["timestamp"] = pd.to_datetime(df["open_time"], unit='ms')
            return df
        except Exception as e:
            logger.error(f"خطا در دریافت کندل‌ها: {e}")
            return None

# محاسبه اندیکاتورها
class TechnicalAnalysis:
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int) -> pd.Series:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def calculate_stoch_rsi(df: pd.DataFrame, period: int) -> pd.Series:
        rsi = TechnicalAnalysis.calculate_rsi(df, period)
        stoch_rsi = (rsi - rsi.rolling(period).min()) / (rsi.rolling(period).max() - rsi.rolling(period).min())
        return stoch_rsi

    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df["EMA_fast"] = df["close"].ewm(span=Config.EMA_FAST, adjust=False).mean()
        df["EMA_slow"] = df["close"].ewm(span=Config.EMA_SLOW, adjust=False).mean()
        df["RSI"] = TechnicalAnalysis.calculate_rsi(df, Config.RSI_PERIOD)
        df["StochRSI"] = TechnicalAnalysis.calculate_stoch_rsi(df, Config.RSI_PERIOD)
        ema_fast_macd = df["close"].ewm(span=Config.MACD_FAST, adjust=False).mean()
        ema_slow_macd = df["close"].ewm(span=Config.MACD_SLOW, adjust=False).mean()
        df["MACD"] = ema_fast_macd - ema_slow_macd
        df["MACD_signal"] = df["MACD"].ewm(span=Config.MACD_SIGNAL, adjust=False).mean()
        df["MACD_histogram"] = df["MACD"] - df["MACD_signal"]
        return df

# تولید سیگنال
class SignalGenerator:
    @staticmethod
    def generate_signal(df: pd.DataFrame) -> Dict:
        if len(df) < 2:
            return {"signal": "HOLD", "strength": 0, "conditions": []}

        last = df.iloc[-1]
        prev = df.iloc[-2]

        buy_conditions = []
        sell_conditions = []
        strength = 0

        # EMA cross
        if prev["EMA_fast"] <= prev["EMA_slow"] and last["EMA_fast"] > last["EMA_slow"]:
            buy_conditions.append("EMA Bullish Cross")
            strength += 2
        elif prev["EMA_fast"] >= prev["EMA_slow"] and last["EMA_fast"] < last["EMA_slow"]:
            sell_conditions.append("EMA Bearish Cross")
            strength += 2

        # RSI oversold/overbought
        if last["RSI"] < Config.RSI_OVERSOLD and prev["RSI"] >= Config.RSI_OVERSOLD:
            buy_conditions.append("RSI Oversold")
            strength += 1
        elif last["RSI"] > Config.RSI_OVERBOUGHT and prev["RSI"] <= Config.RSI_OVERBOUGHT:
            sell_conditions.append("RSI Overbought")
            strength += 1

        # MACD cross
        if prev["MACD"] <= prev["MACD_signal"] and last["MACD"] > last["MACD_signal"]:
            buy_conditions.append("MACD Bullish Cross")
            strength += 1.5
        elif prev["MACD"] >= prev["MACD_signal"] and last["MACD"] < last["MACD_signal"]:
            sell_conditions.append("MACD Bearish Cross")
            strength += 1.5

        # سیگنال نهایی
        if len(buy_conditions) >= 2 and strength >= 3:
            return {"signal": "BUY", "strength": strength, "conditions": buy_conditions}
        elif len(sell_conditions) >= 2 and strength >= 3:
            return {"signal": "SELL", "strength": strength, "conditions": sell_conditions}
        else:
            return {"signal": "HOLD", "strength": 0, "conditions": buy_conditions + sell_conditions}

# ارسال پیام به تلگرام
class TelegramNotifier:
    @staticmethod
    def send_message(text: str) -> bool:
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": Config.TELEGRAM_USER_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            response = requests.post(url, data=payload, timeout=10)
            if response.ok:
                logger.info("پیام تلگرام ارسال شد.")
                return True
            else:
                logger.error(f"خطا در ارسال پیام تلگرام: {response.text}")
                return False
        except Exception as e:
            logger.error(f"خطا در ارسال پیام تلگرام: {e}")
            return False

# مدیریت داده ها (بارگذاری و ذخیره)
class DataManager:
    @staticmethod
    def load_json(filename: str) -> dict:
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"خطا در بارگذاری فایل {filename}: {e}")
        return {}

    @staticmethod
    def save_json(data: dict, filename: str) -> bool:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"خطا در ذخیره فایل {filename}: {e}")
            return False

# قالب پیام
def format_signal_message(symbol: str, price: float, signal_data: dict, entry_data: dict) -> str:
    entry_price = entry_data.get("entry_price", 0)
    side = entry_data.get("side", "HOLD")
    pnl = 0
    if entry_price > 0:
        if side == "BUY":
            pnl = (price - entry_price) / entry_price * 100
        elif side == "SELL":
            pnl = (entry_price - price) / entry_price * 100
    signal_emojis = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
    strength_text = "ضعیف"
    if signal_data["strength"] >= 4:
        strength_text = "قوی"
    elif signal_data["strength"] >= 2:
        strength_text = "متوسط"
    conditions_text = "\n".join([f"• {c}" for c in signal_data["conditions"][:3]])
    msg = f"""
🚀 سیگنال {symbol} {signal_emojis.get(signal_data['signal'], '🟡')}

📊 قیمت فعلی: {price:.4f}
📈 سیگنال: {signal_data['signal']}
💪 قدرت سیگنال: {strength_text} ({signal_data['strength']}/5)

💹 شرایط تحلیل:
{conditions_text}

💰 ورود: {entry_price:.4f} ({side})
📉 سود/ضرر فعلی: {pnl:+.2f}%

⚠️ لطفاً همیشه مدیریت ریسک را رعایت کنید.
"""
    return msg.strip()

# ربات اصلی
class CryptoSignalBot:
    def __init__(self):
        self.entry_data = DataManager.load_json(Config.ENTRY_FILE)
        self.last_signal_time = 0

    def run(self):
        logger.info("ربات سیگنال‌دهی کریپتو شروع به کار کرد.")
        TelegramNotifier.send_message(f"✅ ربات {Config.SYMBOL} فعال شد.")

        while True:
            try:
                df = BinanceAPI.get_klines(Config.SYMBOL, Config.INTERVAL, Config.DATA_LIMIT)
                if df is None:
                    logger.warning("داده‌ها دریافت نشد. تلاش مجدد بعد از 1 دقیقه.")
                    time.sleep(Config.ERROR_RETRY_DELAY)
                    continue

                df = TechnicalAnalysis.calculate_indicators(df)
                signal_data = SignalGenerator.generate_signal(df)
                current_price = df["close"].iloc[-1]

                self.process_signal(signal_data, current_price)
                DataManager.save_json(self.entry_data, Config.ENTRY_FILE)

                logger.info(f"منتظر {Config.LOOP_INTERVAL//60} دقیقه برای آپدیت بعدی...")
                time.sleep(Config.LOOP_INTERVAL)

            except KeyboardInterrupt:
                logger.info("ربات توسط کاربر متوقف شد.")
                TelegramNotifier.send_message("🛑 ربات متوقف شد.")
                break
            except Exception as e:
                logger.error(f"خطای غیرمنتظره: {e}")
                time.sleep(Config.ERROR_RETRY_DELAY)

    def process_signal(self, signal_data: dict, current_price: float):
        signal = signal_data["signal"]
        now = time.time()
        should_notify = (self.entry_data.get("side") != signal or (now - self.last_signal_time) > 3600)

        if should_notify and signal != "HOLD":
            self.entry_data = {
                "entry_price": current_price,
                "side": signal,
                "entry_time": datetime.now().isoformat(),
                "signal_strength": signal_data["strength"]
            }
            msg = format_signal_message(Config.SYMBOL, current_price, signal_data, self.entry_data)
            if TelegramNotifier.send_message(msg):
                self.last_signal_time = now
                logger.info(f"سیگنال {signal} ارسال شد: قیمت {current_price}")

def main():
    bot = CryptoSignalBot()
    bot.run()

if __name__ == "__main__":
    main()
