import logging
from flask import current_app, jsonify
import json

import time
import requests
import datetime
import openai
from openai import OpenAI
from openai import Completion
from pydantic import BaseModel
from typing import List, Optional
from openai.types.beta.threads.message_create_params import (
    Attachment,
    AttachmentToolFileSearch,
)
import asyncio
import sys
sys.path.append('./app/services')
from openai_service import generate_response
# from app.services.openai_service import generate_response
import re
import os
import pdfplumber
# from langchain.text_splitter import CharacterTextSplitter
# from langchain.llms import OpenAI as lang_openai
from dotenv import load_dotenv
load_dotenv()
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_KEY = "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"
OPENAI_ASSISTANT_ID = "asst_b92iwdeoXEa1uVNjmWjSIjiI"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID =os.getenv("PHONE_NUMBER_ID")
VERSION = os.getenv("VERSION") 
# OPENAI_ASSISTANT_ID_1 = os.getenv("OPENAI_ASSISTANT_ID_1")
client = OpenAI(api_key=OPENAI_API_KEY)

class LoadInfo(BaseModel):
    route: str
    from_: str
    to: str
    rate: float
    product_type: str
    trucks_needed: int
    payment_details: str

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

def download_whatsapp_document(media_id, mime_type, access_token):
    url = f"https://graph.facebook.com/v17.0/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"fields": "url"}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    media_url = response.json().get("url")

    # Fetch the document file from the media URL
    document_response = requests.get(media_url, headers=headers, stream=True)
    document_response.raise_for_status()

    file_extension = mime_type.split("/")[-1].split(";")[0]
    base_filename = f"document_{media_id}.{file_extension}"
    temp_filename = base_filename + ".part"
    with open(temp_filename, "wb") as document_file:
        for chunk in document_response.iter_content(chunk_size=1024):
            document_file.write(chunk)

    # Rename the file if successful
    try:
        os.rename(temp_filename, base_filename)
        print(f"Document saved successfully: {base_filename}")
        return base_filename
    except Exception as e:
        print(f"Error saving document: {e}")
        return None




def download_whatsapp_audio(media_id, mime_type, access_token):
    url = f"https://graph.facebook.com/v17.0/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"fields": "url"}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    media_url = response.json().get("url")

    # Fetch the audio file from the media URL
    audio_response = requests.get(media_url, headers=headers, stream=True)
    audio_response.raise_for_status()

    file_extension = mime_type.split("/")[-1].split(";")[0]  # Handle MIME types like "audio/ogg; codecs=opus"
    file_path = f"audio_message.{file_extension}"
    with open(file_path, "wb") as audio_file:
        for chunk in audio_response.iter_content(chunk_size=1024):
            audio_file.write(chunk)

    return file_path


def transcribe_audio_with_openai(file_path):
    client = OpenAI()
    
    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
        model="whisper-1", 
        file=audio_file
        )
        print(transcription.text)
    
    # Extract the transcription text
    return transcription.text

    

    


def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )


# def generate_response(response):
#     # Return text in uppercase
#     return response.upper()


def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }

    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10, verify=False
        )  # 10 seconds timeout as an example
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except (
        requests.RequestException
    ) as e:  # This will catch any general request exception
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        # Process the response as normal
        log_http_response(response)
        return response


def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text

def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {
                "preview_url": True, 
                "body": text}
        }
    )
    # return json.dumps(
    #    {
    #     "messaging_product":"whatsapp",
    #     "to":recipient,
    #     "type":"template",
    #     "template":{
    #         "name":"siai_init_template",
    #         "language":{
    #             "code":"en"
    #         }
    #     }
    #     }
    # )

