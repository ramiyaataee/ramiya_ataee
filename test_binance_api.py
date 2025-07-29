import requests

url = "https://api.binance.com/api/v3/klines?symbol=SOLUSDT&interval=15m&limit=100"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    print("Status Code:", response.status_code)
    if response.status_code == 200:
        data = response.json()
        print("تعداد کندل‌ها:", len(data))
    else:
        print("خطا در دریافت داده:", response.text)
except Exception as e:
    print("خطا در اجرای درخواست:", e)
