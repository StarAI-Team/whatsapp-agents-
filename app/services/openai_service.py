from openai import OpenAI
import shelve
from dotenv import load_dotenv
import os
import time
import datetime
import logging
import json
from sqlalchemy import create_engine, Column, Integer, String, JSON, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
load_dotenv()

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_KEY = "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"
OPENAI_ASSISTANT_ID = "asst_b92iwdeoXEa1uVNjmWjSIjiI"
client = OpenAI(api_key=OPENAI_API_KEY)

# Database configuration
ENV = 'dev'
if ENV == 'dev':
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@localhost/takura'
else:
    SQLALCHEMY_DATABASE_URI = 'postgres://u1n0nspkcs7s1c:p51be4287c7ae4e0b0f325b0262726d2b475befad2580f18461ff0c7913dba823@cfls9h51f4i86c.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d3vsq6o1lrtt1c'
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://")
# Create SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=True)

# Create session factory
Session = sessionmaker(bind=engine)

# Define Conversation model (this assumes the table structure matches)
class Conversation:
    def __init__(self, thread_id, wa_id, conversation):
        self.thread_id = thread_id
        self.wa_id = wa_id
        self.conversation = conversation

def store_conversation(thread_id, wa_id, message):
    """
    Store a conversation message in the existing conversations table.
    Messages with the same thread_id and wa_id are stored together.
    
    Args:
        thread_id (str): The thread identifier
        wa_id (str): The WhatsApp identifier
        message (dict): The message to store
    """
    session = Session()
    try:
        # Check for existing conversation
        select_stmt = text("""
            SELECT conversation 
            FROM conversation 
            WHERE thread_id = :thread_id AND wa_id = :wa_id
        """)
        
        result = session.execute(
            select_stmt, 
            {"thread_id": thread_id, "wa_id": wa_id}
        ).first()
        
        if result:
            # Update existing conversation
            current_messages = json.loads(result[0]) if result[0] else []
            current_messages.append(message)
            
            update_stmt = text("""
                UPDATE conversation 
                SET conversation = :conversation 
                WHERE thread_id = :thread_id AND wa_id = :wa_id
            """)
            
            session.execute(
                update_stmt,
                {
                    "conversation": json.dumps(current_messages),
                    "thread_id": thread_id,
                    "wa_id": wa_id
                }
            )
        else:
            # Insert new conversation
            insert_stmt = text("""
                INSERT INTO conversation (thread_id, wa_id, conversation)
                VALUES (:thread_id, :wa_id, :conversation)
            """)
            
            session.execute(
                insert_stmt,
                {
                    "thread_id": thread_id,
                    "wa_id": wa_id,
                    "conversation": json.dumps([message])
                }
            )
        
        session.commit()
        return True
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

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
        You are an agent responsible for outsourcing transporters for available loads that need to be transported. Your task is to ask transporters if they are interested in transporting loads, by matching them strictly based on the provided knowledge base or vector space. 

        Do not fetch or infer load details from external sources, including the internet previously cached data, and do not create any load information. Always present current and accurate details based on only the knowledge base. Adhere strictly to the following workflow, guidelines, and examples. Deviating from these instructions is strictly prohibited.

        - **Always strictly start by asking the transporter the following question:**  
          - "Do you have trucks available to transport loads today?"
        - Do not greet with phrases like "Hello" or "How can I assist you?", or "How may I assist you today?"  Skip directly to the inquiry.

        - **Always strictly follow the coversation flow guidlines as they are, do not leave out, or filter out any anything**  

        ---

        ### **Client Interaction Workflow**

        #### 1. **Initial Inquiry**
        - **Always start by asking the transporter the following question:**  
          - "Do you have trucks available to transport loads today?"
        - Do not greet with phrases like "Hello" or "How can I assist you?", or "How may I assist you today?"  Skip directly to the inquiry.

        ---

        #### 2. **Positive Response from Client**
        - If the transporter confirms interest:
          1. Respond warmly:  
             - "Great, We currently have available loads that require transportation."
          2. Check the knowledge base for available loads:
             - If loads are available:  
               - Notify the transporter:  
                 - "Could you share the current location of your truck(s) and the number of trucks you have available?"  
             - If no loads are available:  
               - Direct the transporter to the following fallback contacts:  
                 - Molly Chinyama: +263 77 237 8206, email: mchinyama@starinternational.co.zw  
                 - Accounts Department: Tendai at +263 77 329 9214, email: accounts@starinternational.co.zw  

        ---

        #### 3. **Load Matching**
        - Use the **knowledge base** to match loads based on the transporter's provided location. Follow these steps:
          1. Filter loads to match the transporter's exact location.  
             - Example: If the location is "Mbare," only show loads with "Mbare" in the route.  
          2. If no loads match:  
             - Notify the transporter:  
               - "We currently don't have any loads matching your location. Are you interested in loads from other areas?"  
             - If they are not interested:  
               - Provide fallback contact information:  
                 - Molly Chinyama: +263 77 237 8206, email: mchinyama@starinternational.co.zw  
                 - Accounts Department: Tendai at +263 77 329 9214, email: accounts@starinternational.co.zw  
          3. If loads match:  
             - Provide load details:  
               - "Here are the available loads based on your location:  
                 - Route  
                 - Rate  
                 - Product  
                 - Payment Terms  
                 - Trucks Needed"

        ---

        #### 4. **Booking Confirmation**
        - After the transporter confirms their load preference:
          1. Request driver details:  
             - "Could you provide the driver's name and contact information?"  
          2. Request truck details:  
             - "I'll also need the truck details—make, model, and registration number."  
          3. Request tracking credentials, if applicable:  
             - "Finally, could you provide tracking credentials if possible?"  
        - Do not ask for this information in one message, ask in phases.
        ---

        #### 5. **Contact Information**
        - Collect details for follow-ups:  
          1. WhatsApp number:  
             - "Could I get your preferred call number to stay in touch?"  
          2. Email address:  
             - "What's your email address?"  
        - Do not ask for this information in one message, ask in phases.
        ---

        #### 6. **Verify and Confirm**
        - Verify all booking and load details with the transporter. Example:  
          - "Please confirm the following details for accuracy:  
             - Route  
             - Rate  
             - Product  
             - Payment Terms  
             - Trucks Needed."  
        - Ensure case sensitivity and terminology (e.g., always use "Route" as written in the knowledge base).

        ---

        #### 7. **Closing the Conversation**

          - "Our team will contact you shortly. Thanks a million for your time! Always a pleasure chatting with you. Could you rate this conversation on a scale of 1 to 10?"  

        #### 7. **Closing the Conversation**
        - Express gratitude:  
        - Thank the client for their feedback and ask if they are interested in loads from other areas.:  
          - "Thank you for your feedback! Would you be interested in loads from other areas.?"
          - If interested, next, show them all the loads that you currently have in the provided knowledge base, and let the 
             choose. Continue with the conversation.
        - If they are not interested simply thank the client and encourage future interaction: 
           - Thank you, Looking forward to working with you again. If you need any more assistance, simply say hi Takura, or 
              contact our representatives using the details below. Take care and have a great day!"  
            - Molly Chinyama: +263 77 237 8206, email: mollyc@starinternational.co.zw  
            - Accounts Department: Tendai at +263 77 329 9214, email: accounts@starinternational.co.zw  

        - Do not put this information in one message, ask in phases.
        ---

        ### **General Guidelines**

        1. **Strict Knowledge Base Usage**:  
           - Only use the knowledge base/vector space provided for load details. Do not create, infer, or fetch load details from external sources, including the internet.

        2. **Location-Specific Matching**:  
           - Provide load details that match the exact location provided by the transporter. Do not share loads unrelated to the specified location.

        3. **Fallback Contacts**:  
           - For any inquiries you cannot resolve, direct the client to:  
             - Molly Chinyama: +263 77 237 8206, email: mchinyama@starinternational.co.zw  
             - Accounts Department: Tendai at +263 77 329 9214, email: accounts@starinternational.co.zw  

        4. **Professionalism**:  
           - Always maintain a polite and professional tone.  
           - Respond promptly and ensure clarity in communication.

        5. **Accuracy**:  
           - Verify all information with the client before finalizing bookings.  
           - Adhere strictly to the information in the knowledge base.

        ---

        **Behavioral Requirements**:  
        - **Do not deviate** from these instructions in any way.  
        - Always follow the interaction workflow and guidelines exactly as specified.  
        - Starting with greetings like "Hello" or "How can I assist you?" or "How may I assist you today?" is strictly prohibited. 
        - Try to split the questions so that the don't become overwhelming,  unless there is real need to bundle the questions together.

        **Client services**
        Role Activation:

        -When a transporter begins with "Hi Takura", immediately switch to the role of assisting transporters with their load or transportation issues.

        Greeting and Inquiry:

        -Respond with a friendly tone and ask, "How may I assist you today?". Add a touch of humour to keep the interaction engaging and pleasant.
        -Next, respond to all transporter queries accordingly using the provided knowledge base only.
        Strict Knowledge Base Usage:


        -Do not make up answers or attempt to respond to questions outside the scope of the knowledge base.

        Fallback Procedure:

        -If a query cannot be answered, inform the transporter that you are unable to help with the question.
        Immediately direct them to the host's fallback contact details:
        Molly Chinyama: +263 77 237 8206 | Email: mollyc@starinternational.co.zw
        Accounts Department: Tendai: +263 77 329 9214 | Email: accounts@starinternational.co.zw
        Tone and Personality:

        -Be friendly, approachable, and lightly humorous while maintaining professionalism.
        Consistency:

        -Follow these instructions exactly and do not deviate from the outlined process.
        -Strictly adhere to all of these instructions exactly and do not deviate from the conversation flow.



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
        "user_message": message_body,
        "bot_message": new_message,
        "time": date_string
    }

   

    result = store_conversation(thread_id, wa_id, conversation_pair)
    print(f"Conversation stored successfully: {result}")


    # # Define the file path
    # two_dirs_up = os.path.abspath(os.path.join(os.getcwd(), "data/conversations/"))
    # file_path = os.path.join(two_dirs_up, "conversations.json")

    # # Ensure the directory exists
    # if not os.path.exists(two_dirs_up):
    #     os.makedirs(two_dirs_up)

    # # Initialize the file if it does not exist
    # if not os.path.exists(file_path):
    #     with open(file_path, 'w') as file:
    #         json.dump({}, file)  # Use an empty dictionary
    #         print("File created!")

    # # Read existing data
    # with open(file_path, 'r') as f:
    #     data = json.load(f)

    #     print(f"data: {data}")

    # # Ensure the wa_id exists in the data
    # if wa_id not in data:
    #     data[wa_id] = []
    #     print(f"data1: {data}")

    # # Append the conversation pair
    # data[wa_id].append(conversation_pair)
    # print(f"data2: {data}")

    # # Write updated data back to the file
    # with open(file_path, 'w') as f:
    #     json.dump(data, f, indent=4)

    # print("Conversation added successfully!")

    
    return new_message

