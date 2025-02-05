from flask import Flask, app, render_template, request, redirect, url_for, flash, jsonify, session
from app.config import load_configurations, configure_logging
from .views import webhook_blueprint
import os, secrets
from werkzeug.utils import secure_filename
import pandas as pd

def create_app():
    app = Flask(__name__)
    # Dynamically generate a secure secret key
    app.config['SECRET_KEY'] = secrets.token_hex(16)
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

    # Load configurations and logging settings
    load_configurations(app)
    configure_logging()

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])


    @app.route('/', methods=['GET', 'POST'])
    def login():
        # Hardcoded username and password
        HARDCODED_USERNAME = 'admin'
        HARDCODED_PASSWORD = 'password123'

        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            # Validate against hardcoded credentials
            if username == HARDCODED_USERNAME and password == HARDCODED_PASSWORD:
                session['user_id'] = 1  # Assign a dummy user ID for session management
                flash('Login successful!', 'success')
                return redirect(url_for('upload'))  # Redirect to dashboard or main page
            else:
                flash('Invalid username or password', 'danger')

        return render_template('index.html')  # Render the login page


    @app.route('/upload', methods=['GET'])
    def upload():
        return render_template('uploads.html')

    @app.route('/upload_batches', methods=['GET', 'POST'])
    def upload_batches():
        if request.method == 'POST':
            # Check if files are provided
            if 'loads_file' not in request.files or 'contacts_file' not in request.files:
                flash("Both loads and contacts files are required!", "danger")
                return redirect(url_for('upload_batches'))

            loads_file = request.files['loads_file']
            contacts_file = request.files['contacts_file']

            # Check if files are selected
            if loads_file.filename == '' or contacts_file.filename == '':
                flash("Please select files to upload.", "warning")
                return redirect(url_for('upload_batches'))

            # Save the uploaded files temporarily
            loads_filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(loads_file.filename))
            contacts_filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(contacts_file.filename))
            
            loads_file.save(loads_filepath)
            contacts_file.save(contacts_filepath)

            try:
                # Read and process the files (CSV or Excel)
                loads_data = pd.read_excel(loads_filepath)  # Change to pd.read_excel for Excel
                contacts_data = pd.read_excel(contacts_filepath)  # Change to pd.read_excel for Excel

                # Convert data to JSON format
                combined_data = {
                    "loads": loads_data.to_dict(orient='records'),
                    "contacts": contacts_data.to_dict(orient='records')
                }

                # Debug: Print JSON data to the console
                print("Extracted JSON Data:")
                print(combined_data)

                def append_to_json(data, filename):
                    # Navigate two directories up
                    two_dirs_up = os.path.abspath(os.path.join(os.getcwd(), "load_details/"))
                    file_path = os.path.join(two_dirs_up, filename)

                    # If file doesn't exist, create it with empty list
                    if not os.path.exists(file_path):
                        with open(file_path, 'w') as file:
                            json.dump([], file)

                    # Read the existing data
                    with open(file_path, 'r') as file:
                        try:
                            existing_data = json.load(file)
                            if not isinstance(existing_data, list):
                                raise ValueError("File does not contain a list.")
                        except json.JSONDecodeError:
                            existing_data = []  # Initialize as empty list if JSON is invalid

                    # Append new data to the list
                    existing_data.append(data)

                    # Write updated data back to the file
                    with open(file_path, 'w') as file:
                        json.dump(existing_data, file, indent=4)

                    print(f"Data appended to {file_path}")

                    # Current date and time
                current_time = datetime.datetime.now()

                # Convert to string
                date_string = current_time.strftime("%Y-%m-%d %H:%M:%S")
                print("Formatted DateTime String:", date_string)

                combined_data["time"] = date_string

                append_to_json(combined_data, "data.json")
                print(f"APPENDED JSON DATA TO FOLDER")
                print(combined_data)

                # Display JSON on the page for testing
                return jsonify(combined_data)
            #here we can then send the JSN payload to a webhook of our choosing

            except Exception as e:
                flash(f"Error processing files: {str(e)}", "danger")
                return redirect(url_for('upload_batches'))

        # Render the upload form for GET requests
        return render_template('uploads.html')

    # Import and register blueprints, if any
    app.register_blueprint(webhook_blueprint)

    return app
