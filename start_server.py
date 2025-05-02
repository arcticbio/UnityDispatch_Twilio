import logging
from logging.handlers import RotatingFileHandler
from waitress import serve
from app.sms_service import sms_app  # app.py must define: app = Flask(__name__)
import os
import sys

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "server.log")

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Set up rotating logs: 5 files, each up to 1MB
handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)

# Set up logger
logger = logging.getLogger("waitress_server")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Log to console only if running interactively (e.g., not as Windows Service)
if sys.stdout.isatty():
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

try:
    logger.info("Starting Waitress server on 127.0.0.1:5000...")
    serve(sms_app, host='127.0.0.1', port=5000, _quiet=True)  # _quiet=True suppresses waitress console output
except Exception as e:
    logger.exception("An error occurred while starting the Flask server.")