# # 2
# from openai import OpenAI
# import shelve
# from dotenv import load_dotenv
# import os
# import time
# import datetime
# import logging
# import json
# from sqlalchemy import create_engine, Column, Integer, String, JSON, text
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# load_dotenv()

# # Global message cache for deduplication
# message_cache = {}

# # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# OPENAI_API_KEY = "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"
# OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
# client = OpenAI(api_key=OPENAI_API_KEY)

# # Database configuration
# ENV = 'prod'
# if ENV == 'dev':
#     SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@localhost/takura'
# else:
#     SQLALCHEMY_DATABASE_URI = 'postgres://u1n0nspkcs7s1c:p51be4287c7ae4e0b0f325b0262726d2b475befad2580f18461ff0c7913dba823@cfls9h51f4i86c.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d3vsq6o1lrtt1c'
#     if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
#         SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://")

# engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=True)
# Session = sessionmaker(bind=engine)

# class Conversation:
#     def __init__(self, thread_id, wa_id, conversation):
#         self.thread_id = thread_id
#         self.wa_id = wa_id
#         self.conversation = conversation

# def is_duplicate_message(wa_id, message_body, window_seconds=30):
#     """Check if a message was recently processed"""
#     current_time = time.time()
#     message_key = f"{wa_id}:{message_body}"
    
