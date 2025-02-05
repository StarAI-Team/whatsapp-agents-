import time
import json
import requests
import pandas as pd
import os
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
import datetime
import openai
import asyncio
import aiohttp
from openai import OpenAI
from openai import Completion
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import tempfile
from pathlib import Path
env = "dev"

class NewFileHandler(FileSystemEventHandler):
    def __init__(self, process_function):
        super().__init__()
        self.process_function = process_function

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".json"):
            self.process_function(event.src_path)

def process_new_file(file_path):
    print(f"Processing new file: {file_path}")
    file_list = []
    
    with open(file_path, 'r', encoding='utf-8-sig') as file:
        json_content = file.read().strip()

        # if not (json_content.startswith('[') and json_content.endswith(']')):
        #     json_content = f'[{json_content}]'

        json_file = json.loads(json_content)
        print(">>-- ",json_file)
        if "loads" in json_file.keys():
            print(f"loads available: {len(json_file['loads'])}")

            

            def create_vector_store_from_json(json_data, store_name="Available Loads"):
                # Initialize OpenAI client
                client = OpenAI()
                
                # Create the vector store
                vector_store = client.beta.vector_stores.create(name=store_name)
                
                # Create a temporary file to store the JSON data
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                    # Write the JSON data to the temporary file
                    json.dump(json_data, tmp_file, indent=2)
                    tmp_file_path = tmp_file.name
                
                try:
                    # Open the temporary file in binary mode for the OpenAI API
                    with open(tmp_file_path, 'rb') as file_stream:
                        # Upload the file to the vector store
                        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
                            vector_store_id=vector_store.id,
                            files=[file_stream]
                        )
                    
                    # Print status and file counts
                    print(f"Batch Status: {file_batch.status}")
                    print(f"File Counts: {file_batch.file_counts}")
                    
                    # Update the assistant with the vector store
                    OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
                    assistant = client.beta.assistants.retrieve(OPENAI_ASSISTANT_ID)
                    assistant = client.beta.assistants.update(
                        assistant_id=assistant.id,
                        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
                    )
                    
                    return vector_store, file_batch, assistant
                    
                finally:
                    # Clean up the temporary file
                    Path(tmp_file_path).unlink()

            try:
                async def send_message(data):
                    headers = {
                        "Content-type": "application/json",
                        "Authorization": f"Bearer {ACCESS_TOKEN}",
                    }

                    async with aiohttp.ClientSession() as session:
                        url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
                        try:
                            async with session.post(url, data=data, headers=headers, verify_ssl=False) as response:
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

                vector_store, file_batch, assistant = create_vector_store_from_json(json_file)
                print("Success - equivalent to 200 OK")

                message_text = "Hi, Good day!"
                RECIPIENT_LIST = [contact["Number"] for contact in json_file["contacts"]]
                ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
                RECIPIENT_WAID = os.getenv("RECIPIENT_WAID")
                PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
                VERSION = os.getenv("VERSION")
                APP_ID = os.getenv("APP_ID")
                APP_SECRET = os.getenv("APP_SECRET")

                print(APP_ID, RECIPIENT_WAID)

                # Create and set a new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                
                # Use the new loop
                try:
                    new_loop.run_until_complete(send_bulk_messages(RECIPIENT_LIST, message_text))
                finally:
                    new_loop.close()

            except openai.APIError as e:
                print(f"Failed: {e}")


def monitor_folder(folder_path):
    event_handler = NewFileHandler(process_new_file)
    observer = PollingObserver()
    observer.schedule(event_handler, folder_path, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    folder_to_watch = "./data/load_details"  # Change this to your target directory
    if not os.path.exists(folder_to_watch):
        print(f"Directory {folder_to_watch} does not exist.")
    else:
        print(f"Starting to monitor {folder_to_watch} for new JSON files...")
        monitor_folder(folder_to_watch)
