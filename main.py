import time
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

# Configure Logging for Cloud Logging (Stackdriver) compatibility
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK - Bot is running")
        else:
            self.send_response(404)
            self.end_headers()

def run_bot():
    logging.info("Bot starting up...")
    # Simulate bot logic loop
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, HealthHandler)
    logging.info("Health check server running on port 8080")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == "__main__":
    run_bot()
