# app/config.py
import os
from dotenv import load_dotenv

# Load .env file from the root directory
load_dotenv()

DB_SERVER   = os.getenv("DB_SERVER")
DB_NAME     = os.getenv("DB_NAME")
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
AUTH_TOKEN  = os.getenv("AUTH_TOKEN")
AUTH_ENDPOINT = os.getenv("AUTH_ENDPOINT")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")

# Construct connection string
DB_CONN_STR = (
    f"DRIVER={{SQL Server}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    f"UID={DB_USER};"
    f"PWD={DB_PASSWORD}"
)