#     if message_key in message_cache:
#         last_processed_time = message_cache[message_key]
#         if current_time - last_processed_time < window_seconds:
#             return True
            
#     message_cache[message_key] = current_time
#     return False

# def store_conversation(thread_id, wa_id, message):
#     """Store a conversation message in the existing conversations table."""
#     session = Session()
#     try:
#         # Check for existing conversation
#         select_stmt = text("""
#             SELECT conversation 
#             FROM conversation 
#             WHERE thread_id = :thread_id AND wa_id = :wa_id
#         """)
        
#         result = session.execute(
#             select_stmt, 
#             {"thread_id": thread_id, "wa_id": wa_id}
#         ).first()
        
#         if result:
#             # Update existing conversation
#             current_messages = json.loads(result[0]) if result[0] else []
#             current_messages.append(message)
            
#             update_stmt = text("""
#                 UPDATE conversation 
#                 SET conversation = :conversation 
#                 WHERE thread_id = :thread_id AND wa_id = :wa_id
#             """)
            
#             session.execute(
#                 update_stmt,
#                 {
#                     "conversation": json.dumps(current_messages),
#                     "thread_id": thread_id,
#                     "wa_id": wa_id
#                 }
#             )
#         else:
#             # Insert new conversation
#             insert_stmt = text("""
#                 INSERT INTO conversation (thread_id, wa_id, conversation)
#                 VALUES (:thread_id, :wa_id, :conversation)
#             """)
            
