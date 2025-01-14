import logging
import json
import os
import requests
import aiohttp
import asyncio

from flask import Blueprint, request, jsonify, current_app

from .decorators.security import signature_required
from .utils.whatsapp_utils import (
    process_whatsapp_message,
    is_valid_whatsapp_message,
)

webhook_blueprint = Blueprint("webhook", __name__)


def handle_message():
    """
    Handle incoming webhook events from the WhatsApp API.

    This function processes incoming WhatsApp messages and other events,
    such as delivery statuses. If the event is a valid message, it gets
    processed. If the incoming payload is not a recognized WhatsApp event,
    an error is returned.

    Every message send will trigger 4 HTTP requests to your webhook: message, sent, delivered, read.

    Returns:
        response: A tuple containing a JSON response and an HTTP status code.
    """
    
    body = request.get_json()
    logging.info(f"request body: {body}")
    print(f"request body: {body}")

    # Check if it's a WhatsApp status update
    if (
        body.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("statuses")
    ):
        logging.info("Received a WhatsApp status update.")
        return jsonify({"status": "ok"}), 200

    try:
        if is_valid_whatsapp_message(body):
            process_whatsapp_message(body)
            return jsonify({"status": "ok"}), 200
        else:
            # if the request is not a WhatsApp API event, return an error
            return (
                jsonify({"status": "error", "message": "Not a WhatsApp API event"}),
                404,
            )
    except json.JSONDecodeError:
        logging.error("Failed to decode JSON")
        return jsonify({"status": "error", "message": "Invalid JSON provided"}), 400


# Required webhook verifictaion for WhatsApp
def verify():
    # Parse params from the webhook verification request
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    logging.info(f"challenge: {challenge}")
    # Check if a token and mode were sent
    if mode and token:
        # Check the mode and token sent are correct
        if mode == "subscribe" and token == current_app.config["VERIFY_TOKEN"]:
            # Respond with 200 OK and challenge token from the request
            logging.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            # Responds with '403 Forbidden' if verify tokens do not match
            logging.info("VERIFICATION_FAILED")
            return jsonify({"status": "error", "message": "Verification failed"}), 403
    else:
        # Responds with '400 Bad Request' if verify tokens do not match
        logging.info("MISSING_PARAMETER")
        return jsonify({"status": "error", "message": "Missing parameters"}), 400


async def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }

    async with aiohttp.ClientSession() as session:
        url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
        try:
            async with session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    print("Message sent successfully.")
                    print("Status:", response.status)
                    print("Response Body:", await response.text())
                else:
                    print(f"Failed to send message. Status: {response.status}")
                    print("Response Body:", await response.text())
        except aiohttp.ClientConnectorError as e:
            print("Connection Error:", str(e))

def get_text_message_input(recipient, text):
    # return json.dumps(
    #     {
    #         "messaging_product": "whatsapp",
            
    #         "recipient_type": "individual",
    #         "to": recipient,
    #         "type": "text",
    #         "text": {
    #             "preview_url": True, 
    #             "body": text}
    #     }
    # )
    return json.dumps(
       {
        "messaging_product":"whatsapp",
        "to":recipient,
        "type":"template",
        "template":{
            "name":"siai_init_template",
            "language":{
                "code":"en"
            }
        }
        }
    )

async def send_bulk_messages(recipients, text):
    tasks = []
    for recipient in recipients:
        logging.info(f"Sending to {recipient}")
        data = get_text_message_input(recipient, text)
        tasks.append(send_message(data))
    await asyncio.gather(*tasks)

message_text = "Hi, Good day!"
# PHONE_NUMBER_ID = "your_phone_number_id"  # Replace with your phone number ID
RECIPIENT_LIST =  ["+263715775261"]#["+263773344079", "+79999171644", "+263772378206"]
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
RECIPIENT_WAID = os.getenv("RECIPIENT_WAID")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERSION = os.getenv("VERSION")
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")

print(APP_ID, RECIPIENT_WAID)

loop = asyncio.get_event_loop()
loop.run_until_complete(send_bulk_messages(RECIPIENT_LIST, message_text))
loop.close()

@webhook_blueprint.route("/webhook", methods=["GET"])
def webhook_get():
    return verify()

@webhook_blueprint.route("/webhook", methods=["POST"])
@signature_required
def webhook_post():
    
    return handle_message()


