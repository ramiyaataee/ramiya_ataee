import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from bot import CryptoSignalBot  # فرض بر اینه فایل bot.py در همان فولدر است

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running')

def run_health_server(port):
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))

    # اجرای سرور سلامت در یک thread جدا
    thread = threading.Thread(target=run_health_server, args=(port,))
    thread.daemon = True
    thread.start()

    # اجرای ربات
    bot = CryptoSignalBot()
    bot.run()