#             session.execute(
#                 insert_stmt,
#                 {
#                     "thread_id": thread_id,
#                     "wa_id": wa_id,
#                     "conversation": json.dumps([message])
#                 }
#             )
        
#         session.commit()
#         return True
        
#     except Exception as e:
#         session.rollback()
#         logging.error(f"Error storing conversation: {str(e)}")
#         raise e
#     finally:
#         session.close()

# def upload_file(path):
#     try:
#         file = client.files.create(
#             file=open("../../data/SIAI Conversation Flow.pdf", "rb"), 
#             purpose="assistants"
#         )
#         return file
#     except Exception as e:
#         logging.error(f"Error uploading file: {str(e)}")
#         raise

# def create_assistant(file):
#     try:
#         assistant = client.beta.assistants.create(
#             name="WhatsApp SIAI Assistant",
#             instructions="""
#             [Your existing instructions here]
#             """,
#             tools=[{"type": "retrieval"}],
#             model="gpt-3.5-turbo",
#             file_ids=[file.id],
#         )
#         logging.info(f"Assistant created: {assistant.id}")
#         return assistant
#     except Exception as e:
#         logging.error(f"Error creating assistant: {str(e)}")
#         raise

# def check_if_thread_exists(wa_id):
#     try:
#         with shelve.open("threads_db") as threads_shelf:
#             return threads_shelf.get(wa_id, None)
#     except Exception as e:
#         logging.error(f"Error checking thread: {str(e)}")
#         return None

# def store_thread(wa_id, thread_id):
#     try:
#         with shelve.open("threads_db", writeback=True) as threads_shelf:
#             threads_shelf[wa_id] = thread_id
#     except Exception as e:
#         logging.error(f"Error storing thread: {str(e)}")
#         raise

