from openai import OpenAI
import shelve
from dotenv import load_dotenv
import os
import time
import datetime
import logging
import json

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
client = OpenAI(api_key=OPENAI_API_KEY)


def upload_file(path):
    # Upload a file with an "assistants" purpose
    file = client.files.create(
        file=open("../../data/SIAI Conversation Flow.pdf", "rb"), purpose="assistants"
    )


def create_assistant(file):
    """
    You currently cannot set the temperature for Assistant via the API.
    """
    assistant = client.beta.assistants.create(
        name="WhatsApp SIAI Assistant",
        instructions="""
        You are an agent responsible for outsourcing transporters for available loads that need to be transported. Your task is to ask transporters if they are interested in transporting loads, by matching them with loads strictly based on the provided knowledge base or vector space. Do not use, fetch, or infer load details from the internet or create your own load information.

        Strictly adhere to the following guidelines and do not deviate in any way.

        Client Interaction Workflow:
        Do not start by asking the transporters if you can assist them! For example, don't say "Hello! How can I assist you today," rather start by asking, "Are you looking to move a load (transport a shipment) today?"

        Initial Inquiry: Always and strictly begin by asking the transporter: "Are you looking to move a load (transport a shipment) today?"


        Positive Response from Client: If the transporter confirms interest, respond warmly: "Great to know that you're looking for loads to move!" Proceed to check the knowledge base for available loads. If loads are available, first Notify the transporter that we do have loads available before sharing the load information with them and inquire about their current location  and the number of available trucks before showing the list of loads. . Example: "We have loads available. Could you share your current location and the number of trucks you have available?" 
        If no loads are available: Direct the transporter to the following contacts: Molly Chinyama: +263 77 237 8206, email: mchinyama@starinternational.co.zw Accounts Department: Tendai at +263 77 329 9214, email: accounts@starinternational.co.zw
        Load Matching: Use the knowledge base from file to strictly match loads based on the client's provided location: Strictly follow these guidelines: Filter loads to match the transporter's exact location (e.g., if the location is "Mbare," only show loads with "Mbare" in the route). If no loads match the provided location, notify the client. Example: "We currently don't have any loads matching your location, and Ask if they are interested in loads from other areas, and if they are not interested You may direct the transporter to the following contacts: Molly Chinyama: +263 77 237 8206, email: mchinyama@starinternational.co.zw Accounts Department: Tendai at +263 77 329 9214, email: accounts@starinternational.co.zw.
        Load Details: If the transporter chooses loads, confirm and provide the following details from the knowledge base: Route Rate Product Payment Terms Trucks Needed
        Booking Confirmation: After the transporter confirms their load preference: Request driver details: "Could you provide the driver's name and contact information?" Request truck details: "I'll also need the truck details—make, model, and registration number." Request tracking credentials, if applicable: "Finally, could you provide tracking credentials if possible?"
        Contact Information: Collect contact details for follow-ups: WhatsApp number: "Could I get your preferred call number to stay in touch?" Email address: "What's your email address?"
        Verify and Confirm: Verify all booking and load details with the transporter, showing the details exactly as written in the knowledge base. Example: "Please confirm the following details for accuracy: Route, Rate, Product, Payment Terms, Trucks Needed." Ensure case sensitivity and terminology (e.g., always use "Route" if written as such in the knowledge base).
        Closing the Conversation: Express gratitude: "Our team will contact shortly. Thanks a million for your time! Always a pleasure chatting with you. could you rate this conversation  on a scale of 1 to 10. 
        Thank the client for the feedback and Encourage future interaction: "Thank you for your feedback, Looking forward to working with you again. If you need any more assistance, contact our representatives using the details below. Take care and have a great day!" Molly Chinyama: +263 77 237 8206, email: mchinyama@starinternational.co.zw Accounts Department: Tendai at +263 77 329 9214, email: accounts@starinternational.co.zw
        General Guidelines: Strict Knowledge Base Usage: Only use the knowledge base/vector space provided for load details. Do not create, infer, or fetch load details from external sources, including the internet.

        Location-Specific Matching: Provide load details that match the exact location provided by the transporter. Do not share loads unrelated to the specified location.

        Fallback Contacts: For any inquiries you cannot resolve, direct the client to: Molly Chinyama: +263 77 237 8206, email: mchinyama@starinternational.co.zw Accounts Department: Tendai at +263 77 329 9214, email: accounts@starinternational.co.zw

        Professionalism: Always maintain a polite and professional tone. Respond promptly and ensure clarity in communication. Accuracy: Verify all information with the client before finalizing bookings. Adhere strictly to the information in the knowledge base.

        """,
                tools=[{"type": "retrieval"}],
        model="gpt-3.5-turbo",
        file_ids=[file.id],
    )
    logging.info(f"ASSISTANT>> {assistant}")
    return assistant


