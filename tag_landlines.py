"""
One-time-use harness: tag Clients.IsValidMobile using Twilio Lookup v2
(Line Type Intelligence). Re-runnable; only processes rows where
IsValidMobile IS NULL.

Run from VS Code's terminal:
    python tag_landlines.py

Required env vars (loaded from .env via app/config.py):
    DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD
    TWILIO_ACCOUNT_SID, AUTH_TOKEN
"""

import logging
import sys
import time

import pyodbc
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from app import config

# Verify current pricing at https://www.twilio.com/lookup
COST_PER_LOOKUP_USD = 0.005

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("tag_landlines")


VALID_MOBILE_TYPES = {"mobile", "fixedvoip", "nonfixedvoip"}


def fetch_pending(cursor):
    cursor.execute(
        """
        SELECT ClientID, PhoneKey10
          FROM dbo.Clients
         WHERE IsValidMobile IS NULL
           AND PhoneKey10 IS NOT NULL
           AND LEN(PhoneKey10) = 10
        """
    )
    return cursor.fetchall()


def classify(twilio, phone_key_10):
    """Return True if Twilio reports 'mobile', False for any other known type,
    or None if the lookup itself fails so the row stays NULL for a retry."""
    e164 = "+1" + phone_key_10
    try:
        result = twilio.lookups.v2.phone_numbers(e164).fetch(
            fields="line_type_intelligence"
        )
    except TwilioRestException as e:
        # 404 = number not in Twilio's dataset; treat as not-a-valid-mobile.
        if e.status == 404:
            return False
        log.warning("Twilio error for %s: %s", e164, e)
        return None
    except Exception as e:
        log.warning("Unexpected error for %s: %s", e164, e)
        return None

    lti = result.line_type_intelligence or {}
    line_type = (lti.get("type") or "").lower()
    return line_type in VALID_MOBILE_TYPES


def main():
    if not config.TWILIO_ACCOUNT_SID or not config.AUTH_TOKEN:
        log.error("TWILIO_ACCOUNT_SID and AUTH_TOKEN must be set in .env")
        sys.exit(1)

    twilio = TwilioClient(config.TWILIO_ACCOUNT_SID, config.AUTH_TOKEN)

    with pyodbc.connect(config.DB_CONN_STR, autocommit=False) as conn:
        cursor = conn.cursor()

        rows = fetch_pending(cursor)
        total = len(rows)
        if total == 0:
            log.info("No clients to classify. Exiting.")
            return

        est_cost = total * COST_PER_LOOKUP_USD
        log.info(
            "Found %d clients to classify (estimated Twilio cost: $%.2f).",
            total,
            est_cost,
        )
        confirm = input("Proceed? [y/N]: ").strip().lower()
        if confirm != "y":
            log.info("Aborted by user.")
            return

        mobile = non_mobile = errors = 0
        start = time.time()

        for i, (client_id, phone_key_10) in enumerate(rows, start=1):
            is_mobile = classify(twilio, phone_key_10)

            if is_mobile is None:
                errors += 1
            else:
                cursor.execute(
                    "UPDATE dbo.Clients SET IsValidMobile = ? WHERE ClientID = ?",
                    (1 if is_mobile else 0, client_id),
                )
                conn.commit()
                if is_mobile:
                    mobile += 1
                else:
                    non_mobile += 1

            if i % 25 == 0 or i == total:
                elapsed = time.time() - start
                rate = i / elapsed if elapsed > 0 else 0
                log.info(
                    "Progress %d/%d  mobile=%d  non-mobile=%d  errors=%d  (%.1f/sec)",
                    i, total, mobile, non_mobile, errors, rate,
                )

        log.info(
            "Done. mobile=%d  non-mobile=%d  errors=%d  total=%d",
            mobile, non_mobile, errors, total,
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Interrupted by user. Partial progress is saved.")
        sys.exit(130)