# def run_assistant(thread, name, openai_assistant, max_retries=3, timeout=30):
#     start_time = time.time()
    
#     try:
#         assistant = client.beta.assistants.retrieve(openai_assistant)
#         run = client.beta.threads.runs.create(
#             thread_id=thread.id,
#             assistant_id=assistant.id,
#         )
        
#         while run.status != "completed":
#             if time.time() - start_time > timeout:
#                 raise TimeoutError("Assistant run timed out")
                
#             time.sleep(0.5)
#             run = client.beta.threads.runs.retrieve(
#                 thread_id=thread.id, 
#                 run_id=run.id
#             )
            
#             if run.status == "failed":
#                 if max_retries > 0:
#                     logging.warning(f"Assistant run failed, retrying... ({max_retries} retries left)")
#                     return run_assistant(thread, name, openai_assistant, max_retries - 1, timeout)
#                 else:
#                     raise Exception(f"Assistant run failed after all retries: {run.last_error}")

#         messages = client.beta.threads.messages.list(thread_id=thread.id)
#         return messages.data[0].content[0].text.value
        
#     except Exception as e:
#         logging.error(f"Error running assistant: {str(e)}")
#         raise

# def generate_response(message_body, wa_id, name, openai_assistant):
#     # Check for duplicate messages
#     if is_duplicate_message(wa_id, message_body):
#         logging.info(f"Duplicate message detected for {wa_id}: {message_body}")
#         return None
        
#     try:
#         # Check if there is already a thread_id for the wa_id
#         thread_id = check_if_thread_exists(wa_id)

#         # If a thread doesn't exist, create one and store it
#         if thread_id is None:
#             logging.info(f"Creating new thread for {name} with wa_id {wa_id}")
#             thread = client.beta.threads.create()
#             store_thread(wa_id, thread.id)
#             thread_id = thread.id
#         else:
#             logging.info(f"Retrieving existing thread for {name} with wa_id {wa_id}")
#             thread = client.beta.threads.retrieve(thread_id)

#         # Add message to thread
#         message = client.beta.threads.messages.create(
#             thread_id=thread_id,
#             role="user",
#             content=message_body,
#         )
#         logging.info(f"Message created: {message}")

#         # Run the assistant and get the new message
#         new_message = run_assistant(thread, name, openai_assistant)
#         logging.info(f"Generated response for wa_id: {wa_id}")

#         # Store conversation only after successful response
#         conversation_pair = {
#             "user_message": message_body,
#             "bot_message": new_message,
#             "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         }

#         store_conversation(thread_id, wa_id, conversation_pair)
#         return new_message

#     except Exception as e:
#         logging.error(f"Error generating response: {str(e)}")
#         raise

# from openai import OpenAI
# import shelve
# from dotenv import load_dotenv
# import os
# import time
# import datetime
# import logging
# import json
# from sqlalchemy import create_engine, Column, Integer, String, JSON, text
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# load_dotenv()

# # Global message cache for deduplication
# message_cache = {}

# # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# OPENAI_API_KEY = "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"
# OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
# client = OpenAI(api_key=OPENAI_API_KEY)

# # Database configuration
# ENV = 'prod'
# if ENV == 'dev':
#     SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@localhost/takura'
# else:
#     SQLALCHEMY_DATABASE_URI = 'postgres://u1n0nspkcs7s1c:p51be4287c7ae4e0b0f325b0262726d2b475befad2580f18461ff0c7913dba823@cfls9h51f4i86c.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d3vsq6o1lrtt1c'
#     if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
#         SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://")

# engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=True)
# Session = sessionmaker(bind=engine)

# class Conversation:
#     def __init__(self, thread_id, wa_id, conversation):
#         self.thread_id = thread_id
#         self.wa_id = wa_id
#         self.conversation = conversation

