import requests
import time
import json
import os
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Optional
import numpy as np

# --- تنظیمات لاگینگ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- تنظیمات کلی ---
class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "توکن_ربات_تلگرام_تو")  # بهتر است با env ست شود
    TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID", "570096331"))  # شناسه عددی کاربر
    SYMBOL = "SOLUSDT"
    INTERVAL = "15m"
    DATA_LIMIT = 100
    ENTRY_FILE = "entry_exit.json"
    SETTINGS_FILE = "bot_settings.json"
    
    # پارامترهای تحلیل تکنیکال
    EMA_FAST = 9
    EMA_SLOW = 21
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    
    # مدیریت ریسک
    SCALING_STEPS = [0.25, 0.25, 0.25, 0.25]  # ورود مرحله‌ای
    STOP_LOSS_PERCENT = 2.0  # 2% حد ضرر
    TAKE_PROFIT_LEVELS = [1.5, 3.0, 4.5, 6.0]  # درصدهای سود
    MAX_RISK_PER_TRADE = 2.0  # حداکثر ریسک هر معامله
    
    # تنظیمات زمانی
    LOOP_INTERVAL = 900  # ۱۵ دقیقه به ثانیه
    ERROR_RETRY_DELAY = 60  # ۱ دقیقه در صورت خطا

# --- کلاس ارتباط با API بایننس ---
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
            
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df["timestamp"] = pd.to_datetime(df["open_time"], unit='ms')
            return df
        except Exception as e:
            logger.error(f"خطا در دریافت داده‌ها از بایننس: {e}")
            return None

# --- کلاس محاسبه اندیکاتورها ---
class TechnicalAnalysis:
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        try:
            df["EMA_fast"] = df["close"].ewm(span=Config.EMA_FAST, adjust=False).mean()
            df["EMA_slow"] = df["close"].ewm(span=Config.EMA_SLOW, adjust=False).mean()
            
            delta = df["close"].diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(window=Config.RSI_PERIOD).mean()
            avg_loss = loss.rolling(window=Config.RSI_PERIOD).mean()
            rs = avg_gain / avg_loss
            df["RSI"] = 100 - (100 / (1 + rs))
            
            ema12 = df["close"].ewm(span=Config.MACD_FAST, adjust=False).mean()
            ema26 = df["close"].ewm(span=Config.MACD_SLOW, adjust=False).mean()
            df["MACD"] = ema12 - ema26
            df["MACD_signal"] = df["MACD"].ewm(span=Config.MACD_SIGNAL, adjust=False).mean()
            df["MACD_histogram"] = df["MACD"] - df["MACD_signal"]
            
            df["BB_middle"] = df["close"].rolling(window=20).mean()
            bb_std = df["close"].rolling(window=20).std()
            df["BB_upper"] = df["BB_middle"] + 2 * bb_std
            df["BB_lower"] = df["BB_middle"] - 2 * bb_std
            
            df["volume_sma"] = df["volume"].rolling(window=20).mean()
            df["volume_ratio"] = df["volume"] / df["volume_sma"]
            
            return df
        except Exception as e:
            logger.error(f"خطا در محاسبه اندیکاتورها: {e}")
            return df

