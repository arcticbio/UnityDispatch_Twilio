from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
import pyodbc
import logging
from app import config

# Set up logger to use the same 'waitress_server' logger defined in the service script
logger = logging.getLogger("waitress_server")

sms_app = Flask(__name__)

conn_str = config.DB_CONN_STR
auth_token = config.AUTH_TOKEN
auth_endpoint = config.AUTH_ENDPOINT

@sms_app.route("/sms", methods=['POST'])
def sms_reply():

    # Twlio Auth Token stored as an environment variable for security
    validator = RequestValidator(auth_token)

    # Extract the X-Twilio-Signature from the headers
    signature = request.headers.get('X-Twilio-Signature', '')

    # Full URL of this endpoint
    url = auth_endpoint

    # For form-encoded requests, use `request.form` (for JSON, use `request.get_json()`)
    post_vars = request.form.to_dict()

    # Validate the request
    if not validator.validate(url, post_vars, signature):
        logger.warning(f"!!Possible Attack: Twilio signature validation failed for URL={url} from {request.remote_addr}")
        logger.warning(f"Auth={auth_token} ; {post_vars} ; {signature}")
        abort(403)


    # === 1) Parse Twilio webhook parameters ===
    message_sid = request.form.get('MessageSid', '').strip()           # unique ID
    account_sid = request.form.get('AccountSid', '').strip()           # Twilio account
    to_number   = request.form.get('To', '').strip()                   # your Twilio number
    from_number = request.form.get('From', '').strip()                 # sender’s number
    body        = request.form.get('Body', '').strip()                 # SMS body
    num_media   = int(request.form.get('NumMedia', '0'))               # media count
    has_media   = 1 if num_media > 0 else 0                            # bit flag

    exists = False
    last_batch_item_id = None

    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()

            # === 2) Check for messages from this number in the last 16 months ===
            cursor.execute(
                """
                SELECT COUNT(*)
                  FROM InboundSMSMessages
                 WHERE FromPhoneNumber = ?
                   AND SentTime >= DATEADD(month, -16, GETDATE())
                """, (from_number,)
            )
            exists = (cursor.fetchone()[0] or 0) > 0

            # === 3) Retrieve last processed SMS batch item ID for this sender ===
            cursor.execute(
                """
                SELECT TOP 1 SmsBatchItemID
                  FROM SmsBatchItems
                 WHERE '+1' + ToPhoneNumber = ?
                   AND CompletedProcessTime IS NOT NULL
                 ORDER BY CompletedProcessTime DESC
                """, (from_number,)
            )
            row = cursor.fetchone()
            if row:
                last_batch_item_id = row[0]


            # === 4) Insert the inbound message ===
            cursor.execute(
                """
                INSERT INTO InboundSMSMessages
                  (MessageIdentifier,
                   ServiceAccountIdentifier,
                   LastSmsBatchItemID,
                   SentTime,
                   ReceivedTime,
                   ToPhoneNumber,
                   FromPhoneNumber,
                   Message,
                   HasMedia,
                   Completed)
                VALUES (?, ?, ?, SYSDATETIMEOFFSET(), SYSDATETIMEOFFSET(), ?, ?, ?, ?, 0)
                """, (
                    message_sid,
                    account_sid,
                    last_batch_item_id,                    
                    to_number,
                    from_number,
                    body,
                    has_media
                )
            )
            conn.commit()
            logger.info(f"Inserted message {message_sid} from {from_number} (media={has_media}), last batch item {last_batch_item_id}")
            print(f"Inserted message {message_sid} from {from_number} (media={has_media}), last batch item {last_batch_item_id}")

    except Exception as e:
        # Log and print any database errors
        print(f"Database error: {e}")
        logger.error(f"Database error: {e}")

    # === 4) Build reply only if no recent messages from this sender ===
    resp = MessagingResponse()
    if not exists:
        resp.message(
            "Thank you for the message. We will get back to you shortly. "
            "The office number is (907) 248-0800.\n\n"
            "Reply STOP to permanently block all future text messaging "
            "(NOTE: This action may restrict your ability to sign up for future services or "
            "cancel existing services). Msg&Data rates may apply."
        )

    return str(resp)


if __name__ == "__main__":
    sms_app.run(debug=True)