# def is_duplicate_message(wa_id, message_body, window_seconds=30):
#     """Check if a message was recently processed"""
#     current_time = time.time()
#     message_key = f"{wa_id}:{message_body}"
    
#     if message_key in message_cache:
#         last_processed_time = message_cache[message_key]
#         if current_time - last_processed_time < window_seconds:
#             return True
            
#     message_cache[message_key] = current_time
#     return False

# def store_conversation(thread_id, wa_id, message):
#     """Store a conversation message in the existing conversations table."""
#     session = Session()
#     try:
#         # Check for existing conversation
#         select_stmt = text("""
#             SELECT conversation 
#             FROM conversation 
#             WHERE thread_id = :thread_id AND wa_id = :wa_id
#         """)
        
#         result = session.execute(
#             select_stmt, 
#             {"thread_id": thread_id, "wa_id": wa_id}
#         ).first()
        
#         if result:
#             # Update existing conversation
#             current_messages = json.loads(result[0]) if result[0] else []
#             current_messages.append(message)
            
#             update_stmt = text("""
#                 UPDATE conversation 
#                 SET conversation = :conversation 
#                 WHERE thread_id = :thread_id AND wa_id = :wa_id
#             """)
            
#             session.execute(
#                 update_stmt,
#                 {
#                     "conversation": json.dumps(current_messages),
#                     "thread_id": thread_id,
#                     "wa_id": wa_id
#                 }
#             )
#         else:
#             # Insert new conversation
#             insert_stmt = text("""
#                 INSERT INTO conversation (thread_id, wa_id, conversation)
#                 VALUES (:thread_id, :wa_id, :conversation)
#             """)
            
#             session.execute(
#                 insert_stmt,
#                 {
#                     "thread_id": thread_id,
#                     "wa_id": wa_id,
#                     "conversation": json.dumps([message])
#                 }
#             )
        
#         session.commit()
#         return True
        
#     except Exception as e:
#         session.rollback()
#         logging.error(f"Error storing conversation: {str(e)}")
#         raise e
#     finally:
#         session.close()

# def upload_file(path):
#     try:
#         file = client.files.create(
#             file=open("../../data/SIAI Conversation Flow.pdf", "rb"), 
#             purpose="assistants"
#         )
#         return file
#     except Exception as e:
#         logging.error(f"Error uploading file: {str(e)}")
#         raise

# def create_assistant(file):
#     try:
#         assistant = client.beta.assistants.create(
#             name="WhatsApp SIAI Assistant",
#             instructions="""
#             [Your existing instructions here]
#             """,
#             tools=[{"type": "retrieval"}],
#             model="gpt-3.5-turbo",
#             file_ids=[file.id],
#         )
#         logging.info(f"Assistant created: {assistant.id}")
#         return assistant
#     except Exception as e:
#         logging.error(f"Error creating assistant: {str(e)}")
#         raise

# def check_if_thread_exists(wa_id):
#     try:
#         with shelve.open("threads_db") as threads_shelf:
#             return threads_shelf.get(wa_id, None)
#     except Exception as e:
#         logging.error(f"Error checking thread: {str(e)}")
#         return None

# def store_thread(wa_id, thread_id):
#     try:
#         with shelve.open("threads_db", writeback=True) as threads_shelf:
#             threads_shelf[wa_id] = thread_id
#     except Exception as e:
#         logging.error(f"Error storing thread: {str(e)}")
#         raise

# def retry_with_exponential_backoff(func, max_retries=3, base_delay=1):
#     """Retry a function with exponential backoff"""
#     retries = 0
#     while retries < max_retries:
#         try:
#             return func()
#         except Exception as e:
#             if "rate_limit_exceeded" not in str(e) or retries == max_retries - 1:
#                 raise
#             delay = base_delay * (2 ** retries)
#             logging.warning(f"Rate limit exceeded, retrying in {delay} seconds... ({max_retries - retries - 1} retries left)")
#             time.sleep(delay)
#             retries += 1
#     raise Exception("Max retries exceeded")

# def run_assistant(thread, name, openai_assistant, max_retries=3, timeout=30):
#     start_time = time.time()
    
#     try:
#         def check_existing_runs():
#             existing_runs = client.beta.threads.runs.list(thread_id=thread.id)
#             for run in existing_runs.data:
#                 if run.status in ['queued', 'in_progress']:
#                     while run.status not in ['completed', 'failed', 'cancelled', 'expired']:
#                         if time.time() - start_time > timeout:
#                             try:
#                                 client.beta.threads.runs.cancel(
#                                     thread_id=thread.id,
#                                     run_id=run.id
#                                 )
#                             except:
#                                 pass
#                             return None
#                         time.sleep(0.5)
#                         run = client.beta.threads.runs.retrieve(
#                             thread_id=thread.id,
#                             run_id=run.id
#                         )
#                     if run.status == 'completed':
#                         messages = client.beta.threads.messages.list(thread_id=thread.id)
#                         return messages.data[0].content[0].text.value
#             return None

#         # Check existing runs with retry
#         result = retry_with_exponential_backoff(
#             check_existing_runs,
#             max_retries=max_retries
#         )
#         if result:
#             return result

#         # Create new run with retry
#         def create_and_monitor_run():
#             assistant = client.beta.assistants.retrieve(openai_assistant)
#             run = client.beta.threads.runs.create(
#                 thread_id=thread.id,
#                 assistant_id=assistant.id,
#             )
            
#             while run.status != "completed":
#                 if time.time() - start_time > timeout:
#                     try:
#                         client.beta.threads.runs.cancel(
#                             thread_id=thread.id,
#                             run_id=run.id
#                         )
#                     except:
#                         pass
#                     raise TimeoutError("Assistant run timed out")
                    
#                 time.sleep(0.5)
#                 run = client.beta.threads.runs.retrieve(
#                     thread_id=thread.id, 
#                     run_id=run.id
#                 )
                
#                 if run.status == "failed":
#                     raise Exception(f"Run failed: {run.last_error}")

#             messages = client.beta.threads.messages.list(thread_id=thread.id)
#             return messages.data[0].content[0].text.value

#         return retry_with_exponential_backoff(
#             create_and_monitor_run,
#             max_retries=max_retries
#         )
        
#     except Exception as e:
#         logging.error(f"Error running assistant: {str(e)}")
#         raise

# def generate_response(message_body, wa_id, name, openai_assistant):
#     if is_duplicate_message(wa_id, message_body):
#         logging.info(f"Duplicate message detected for {wa_id}: {message_body}")
#         return None
        
#     try:
#         thread_id = check_if_thread_exists(wa_id)

#         if thread_id is None:
#             logging.info(f"Creating new thread for {name} with wa_id {wa_id}")
#             thread = client.beta.threads.create()
#             store_thread(wa_id, thread.id)
#             thread_id = thread.id
#         else:
#             logging.info(f"Retrieving existing thread for {name} with wa_id {wa_id}")
#             thread = client.beta.threads.retrieve(thread_id)

#         def create_message():
#             return client.beta.threads.messages.create(
#                 thread_id=thread_id,
#                 role="user",
#                 content=message_body,
#             )

#         # Create message with retry
#         message = retry_with_exponential_backoff(create_message)
#         logging.info(f"Message created: {message}")

#         # Run assistant with retry
#         new_message = run_assistant(thread, name, openai_assistant)
#         logging.info(f"Generated response for wa_id: {wa_id}")

#         conversation_pair = {
#             "user_message": message_body,
#             "bot_message": new_message,
#             "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         }

#         store_conversation(thread_id, wa_id, conversation_pair)
#         return new_message

#     except Exception as e:
#         logging.error(f"Error generating response: {str(e)}")
#         raise