# Use context manager to ensure the shelf file is closed properly
def check_if_thread_exists(wa_id):
    with shelve.open("threads_db") as threads_shelf:
        return threads_shelf.get(wa_id, None)


def store_thread(wa_id, thread_id):
    with shelve.open("threads_db", writeback=True) as threads_shelf:
        threads_shelf[wa_id] = thread_id


def run_assistant(thread, name, openai_assistant):
    # Retrieve the Assistant
    assistant = client.beta.assistants.retrieve(openai_assistant)
    logging.info(f"RUN_ASSISTANT: {assistant}")
    logging.info(f"ASSISTANT_ID_AFTER_RUN: {assistant.id}")
    # Run the assistant
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
        # instructions=f"You are having a conversation with {name}",
    )
    logging.info(f"RUN: {run}")

    # Wait for completion
    # https://platform.openai.com/docs/assistants/how-it-works/runs-and-run-steps#:~:text=under%20failed_at.-,Polling%20for%20updates,-In%20order%20to
    while run.status != "completed":
        # Be nice to the API
        time.sleep(0.5)
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        logging.info(f"RUN-2: {run}")

    # Retrieve the Messages
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    new_message = messages.data[0].content[0].text.value
    logging.info(f"Generated message: {new_message}")
    print(f"Generated message: {new_message}")
    return new_message


def generate_response(message_body, wa_id, name, openai_assistant):
    # Check if there is already a thread_id for the wa_id
    thread_id = check_if_thread_exists(wa_id)

    # If a thread doesn't exist, create one and store it
    if thread_id is None:
        logging.info(f"Creating new thread for {name} with wa_id {wa_id}")
        thread = client.beta.threads.create()
        store_thread(wa_id, thread.id)
        thread_id = thread.id

    # Otherwise, retrieve the existing thread
    else:
        logging.info(f"Retrieving existing thread for {name} with wa_id {wa_id}")
        thread = client.beta.threads.retrieve(thread_id)

    logging.info(f"OPENAI_ASSISTANT_ID: {OPENAI_ASSISTANT_ID}")

    # Add message to thread
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=message_body,
    )
    logging.info(f"MESSAGE: {message}")
    print(f">>: {message}")

    # Run the assistant and get the new message
    new_message = run_assistant(thread, name, openai_assistant)
    # logging.info(new_message)
    print(f">>: wa_id: {wa_id} - {new_message}")

    # Get the current timestamp
    now = datetime.datetime.now().isoformat()
    # now = datetime.datetime.now()
            

    # Current date and time
    current_time = datetime.datetime.now()

    # Convert to string
    date_string = current_time.strftime("%Y-%m-%d %H:%M:%S")
    print("Formatted DateTime String:", date_string)
    
    # Create the conversation pair
    conversation_pair = {
        "user": message_body,
        "bot": new_message,
        "time": date_string
    }

    # Define the file path
    two_dirs_up = os.path.abspath(os.path.join(os.getcwd(), "data/conversations/"))
    file_path = os.path.join(two_dirs_up, "conversations.json")

    # Ensure the directory exists
    if not os.path.exists(two_dirs_up):
        os.makedirs(two_dirs_up)

    # Initialize the file if it does not exist
    if not os.path.exists(file_path):
        with open(file_path, 'w') as file:
            json.dump({}, file)  # Use an empty dictionary
            print("File created!")

    # Read existing data
    with open(file_path, 'r') as f:
        data = json.load(f)

        print(f"data: {data}")

    # Ensure the wa_id exists in the data
    if wa_id not in data:
        data[wa_id] = []
        print(f"data1: {data}")

    # Append the conversation pair
    data[wa_id].append(conversation_pair)
    print(f"data2: {data}")

    # Write updated data back to the file
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

    print("Conversation added successfully!")

    
    return new_message