# --- کلاس تولید سیگنال ---
class SignalGenerator:
    @staticmethod
    def generate_advanced_signal(df: pd.DataFrame) -> Dict:
        try:
            if len(df) < 2:
                return {"signal": "HOLD", "strength": 0, "conditions": []}
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            buy_conditions = []
            sell_conditions = []
            signal_strength = 0
            
            # EMA cross
            if prev["EMA_fast"] <= prev["EMA_slow"] and last["EMA_fast"] > last["EMA_slow"]:
                buy_conditions.append("EMA Bullish Cross")
                signal_strength += 2
            elif prev["EMA_fast"] >= prev["EMA_slow"] and last["EMA_fast"] < last["EMA_slow"]:
                sell_conditions.append("EMA Bearish Cross")
                signal_strength += 2
            
            # RSI
            if last["RSI"] < Config.RSI_OVERSOLD and prev["RSI"] >= Config.RSI_OVERSOLD:
                buy_conditions.append("RSI Oversold Recovery")
                signal_strength += 1
            elif last["RSI"] > Config.RSI_OVERBOUGHT and prev["RSI"] <= Config.RSI_OVERBOUGHT:
                sell_conditions.append("RSI Overbought Reversal")
                signal_strength += 1
            
            # MACD cross
            if prev["MACD"] <= prev["MACD_signal"] and last["MACD"] > last["MACD_signal"]:
                buy_conditions.append("MACD Bullish Cross")
                signal_strength += 1.5
            elif prev["MACD"] >= prev["MACD_signal"] and last["MACD"] < last["MACD_signal"]:
                sell_conditions.append("MACD Bearish Cross")
                signal_strength += 1.5
            
            # Bollinger Bands touch
            if last["close"] < last["BB_lower"] and prev["close"] >= prev["BB_lower"]:
                buy_conditions.append("BB Lower Band Touch")
                signal_strength += 1
            elif last["close"] > last["BB_upper"] and prev["close"] <= prev["BB_upper"]:
                sell_conditions.append("BB Upper Band Touch")
                signal_strength += 1
            
            # Volume confirmation
            if last["volume_ratio"] > 1.5:
                if buy_conditions:
                    buy_conditions.append("High Volume Confirmation")
                    signal_strength += 0.5
                elif sell_conditions:
                    sell_conditions.append("High Volume Confirmation")
                    signal_strength += 0.5
            
            if len(buy_conditions) >= 2 and signal_strength >= 3:
                return {"signal": "BUY", "strength": min(signal_strength, 5), "conditions": buy_conditions}
            elif len(sell_conditions) >= 2 and signal_strength >= 3:
                return {"signal": "SELL", "strength": min(signal_strength, 5), "conditions": sell_conditions}
            else:
                return {"signal": "HOLD", "strength": 0, "conditions": buy_conditions + sell_conditions}
        except Exception as e:
            logger.error(f"خطا در تولید سیگنال: {e}")
            return {"signal": "HOLD", "strength": 0, "conditions": []}

# --- مدیریت ریسک ---
class RiskManager:
    @staticmethod
    def calculate_tp_sl(entry_price: float, side: str) -> Dict:
        if side == "BUY":
            stop_loss = entry_price * (1 - Config.STOP_LOSS_PERCENT / 100)
            take_profits = [entry_price * (1 + tp/100) for tp in Config.TAKE_PROFIT_LEVELS]
        else:  # SELL
            stop_loss = entry_price * (1 + Config.STOP_LOSS_PERCENT / 100)
            take_profits = [entry_price * (1 - tp/100) for tp in Config.TAKE_PROFIT_LEVELS]
        return {"stop_loss": stop_loss, "take_profits": take_profits}

# --- ارسال پیام به تلگرام ---
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
        for attempt in range(3):
            try:
                response = requests.post(url, data=payload, timeout=10)
                if response.ok:
                    logger.info("پیام تلگرام با موفقیت ارسال شد")
                    return True
                else:
                    logger.warning(f"خطا در ارسال پیام تلگرام: {response.text}")
            except Exception as e:
                logger.error(f"خطا در ارسال پیام تلگرام (تلاش {attempt+1}): {e}")
            time.sleep(2)
        return False

# --- مدیریت فایل‌های ذخیره ---
class DataManager:
    @staticmethod
    def load_data(filename: str) -> Dict:
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"خطا در بارگذاری {filename}: {e}")
        return {}
    
    @staticmethod
    def save_data(data: Dict, filename: str) -> bool:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"خطا در ذخیره {filename}: {e}")
            return False

