import requests
import time
from datetime import datetime
import logging

class CryptoDataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
    
    def get_solana_data_coingecko(self):
        """دریافت داده از CoinGecko (رایگان و بدون محدودیت IP)"""
        try:
            url = "https://api.coingecko.com/api/v3/coins/solana"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'false',
                'developer_data': 'false',
                'sparkline': 'false'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            return {
                'symbol': 'SOL',
                'price': data['market_data']['current_price']['usd'],
                'change_24h': data['market_data']['price_change_percentage_24h'],
                'volume_24h': data['market_data']['total_volume']['usd'],
                'market_cap': data['market_data']['market_cap']['usd'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"خطا در CoinGecko API: {e}")
            return None
    
    def get_solana_data_cryptocompare(self):
        """دریافت داده از CryptoCompare"""
        try:
            url = "https://min-api.cryptocompare.com/data/price"
            params = {
                'fsym': 'SOL',
                'tsyms': 'USD',
                'extraParams': 'TradingBot'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # دریافت داده‌های تاریخی برای محاسبه تغییرات
            hist_url = "https://min-api.cryptocompare.com/data/histoday"
            hist_params = {
                'fsym': 'SOL',
                'tsym': 'USD',
                'limit': 1
            }
            
            hist_response = self.session.get(hist_url, params=hist_params, timeout=30)
            hist_data = hist_response.json()
            
            current_price = data['USD']
            yesterday_price = hist_data['Data'][0]['close']
            change_24h = ((current_price - yesterday_price) / yesterday_price) * 100
            
            return {
                'symbol': 'SOL',
                'price': current_price,
                'change_24h': change_24h,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"خطا در CryptoCompare API: {e}")
            return None
    
    def get_solana_data_coinbase(self):
        """دریافت داده از Coinbase Pro API"""
        try:
            # قیمت فعلی
            ticker_url = "https://api.exchange.coinbase.com/products/SOL-USD/ticker"
            response = self.session.get(ticker_url, timeout=30)
            response.raise_for_status()
            ticker_data = response.json()
            
            # آمار 24 ساعته
            stats_url = "https://api.exchange.coinbase.com/products/SOL-USD/stats"
            stats_response = self.session.get(stats_url, timeout=30)
            stats_data = stats_response.json()
            
            current_price = float(ticker_data['price'])
            open_price = float(stats_data['open'])
            change_24h = ((current_price - open_price) / open_price) * 100
            
            return {
                'symbol': 'SOL',
                'price': current_price,
                'change_24h': change_24h,
                'volume_24h': float(stats_data['volume']),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"خطا در Coinbase API: {e}")
            return None
    
    def get_price_data(self):
        """تلاش برای دریافت داده از چندین منبع"""
        sources = [
            ("CoinGecko", self.get_solana_data_coingecko),
            ("CryptoCompare", self.get_solana_data_cryptocompare),
            ("Coinbase", self.get_solana_data_coinbase)
        ]
        
        for source_name, fetch_func in sources:
            try:
                logging.info(f"تلاش برای دریافت داده از {source_name}")
                data = fetch_func()
                if data:
                    logging.info(f"داده با موفقیت از {source_name} دریافت شد")
                    return data
                    
            except Exception as e:
                logging.warning(f"خطا در {source_name}: {e}")
                continue
        
        logging.error("هیچ منبعی داده‌ای ارائه نداد")
        return None

# استفاده در ربات اصلی:
def main_bot_loop():
    fetcher = CryptoDataFetcher()
    
    while True:
        try:
            data = fetcher.get_price_data()
            
            if data:
                # پردازش داده و ارسال سیگنال
                message = f"""
🚀 سولانا (SOL/USD)
💰 قیمت: ${data['price']:.4f}
📈 تغییر 24 ساعته: {data['change_24h']:.2f}%
🕐 زمان: {data['timestamp']}
                """
                
                # ارسال به تلگرام
                send_telegram_message(message)
                logging.info("سیگنال با موفقیت ارسال شد")
                
            else:
                logging.warning("داده‌ای دریافت نشد")
                
        except Exception as e:
            logging.error(f"خطا در حلقه اصلی: {e}")
        
        # انتظار 15 دقیقه
        time.sleep(900)

def send_telegram_message(message):
    """ارسال پیام به تلگرام"""
    # کد ارسال تلگرام شما
    pass

if __name__ == "__main__":
    main_bot_loop()