def process_whatsapp_message(body):
    logging.info(f">>> {body}")
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    logging.info(f">>> {message.keys()}")
    if "text" in message.keys():
        # Normalize the input text by stripping leading/trailing spaces, collapsing multiple spaces, and converting to lowercase
        normalized_message = ' '.join(message["text"]["body"].split()).lower()
 
        # if normalized_message == "hi takura":
        #     print("Recognized as 'hi takura'")
        #     message_body = message["text"]["body"]
        #     response = generate_response(message_body, wa_id, name, OPENAI_ASSISTANT_ID_1)
        #     responses = process_text_for_whatsapp(response)

        #     # receipientNo is to get the number of the sender to used for responds to the sender
        #     receipientNo = "+" + wa_id

        #     data = get_text_message_input(receipientNo, responses)
        #     print(data)
        #     send_message(data)
            # def get_text_message_input_1(recipient, text):
            
            #     return json.dumps(
            #     {
            #         "messaging_product":"whatsapp",
            #         "to":recipient,
            #         "type":"template",
            #         "template":{
            #             "name":"siai_metis_template",
            #             "language":{
            #                 "code":"en"
            #             }
            #         }
            #         }
            #     )
            
            # logging.info(f"MESSAGE_BODY: {message_body}")
            
            # # OpenAI Integration

            # response = generate_response(message_body, wa_id, name)
            # responses = process_text_for_whatsapp(response)

            # # receipientNo is to get the number of the sender to used for responds to the sender
            # receipientNo = "+" + wa_id

            # data = get_text_message_input_1(receipientNo, responses)
            # print(data)
            # send_message(data)
            

        # elif "star international loads" in message["text"]["body"].replace("*","").lower().split('\n'):
        #     message_body = message["text"]["body"]
        #     print(f"*******")
        #     print(message_body)

        #     # TODO: implement custom function here
        #     # response = generate_response(message_body)
        #     message_content = message_body
        #     logging.info(f"MESSAGE_BODY: {message_body}")
          
        #     client = OpenAI()

        #     schema = {
        #         "type": "object",
        #         "properties": {
        #             "route": {"type": "string"},
        #             "from_": {"type": "string"},
        #             "to": {"type": "string"},
        #             "rate": {"type": "number"},
        #             "product_type": {"type": "string"},
        #             "trucks_needed": {"type": "integer"},
        #             "payment_details": {"type": "string"}
        #         },
        #         "required": ["route", "from_", "to", "rate", "product_type"]
        #     }
            
        #     # Use ChatCompletion instead of Parse for more flexibility
        #     completion = client.chat.completions.create(
        #         model="gpt-4o-mini",
        #         messages=[
        #             {
        #                 "role": "system",
        #                 "content": f"Extract structured data from the following WhatsApp message content, and you must also be able to intepret the number of trucks needed for the load, and label that data as trucks_needed. You must also be able to tell the difference between amount of weight and the number of trucks, for example, a 20 ton truck, does not mean 20 trucks, it means 1 truck that can carry a load of weight 20 tonnes. Do not ask for any other details from the client:\n{message_content}"
        #             },
        #             {
        #                 "role": "user",
        #                 "content": message_content
        #             }
        #         ],
        #         temperature=0,
        #         max_tokens=256,
        #         top_p=1
        #     )
            
        #     # Extract the actual data from the ChatCompletionMessage
        #     print(completion)
        #     content = completion.choices[0].message.content
        #     # Parse the JSON string
        #     data = json.loads(content)
        #     print("-----------")
        #     print(data)
        #     # Access the load details
        #     if "load_details" in data.keys():
        #         load_details = data["load_details"]
        #     elif "content" in data.keys():
        #         load_details = data["content"]
        #     else:
        #         load_details = data

        #     # Extract specific fields
        
        #     route = load_details['route']
        #     if "rate_per_ton" in load_details.keys():
        #         rate = load_details['rate_per_ton']
        #     if "rate" in load_details.keys():
        #         rate = load_details['rate']
        #     product = load_details['product']
        #     payment_terms = load_details['payment_terms']
        #     trucks_needed = load_details['trucks_needed']
        #     now = datetime.datetime.now()
            
            

        #     # Current date and time
        #     current_time = datetime.datetime.now()

        #     # Convert to string
        #     date_string = current_time.strftime("%Y-%m-%d %H:%M:%S")
        #     print("Formatted DateTime String:", date_string)

        #     print(f"KEY INFO: {route, rate, product, payment_terms, trucks_needed, date_string}")
        #     #TODO: implement custom function here

        #     def append_to_json(data, filename):
        #         # Navigate two directories up
        #         two_dirs_up = os.path.abspath(os.path.join(os.getcwd(), "data/load_details/"))
        #         file_path = os.path.join(two_dirs_up, filename)

        #         # If file doesn't exist, create it with empty list
        #         if not os.path.exists(file_path):
        #             with open(file_path, 'w') as file:
        #                 json.dump([], file)

        #         # Read the existing data
        #         with open(file_path, 'r') as file:
        #             try:
        #                 existing_data = json.load(file)
        #                 if not isinstance(existing_data, list):
        #                     raise ValueError("File does not contain a list.")
        #             except json.JSONDecodeError:
        #                 existing_data = []  # Initialize as empty list if JSON is invalid

        #         # Append new data to the list
        #         existing_data.append(data)

        #         # Write updated data back to the file
        #         with open(file_path, 'w') as file:
        #             json.dump(existing_data, file, indent=4)

        #         print(f"Data appended to {file_path}")


        #     # Usage example
        #     new_data = {
        #         "wa_id": wa_id,
        #         "route": route,
        #         "rate": rate,
        #         "product": product,
        #         "payment_terms": payment_terms,
        #         "trucks_needed": trucks_needed,
        #         "time": date_string
        #     }

        #     append_to_json(new_data, "data.json")
        #     two_dirs_up = os.path.abspath(os.path.join(os.getcwd(), "data/load_details/"))
        #     file_path = os.path.join(two_dirs_up, "data.json")

        #     # Create a vector store called Availlable Loads
        #     vector_store = client.beta.vector_stores.create(name="Availlable Loads")
            

        #     # Ready the files for upload to OpenAI
        #     file_paths = [file_path]
        #     file_streams = [open(path, "rb") for path in file_paths]

        #     # Use the upload and poll SDK helper to upload the files, add them to the vector store,
        #     # and poll the status of the file batch for completion.
        #     file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        #     vector_store_id=vector_store.id, files=file_streams
        #     )

            # # You can print the status and the file counts of the batch to see the result of this operation.
            # print(file_batch.status)
            # print(file_batch.file_counts)
            # OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
            # assistant = client.beta.assistants.retrieve(OPENAI_ASSISTANT_ID)
            # assistant = client.beta.assistants.update(
            # assistant_id=assistant.id,
            # tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
            # )

            # # OpenAI Integration

            # def get_text_message_input_2(recipient, text):
            
            #     return json.dumps(
            #     {
            #         "messaging_product":"whatsapp",
            #         "to":recipient,
            #         "type":"template",
            #         "template":{
            #             "name":"load_update",
            #             "language":{
            #                 "code":"en"
            #             }
            #         }
            #         }
            #     )
            

            # receipientNo is to get the number of the sender to used for responds to the sender
            # receipientNo = "+" + wa_id

            # # data = get_text_message_input_2(receipientNo, product)
            # # print(data)
            # # send_message(data)


            # response = generate_response(f"These are the new load details:\n{new_data}", wa_id, name)
            # responses = process_text_for_whatsapp(response)

            # # receipientNo is to get the number of the sender to used for responds to the sender
            # receipientNo = "+" + wa_id

            # data = get_text_message_input_2(receipientNo, responses)
            # print(data)
            # send_message(data)

        # elif "load confirmed" in message["text"]["body"].lower().split('\n'):
        #     message_body = message["text"]["body"]
        #     print(f"*******")
        #     print(message_body)

        #     # TODO: implement custom function here
        #     # response = generate_response(message_body)
        #     logging.info(f"MESSAGE_BODY: {message_body}")

        #     # OpenAI Integration

        #     response = generate_response(message_body, wa_id, name)
        #     responses = process_text_for_whatsapp(response)

        #     # receipientNo is to get the number of the sender to used for responds to the sender
        #     receipientNo = "+" + wa_id

        #     data = get_text_message_input(receipientNo, responses)
        #     print(data)
        #     send_message(data)

        #     # Function to extract confirmed load details dynamically
        #     def extract_confirmed_load(conversation):
        #         confirmed_details = None
        #         for i, msg in enumerate(conversation):
        #             if msg["user"].strip().lower() == "load confirmed":
        #                 # Backtrack to find the bot message with load details
        #                 for j in range(i - 1, -1, -1):
        #                     if any(keyword in conversation[j]["bot"] for keyword in ["Route", "Rate", "Truck", "Driver"]):
        #                         confirmed_details = conversation[j]["bot"]
        #                         break
        #                 break
        #         return confirmed_details

        #     # Load JSON data from a file
        #     two_dirs_up = os.path.abspath(os.path.join(os.getcwd(), "data/conversations/"))
        #     file_path = os.path.join(two_dirs_up, "conversations.json")

        #     try:
        #         with open(file_path, "r") as file:
        #             data = json.load(file)  # Load the JSON data into a Python dictionary

        #         # Extract details for the specific conversation
        #         # conversation_key = list(data.keys())[0]  # Assuming there's only one key like "263715775261"
        #         for conversation_key in list(data.keys()):
        #             conversation = data[conversation_key]
        #             print(f"coversation: {conversation}")
        #             confirmed_load_details = extract_confirmed_load(conversation)

        #             # Parse and display the result
        #             if confirmed_load_details:
        #                 print("Confirmed Load Details:")
        #                 print(confirmed_load_details)
        #                 confirmed_load_details = confirmed_load_details.replace("**", "").lower()
        #                 print(confirmed_load_details)
        #                 # load_details = re.findall(r"Load\s*\d+:.*?(?=\n-|\Z)", confirmed_load_details, re.DOTALL)
        #                 # for load in load_details:
        #                 #     print(load.strip())
        #                 print("done!!!")

        #                 # Extract Route and Rate using regex
        #                 route_rate_pattern = r"route:\s*(.+?)\s*rate:\s*(\$\d+)"
        #                 matches = re.findall(route_rate_pattern, confirmed_load_details, re.IGNORECASE)

        #                 # Convert extracted data into a list of dictionaries
        #                 provided_details = [{"route": match[0], "rate": match[1]} for match in matches]
        #                 print(f"Provided details: {provided_details}")


        #                 # File path for the JSON file
        #                 load_data_dir = os.path.abspath(os.path.join(os.getcwd(), "data/load_details/"))
        #                 load_data_file_path = os.path.join(load_data_dir, "data.json")

        #                 try:
        #                     # Load the JSON file
        #                     with open(load_data_file_path, "r") as file:
        #                         data = json.load(file)
        #                         print(f"data details: {data}")
        #                         # Convert all keys and values to lowercase
        #                         data = [
        #                             {key.lower(): (value.lower() if isinstance(value, str) else value) for key, value in record.items()}
        #                             for record in data
        #                         ]
        #                         print(f"lower cased data: {data}")

        #                     # Filter out dictionaries that match the extracted route and rate
        #                     updated_data = [
        #                         entry for entry in data
        #                         if not any(
        #                             detail["route"] == entry["route"] and detail["rate"] == entry["rate"]
        #                             for detail in provided_details
        #                         )
        #                     ]
        #                     updated_data = [
        #                         entry for entry in data
        #                         if not any(
        #                             detail["route"] == entry["route"] and detail["rate"] == f'${entry["rate"]}'
        #                             for detail in provided_details
        #                         )
        #                     ]



        #                     # Save the updated JSON data back to the file
        #                     with open(load_data_file_path, "w") as file:
        #                         json.dump(updated_data, file, indent=4)

        #                     print("The matching dictionaries have been removed.")
        #                 except FileNotFoundError:
        #                     print(f"File not found: {load_data_file_path}")
        #                 except json.JSONDecodeError as e:
        #                     print(f"Failed to decode JSON: {e}")
        #                 # Now update the vector store with updated loads

        #                 client = OpenAI()

        #                 # Create a vector store called Availlable Loads
        #                 vector_store = client.beta.vector_stores.create(name="Availlable Loads")
                        

        #                 # Ready the files for upload to OpenAI
        #                 file_paths = [load_data_file_path]
        #                 file_streams = [open(path, "rb") for path in file_paths]

        #                 # Use the upload and poll SDK helper to upload the files, add them to the vector store,
        #                 # and poll the status of the file batch for completion.
        #                 file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        #                 vector_store_id=vector_store.id, files=file_streams
        #                 )

        #                 # You can print the status and the file counts of the batch to see the result of this operation.
        #                 print(file_batch.status)
        #                 print(file_batch.file_counts)
        #                 OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
        #                 assistant = client.beta.assistants.retrieve(OPENAI_ASSISTANT_ID)
        #                 assistant = client.beta.assistants.update(
        #                 assistant_id=assistant.id,
        #                 tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        #                 )
                    

        #         else:
        #             print("No confirmed load found.")
        #     except FileNotFoundError:
        #         print(f"File not found: {file_path}")
        #     except json.JSONDecodeError as e:
        #         print(f"Failed to decode JSON: {e}")

        # elif "contact transporter" in message["text"]["body"].replace("*", "").lower() or "contact transporters" in message["text"]["body"].replace("*", "").lower():
        #     message_body = message["text"]["body"]
        #     print(f"*******transporter**********")
        #     print(message_body)

        #     # TODO: implement custom function here
        #     # response = generate_response(message_body)
        #     logging.info(f"MESSAGE_BODY: \n{message_body}")
          
        #     client = OpenAI()
            

        #     # Regular expression to match Name and Contact pairs
        #     pattern = r"(?i)name:\s*(.+?)\s*contact:\s*(\+\d+)"

        #     # Extracting all matches
        #     matches = re.findall(pattern, message_body)
        #     print(f"^^^^^^^^^^^^^^^^{matches}^^^^^^^^^^^^^")

        #     # Processing the matches
        #     transporters = [{"Name": name.strip(), "Contact": contact.strip()} for name, contact in matches]
        #     print(f"^^^^^^^^^^^^^^^^{transporters}^^^^^^^^^^^^^")
        #      # Current date and time
        #     current_time = datetime.datetime.now()
        #     # Output
        #     transporter_list = []
        #     for transporter in transporters:
        #         print(f"Name: {transporter['Name']}, Contact: {transporter['Contact']}")
        #         transporter_list.append(transporter['Contact'])
        #         # Convert to string
        #         date_string = current_time.strftime("%Y-%m-%d %H:%M:%S")
        #         print("Formatted DateTime String:", date_string)

               
        #         #TODO: implement custom function here

        #         def append_to_json(data, filename):
        #             # Navigate two directories up
        #             two_dirs_up = os.path.abspath(os.path.join(os.getcwd(), "data/transporter_details/"))
        #             file_path = os.path.join(two_dirs_up, filename)

        #             # If file doesn't exist, create it with empty list
        #             if not os.path.exists(file_path):
        #                 with open(file_path, 'w') as file:
        #                     json.dump([], file)

        #             # Read the existing data
        #             with open(file_path, 'r') as file:
        #                 try:
        #                     existing_data = json.load(file)
        #                     if not isinstance(existing_data, list):
        #                         raise ValueError("File does not contain a list.")
        #                 except json.JSONDecodeError:
        #                     existing_data = []  # Initialize as empty list if JSON is invalid

        #             # Append new data to the list
        #             existing_data.append(data)

        #             # Write updated data back to the file
        #             with open(file_path, 'w') as file:
        #                 json.dump(existing_data, file, indent=4)

        #             print(f"Data appended to {file_path}")


        #         # # Usage example
        #         new_data = {

        #             "created_by": {"wa_id":wa_id, "name": name},
        #             "name": transporter['Name'],
        #             "contact": transporter['Contact'],
        #             "time": date_string
        #             }
                
        #         print("_________-----------_____")
        #         print(new_data)
        #         append_to_json(new_data, "transporters.json")
        #         two_dirs_up = os.path.abspath(os.path.join(os.getcwd(), "data/transporter_details/"))
        #         file_path = os.path.join(two_dirs_up, "transporters.json")

        #     # # Create a vector store called Availlable Loads
        #     # vector_store = client.beta.vector_stores.create(name="Availlable Transporters")
            
        #     two_dirs_up = os.path.abspath(os.path.join(os.getcwd(), "data/transporter_details/"))
        #     file_path = os.path.join(two_dirs_up, "transporters.json")
        #     # Ready the files for upload to OpenAI
        #     file_paths = [file_path]
        #     file_streams = [open(path, "rb") for path in file_paths]

        #     client = OpenAI()

        #     # Create a vector store called Availlable Loads
        #     vector_store = client.beta.vector_stores.create(name="Availlable Transporters")

        #     # Use the upload and poll SDK helper to upload the files, add them to the vector store,
        #     # and poll the status of the file batch for completion.
        #     file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        #     vector_store_id=vector_store.id, files=file_streams
        #     )

        #     # You can print the status and the file counts of the batch to see the result of this operation.
        #     print(file_batch.status)
        #     print(file_batch.file_counts)
        #     OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
        #     assistant = client.beta.assistants.retrieve(OPENAI_ASSISTANT_ID)
        #     assistant = client.beta.assistants.update(
        #     assistant_id=assistant.id,
        #     tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        #     )

        #     # OpenAI Integration

            
        #     response = generate_response(f"contact the following transporter numbers:\n{message_body}", wa_id, name)
        #     responses = process_text_for_whatsapp(response)

        #     # receipientNo is to get the number of the sender to used for responds to the sender
        #     receipientNo = "+" + wa_id

        #     data = get_text_message_input(receipientNo, responses)
        #     print(data)
        #     send_message(data)
            

        #     def get_text_message_input_3(recipient, text):
            
        #         return json.dumps(
        #         {
        #             "messaging_product":"whatsapp",
        #             "to":recipient,
        #             "type":"template",
        #             "template":{
        #                 "name":"siai_metis_template",
        #                 "language":{
        #                     "code":"en"
        #                 }
        #             }
        #             }
        #         )
            

        #     # OpenAI Integration

        #     response = generate_response(response, wa_id, name)
        #     responses = process_text_for_whatsapp(response)

        #     # OpenAI Integration

        #     response = generate_response(message_body, wa_id, name)
        #     responses = process_text_for_whatsapp(response)

        #     # receipientNo is to get the number of the sender to used for responds to the sender
        #     receipientNos = [number if number.startswith("+") else f"+{number}" for number in transporter_list]

        #     # receipientNo is to get the number of the sender to used for responds to the sender
           

        #     # Call the function
        #     if receipientNos:
        #         print(f"CONTACTING -> {receipientNos}")
        #         for receipientNo in receipientNos:
        #             data = get_text_message_input_3(receipientNo, responses)
        #             print(data)
        #             send_message(data)
                

           

                        
        # else:
            #######
        message_body = message["text"]["body"]
        print(f"*******")
        print(message_body)

        # TODO: implement custom function here
        # response = generate_response(message_body)
        logging.info(f"MESSAGE_BODY: {message_body}")

        # OpenAI Integration

        response = generate_response(message_body, wa_id, name, OPENAI_ASSISTANT_ID)
        responses = process_text_for_whatsapp(response)

        # receipientNo is to get the number of the sender to used for responds to the sender
        receipientNo = "+" + wa_id

        data = get_text_message_input(receipientNo, responses)
        print(data)
        send_message(data)


    if "audio" in message.keys():
        logging.info("Processing audio message")
        media_id = message["audio"]["id"]
        mime_type = message["audio"]["mime_type"]
        logging.info(f">>> {media_id}, {mime_type}")

        access_token = current_app.config["ACCESS_TOKEN"]
        file_path = download_whatsapp_audio(media_id, mime_type, access_token)
        logging.info(f"Audio file saved to {file_path}")

        # Step 2: Transcribe the audio message with OpenAI
        transcription = transcribe_audio_with_openai(file_path)
        logging.info(f"Transcription: {transcription}")
        message_body = transcription


        # TODO: implement custom function here
        # response = generate_response(message_body)
        logging.info(f"MESSAGE_BODY: {message_body}")

        # OpenAI Integration

        response = generate_response(message_body, wa_id, name)
        responses = process_text_for_whatsapp(response)

        # receipientNo is to get the number of the sender to used for responds to the sender
        receipientNo = "+" + wa_id

        data = get_text_message_input(receipientNo, responses)
        print(data)
        send_message(data)

    if "type" in message.keys() and message["type"] == "button":
        logging.info("Processing button data")
        print("Processing button data")
        message_body = message["button"]["text"]


        # TODO: implement custom function here
        # response = generate_response(message_body)
        logging.info(f"MESSAGE_BODY: {message_body}")

        # OpenAI Integration

        response = generate_response(message_body, wa_id, name)
        responses = process_text_for_whatsapp(response)

        # receipientNo is to get the number of the sender to used for responds to the sender
        receipientNo = "+" + wa_id

        data = get_text_message_input(receipientNo, responses)
        print(data)
        send_message(data)

    if "type" in message.keys() and message["type"] == "document":
        logging.info("Processing document data")
        print("Processing document data")
        # message_body = message["document"]["filename"]
         # Extract document details
        doc_info = message['document']
        media_id = doc_info['id']
        filename = doc_info['filename']
        mime_type = doc_info['mime_type']
        print(f"Received document: {filename} (MIME type: {mime_type})")


        access_token = current_app.config["ACCESS_TOKEN"]

        document_path = download_whatsapp_document(media_id, mime_type, access_token)
        if document_path:
            prompt = "Extract car registration details from the file provided."

            client = OpenAI()

            pdf_assistant = client.beta.assistants.create(
                model="gpt-4o",
                description="An assistant to extract the contents of PDF files.",
                tools=[{"type": "file_search"}],
                name="PDF assistant",
            )

            # Create thread
            thread = client.beta.threads.create()

            file = client.files.create(file=open(document_path, "rb"), purpose="assistants")

            # Create assistant
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                attachments=[
                    Attachment(
                        file_id=file.id, tools=[AttachmentToolFileSearch(type="file_search")]
                    )
                ],
                content=prompt,
            )

            # Run thread
            run = client.beta.threads.runs.create_and_poll(
                thread_id=thread.id, assistant_id=pdf_assistant.id, timeout=1000
            )

            if run.status != "completed":
                raise Exception("Run failed:", run.status)

            messages_cursor = client.beta.threads.messages.list(thread_id=thread.id)
            messages = [message for message in messages_cursor]

            # Output text
            res_txt = messages[0].content[0].text.value
            print(res_txt)



        # Initialize OpenAI API
        # llm = OpenAI(model="gpt-4", openai_api_key="your-api-key")

        # # Split the document into smaller chunks
        # splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        # chunks = splitter.split_text(document_text)

        # # Process each chunk
        # for chunk in chunks:
        #     response = llm.generate([chunk])
        #     print(response)

        # # TODO: implement custom function here
        # # response = generate_response(message_body)
        message_body = res_txt.copy()
        logging.info(f"MESSAGE_BODY: {message_body}")

        # OpenAI Integration

        response = generate_response(f"These are my details {message_body}", wa_id, name)
        responses = process_text_for_whatsapp(response)

        # receipientNo is to get the number of the sender to used for responds to the sender
        receipientNo = "+" + wa_id

        data = get_text_message_input(receipientNo, responses)
        print(data)
        send_message(data)




    # response = generate_response(message_body, wa_id, name)
    # response = process_text_for_whatsapp(response)
    # logging.info(f"RESPONSE_BODY: {response}")

    # data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response)
    # logging.info(f"RESPONSE: {data}")
    # send_message(data)


def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )
