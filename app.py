import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
import os
import secrets
from werkzeug.utils import secure_filename
import pandas as pd
import datetime
import json
import sys
sys.path.append('./app')
from views import webhook_blueprint
import time
import requests
import openai
import asyncio
import aiohttp
from openai import OpenAI
from openai import Completion
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import tempfile
from pathlib import Path

# Initialize Flask extensions
db = SQLAlchemy()

# Create the Flask application
def create_app():
    app = Flask(__name__)
    
    # Configure the application
    ENV = 'dev'
    if ENV == 'dev':
        app.debug = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:admin123@localhost/takura'
    else:
        app.debug = False
        SQLALCHEMY_DATABASE_URI = 'postgres://u1n0nspkcs7s1c:p51be4287c7ae4e0b0f325b0262726d2b475befad2580f18461ff0c7913dba823@cfls9h51f4i86c.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d3vsq6o1lrtt1c'
        if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://")
            app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = secrets.token_hex(16)
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
    app.config['APP_SECRET'] = 'eef4ab23066e34046cacfd3fdeb4c0cd' 


    # Ensure upload folder exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Initialize the application with the extension
    db.init_app(app)


    # Test the database connection
    try:
        with app.app_context():
            db.engine.connect()  # Attempt a simple connection
            logging.info("Database connection successful")
            # Create tables within the application context
            try:
                db.create_all()
                logging.info("Database tables created successfully")
            except Exception as e:
                logging.error(f"Error creating database tables: {e}")
    except Exception as e:
        logging.error(f"Database connection failed: {e}")

    
    # Register blueprints
    app.register_blueprint(webhook_blueprint)
    
    return app



# Database Models
class Load(db.Model):
    __tablename__ = 'load'
    
    id = db.Column(db.Integer, primary_key=True)
    route = db.Column(db.String(200))
    rate = db.Column(db.Float)
    product = db.Column(db.String(200))
    payment_terms = db.Column(db.Text)
    trucks_needed = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=func.now()) 

class Contact(db.Model):
    __tablename__ = 'contact'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    number = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=func.now()) 

# Define Conversation model (this assumes the table structure matches)
class Conversation(db.Model):
    __tablename__ = 'conversation'

    thread_id = db.Column(db.String(200), primary_key=True)
    wa_id = db.Column(db.String(200))
    conversation = db.Column(db.Text)

def load_load_data(data):
    for item in data['loads']:
        load = Load(
            route=item['Route'],
            rate=float(item['Rate'].replace('$', '').replace('Per Load', '')),
            product=item['Product'],
            payment_terms=item['Payment Terms'],
            trucks_needed=item['Trucks Needed']
        )
        db.session.add(load)
    
    db.session.commit()

def load_contact_data(data):
    for item in data['contacts']:
        contact = Contact(name=item['Name'], number=str(item['Number']))
        db.session.add(contact)
    
    db.session.commit()


# Create the application instance
app = create_app()
#web: gunicorn "app:create_app()"
# Routes
@app.route('/', methods=['GET', 'POST'])
def login():
    HARDCODED_USERNAME = 'admin'
    HARDCODED_PASSWORD = 'password123'

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == HARDCODED_USERNAME and password == HARDCODED_PASSWORD:
            session['user_id'] = 1
            flash('Login successful!', 'success')
            return redirect(url_for('upload'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('index.html')

@app.route('/upload', methods=['GET'])
def upload():
    return render_template('uploads.html')

@app.route('/upload_batches', methods=['GET', 'POST'])
def upload_batches():
    if request.method == 'POST':
        if 'loads_file' not in request.files or 'contacts_file' not in request.files:
            flash("Both loads and contacts files are required!", "danger")
            return redirect(url_for('upload_batches'))

        loads_file = request.files['loads_file']
        contacts_file = request.files['contacts_file']

        if loads_file.filename == '' or contacts_file.filename == '':
            flash("Please select files to upload.", "warning")
            return redirect(url_for('upload_batches'))

        try:
            loads_filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(loads_file.filename))
            contacts_filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(contacts_file.filename))
            
            loads_file.save(loads_filepath)
            contacts_file.save(contacts_filepath)

            loads_data = pd.read_excel(loads_filepath)
            contacts_data = pd.read_excel(contacts_filepath)

            combined_data = {
                "loads": loads_data.to_dict(orient='records'),
                "contacts": contacts_data.to_dict(orient='records')
            }

            load_load_data(combined_data)
            load_contact_data(combined_data)

            json_file = combined_data

            if "loads" in json_file.keys():
                print(f"loads available: {len(json_file['loads'])}")

                def create_vector_store_from_json(json_data, store_name="Available Loads"):
                    # Initialize OpenAI client
                    OPENAI_API_KEY = "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"
                    client = OpenAI(api_key=OPENAI_API_KEY)
                    
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
                    # APP_SECRET = os.getenv("APP_SECRET")

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

            # return jsonify(combined_data)
            flash(f"Information uploaded, contacting transporters...", "success")
            return render_template('uploads.html')

        except Exception as e:
            flash(f"Error processing files: {str(e)}", "danger")
            return redirect(url_for('upload_batches'))

    return render_template('uploads.html')

@app.route('/view_records', methods=['GET'])
def view_records():
    # Query the database for records from the Contact table
    records = Contact.query.order_by(Contact.created_at.desc()).all()

    # Convert database records into a format compatible with the HTML template
    formatted_records = [
        {
            "name": record.name,
            "contact_number": record.number,
            "rating": 5,  # Placeholder value, adjust if needed
            "conversation_transcript": record.created_at,  # Placeholder, replace if available
            "summary": "No summary provided",  # Placeholder, replace if needed
            "status": record.id,  # Example status, modify based on your business logic
            "action": "Details"
        }
        for record in records
    ]

    # Render the view_records.html template and pass the formatted records
    return render_template('view_records.html', records=formatted_records)

@app.route('/options')
def option():
    
    return render_template('options.html')

@app.route('/loads')
def loads():
    
    return render_template('loads.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    logging.info("Flask app started")
    app.run()

# if __name__ == "__main__":
#     app = create_app()
#     logging.info("Flask app started")
#     app.run(host="0.0.0.0", port=5000)