# --- فرمت پیام ---
class MessageFormatter:
    @staticmethod
    def format_signal_message(symbol: str, price: float, signal_data: Dict,
                              entry_data: Dict, risk_data: Dict) -> str:
        entry_price = entry_data.get("entry_price", 0)
        side = entry_data.get("side", "HOLD")
        
        pnl = 0
        if entry_price > 0:
            if side == "BUY":
                pnl = (price - entry_price) / entry_price * 100
            elif side == "SELL":
                pnl = (entry_price - price) / entry_price * 100
        
        signal_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
        strength_text = "ضعیف"
        if signal_data["strength"] >= 4:
            strength_text = "قوی"
        elif signal_data["strength"] >= 2:
            strength_text = "متوسط"
        
        conditions_text = "\n".join([f"   • {cond}" for cond in signal_data["conditions"][:3]])
        scaling_text = " | ".join([f"{int(p*100)}%" for p in Config.SCALING_STEPS])
        tp_text = "\n".join([f"   TP{i+1}: {tp:.4f}" for i, tp in enumerate(risk_data["take_profits"])])
        
        msg = f"""
🚀 <b>سیگنال {symbol}</b> {signal_emoji.get(signal_data['signal'], '🟡')}

📊 <b>وضعیت فعلی:</b>
├ قیمت: <code>{price:.4f}</code>
├ سیگنال: <b>{signal_data['signal']}</b>
├ قدرت: <b>{strength_text}</b> ({signal_data['strength']}/5)
└ زمان: {datetime.now().strftime('%H:%M:%S')}

💹 <b>تحلیل:</b>
{conditions_text}

📈 <b>معامله فعلی:</b>
├ ورود: <code>{entry_price:.4f}</code> ({side})
├ P&L: <b>{pnl:+.2f}%</b>
└ حد ضرر: <code>{risk_data['stop_loss']:.4f}</code>

🎯 <b>اهداف سود:</b>
{tp_text}

⚖️ <b>مدیریت ریسک:</b>
├ ورود مرحله‌ای: {scaling_text}
├ حد ضرر: {Config.STOP_LOSS_PERCENT}%
└ ریسک هر معامله: {Config.MAX_RISK_PER_TRADE}%

⚠️ <i>همیشه مدیریت ریسک را رعایت کنید</i>
        """.strip()
        return msg

# --- ربات اصلی ---
class CryptoSignalBot:
    def __init__(self):
        self.entry_data = DataManager.load_data(Config.ENTRY_FILE)
        self.settings = DataManager.load_data(Config.SETTINGS_FILE)
        self.last_signal_time = 0
    
    def run(self):
        logger.info("🤖 ربات سیگنال‌دهی کریپتو شروع شد")
        start_msg = f"✅ ربات {Config.SYMBOL} فعال شد\n⏰ بازه زمانی: {Config.INTERVAL}\n🔄 به‌روزرسانی هر {Config.LOOP_INTERVAL//60} دقیقه"
        TelegramNotifier.send_message(start_msg)
        
        while True:
            try:
                df = BinanceAPI.get_klines(Config.SYMBOL, Config.INTERVAL, Config.DATA_LIMIT)
                if df is None:
                    logger.warning("داده‌ها دریافت نشد، تلاش مجدد در ۶۰ ثانیه")
                    time.sleep(Config.ERROR_RETRY_DELAY)
                    continue
                
                df = TechnicalAnalysis.calculate_indicators(df)
                signal_data = SignalGenerator.generate_advanced_signal(df)
                current_price = df["close"].iloc[-1]
                
                self.process_signal(signal_data, current_price)
                self.save_state()
                
                logger.info(f"⏳ انتظار {Config.LOOP_INTERVAL//60} دقیقه تا دور بعدی...")
                time.sleep(Config.LOOP_INTERVAL)
            
            except KeyboardInterrupt:
                logger.info("🛑 ربات توسط کاربر متوقف شد")
                TelegramNotifier.send_message("🛑 ربات متوقف شد")
                break
            except Exception as e:
                logger.error(f"خطای غیرمنتظره: {e}")
                time.sleep(Config.ERROR_RETRY_DELAY)
    
    def process_signal(self, signal_data: Dict, current_price: float):
        signal = signal_data["signal"]
        current_time = time.time()
        
        should_notify = (
            self.entry_data.get("side") != signal or
            (current_time - self.last_signal_time) > 3600  # حداقل هر ۱ ساعت آپدیت
        )
        
        if should_notify and signal != "HOLD":
            if signal in ["BUY", "SELL"]:
                self.entry_data = {
                    "entry_price": current_price,
                    "side": signal,
                    "entry_time": datetime.now().isoformat(),
                    "signal_strength": signal_data["strength"]
                }
            
            risk_data = RiskManager.calculate_tp_sl(current_price, signal)
            
            message = MessageFormatter.format_signal_message(
                Config.SYMBOL, current_price, signal_data, self.entry_data, risk_data
            )
            
            if TelegramNotifier.send_message(message):
                self.last_signal_time = current_time
                logger.info(f"📤 سیگنال {signal} ارسال شد - قیمت: {current_price}")
    
    def save_state(self):
        DataManager.save_data(self.entry_data, Config.ENTRY_FILE)
        settings = {
            "last_run": datetime.now().isoformat(),
            "total_signals": self.settings.get("total_signals", 0) + 1
        }
        DataManager.save_data(settings, Config.SETTINGS_FILE)

# --- تابع اصلی ---
def main():
    bot = CryptoSignalBot()
    bot.run()

if __name__ == "__main__":
    main()
