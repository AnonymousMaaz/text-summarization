from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
import requests
import os
from dotenv import load_dotenv
import time
import firebase_admin
from firebase_admin import credentials, auth
import base64
import uuid
from pathlib import Path
from flask_cors import CORS
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))  # Use environment variable for secret key

# Enable CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# Add Firebase configuration to app context
app.config.update(
    FIREBASE_API_KEY=os.environ.get('FIREBASE_API_KEY'),
    FIREBASE_AUTH_DOMAIN=os.environ.get('FIREBASE_AUTH_DOMAIN'),
    FIREBASE_PROJECT_ID=os.environ.get('FIREBASE_PROJECT_ID'),
    FIREBASE_STORAGE_BUCKET=os.environ.get('FIREBASE_STORAGE_BUCKET'),
    FIREBASE_MESSAGING_SENDER_ID=os.environ.get('FIREBASE_MESSAGING_SENDER_ID'),
    FIREBASE_APP_ID=os.environ.get('FIREBASE_APP_ID')
)

# Initialize Firebase Admin SDK
service_account_path = '/etc/secrets/serviceAccountKey.json'
if os.path.exists(service_account_path):
    # Use service account from secret file in production
    cred = credentials.Certificate(service_account_path)
else:
    # Fallback to local file for development
    cred = credentials.Certificate('serviceAccountKey.json')

firebase_admin.initialize_app(cred)

# Create profile photos directory if it doesn't exist
PROFILE_PHOTOS_DIR = os.path.join(app.static_folder, 'profile_photos')
os.makedirs(PROFILE_PHOTOS_DIR, exist_ok=True)

# Get API key from environment variable with debug logging
API_KEY = os.getenv("HUGGINGFACE_API_KEY")
print(f"Loaded API key: {API_KEY[:5]}...{API_KEY[-5:] if API_KEY else 'None'}")

if not API_KEY:
    print("Warning: HUGGINGFACE_API_KEY not found in environment variables")
    raise ValueError("HUGGINGFACE_API_KEY environment variable is not set")

API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
headers = {"Authorization": f"Bearer {API_KEY}"}
print(f"Headers: {headers}")

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Fallback summarization function
def fallback_summarize(text, max_length=150, min_length=30):
    """Simple fallback summarization when the API is unavailable"""
    # Split the text into sentences
    sentences = text.split('. ')
    
    # If the text is already short, return it as is
    if len(text.split()) <= max_length:
        return text
    
    # Score sentences based on word frequency
    words = text.lower().split()
    word_freq = {}
    for word in words:
        if word not in word_freq:
            word_freq[word] = 1
        else:
            word_freq[word] += 1
    
    # Score sentences
    sentence_scores = {}
    for sentence in sentences:
        for word in sentence.lower().split():
            if word in word_freq:
                if sentence not in sentence_scores:
                    sentence_scores[sentence] = word_freq[word]
                else:
                    sentence_scores[sentence] += word_freq[word]
    
    # Sort sentences by score
    sorted_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Build summary trying to meet min_length
    summary = ""
    word_count = 0
    
    for sentence, _ in sorted_sentences:
        sentence_words = sentence.split()
        if word_count + len(sentence_words) <= max_length:
            summary += sentence + ". "
            word_count += len(sentence_words)
            if word_count >= min_length:
                break
    
    # If we couldn't meet min_length, add more sentences
    if word_count < min_length:
        for sentence, _ in sorted_sentences:
            if sentence not in summary:
                sentence_words = sentence.split()
                if word_count + len(sentence_words) <= max_length:
                    summary += sentence + ". "
                    word_count += len(sentence_words)
                    if word_count >= min_length:
                        break
    
    # If we still don't have enough words, take the first part of the text
    if word_count < min_length:
        words = text.split()
        summary = " ".join(words[:max_length]) + "..."
    
    return summary.strip()

@app.route('/')
@login_required
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', user=session)

@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/signup')
def signup():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/verify-token', methods=['POST'])
def verify_token():
    try:
        id_token = request.json['idToken']
        decoded_token = auth.verify_id_token(id_token)
        session['user_id'] = decoded_token['uid']
        session['user_email'] = decoded_token.get('email', '')
        session['user_name'] = decoded_token.get('name', '')
        return jsonify({'status': 'success', 'redirect': url_for('index')})
    except Exception as e:
        print(f"Token verification error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 401

@app.route('/Summarize', methods=["GET", "POST"])
@login_required
def Summarize():
    print(f"Summarize route accessed with method: {request.method}")
    
    if request.method == "POST":
        try:
            print("POST request received to /Summarize")
            data = request.form.get("data", "")
            print(f"Input text: {data[:50]}...")
            
            # Get parameters from form or use defaults
            min_length = int(request.form.get("min_length", 30))
            max_length = int(request.form.get("max_length", 130))
            do_sample = request.form.get("do_sample", "false").lower() == "true"
            num_beams = int(request.form.get("num_beams", 4))
            
            print(f"Parameters: min_length={min_length}, max_length={max_length}, do_sample={do_sample}, num_beams={num_beams}")
            
            # Try to use the API with retries
            max_retries = 3
            retry_count = 0
            api_success = False
            
            while retry_count < max_retries and not api_success:
                try:
                    # Prepare the output with dynamic parameters
                    output = {
                        "inputs": data,
                        "parameters": {
                            "min_length": min_length,
                            "max_length": max_length,
                            "do_sample": do_sample,
                            "num_beams": num_beams,
                        }
                    }
                    
                    # Make API request
                    print(f"Attempt {retry_count + 1}: Sending request to Hugging Face API")
                    response = requests.post(API_URL, headers=headers, json=output, timeout=30)
                    print(f"API response status: {response.status_code}")
                    
                    # Check if the request was successful
                    if response.status_code == 200:
                        response_data = response.json()
                        print(f"API response data: {response_data}")
                        result = response_data[0]['summary_text']
                        print(f"Summary generated: {result[:50]}...")
                        api_success = True
                        
                        # Return the template with the result
                        return render_template("index.html", 
                                            result=result, 
                                            original_text=data,
                                            min_length=min_length,
                                            max_length=max_length,
                                            do_sample=do_sample,
                                            num_beams=num_beams,
                                            user=session)
                    else:
                        print(f"API error: {response.status_code} - {response.text}")
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"Retrying in 2 seconds...")
                            time.sleep(2)
                except Exception as e:
                    print(f"Exception during API call: {str(e)}")
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"Retrying in 2 seconds...")
                        time.sleep(2)
            
            # If all API attempts failed, use fallback summarization
            if not api_success:
                print("All API attempts failed. Using fallback summarization.")
                result = fallback_summarize(data, max_length=max_length, min_length=min_length)
                print(f"Fallback summary generated: {result[:50]}...")
                
                # Return the template with the fallback result
                return render_template("index.html", 
                                    result=result, 
                                    original_text=data,
                                    min_length=min_length,
                                    max_length=max_length,
                                    do_sample=do_sample,
                                    num_beams=num_beams,
                                    fallback=True,
                                    user=session)
                
        except Exception as e:
            print(f"Exception in Summarize route: {str(e)}")
            return render_template("index.html", error=f"Error: {str(e)}", user=session)
    
    # Default return for GET request or any other case
    return render_template("index.html", user=session)

@app.route('/api/summarize', methods=['POST'])
@login_required
def summarize():
    try:
        data = request.get_json()
        text = data.get('text', '')
        min_length = int(data.get('min_length', 30))
        max_length = int(data.get('max_length', 130))
        num_beams = int(data.get('num_beams', 4))
        do_sample = data.get('do_sample', False)

        # Print debug information
        print(f"Received POST request to /api/summarize")
        print(f"Input text (first 50 chars): {text[:50]}...")
        print(f"Parameters: min_length={min_length}, max_length={max_length}, num_beams={num_beams}, do_sample={do_sample}")

        # Try to use the API with retries
        max_retries = 3
        retry_count = 0
        api_success = False
        
        while retry_count < max_retries and not api_success:
            try:
                # Prepare the payload
                payload = {
                    "inputs": text,
                    "parameters": {
                        "min_length": min_length,
                        "max_length": max_length,
                        "num_beams": num_beams,
                        "do_sample": do_sample
                    }
                }

                # Make the API request
                print(f"Attempt {retry_count + 1}: Sending request to Hugging Face API")
                response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
                print(f"API Response Status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    summary = result[0]['summary_text']
                    print(f"Generated summary (first 50 chars): {summary[:50]}...")
                    api_success = True
                    return jsonify({
                        "success": True,
                        "summary": summary
                    })
                else:
                    print(f"API Error: {response.text}")
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"Retrying in 2 seconds...")
                        time.sleep(2)
            except Exception as e:
                print(f"Exception during API call: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"Retrying in 2 seconds...")
                    time.sleep(2)
        
        # If all API attempts failed, use fallback summarization
        if not api_success:
            print("All API attempts failed. Using fallback summarization.")
            summary = fallback_summarize(text, max_length)
            return jsonify({
                "success": True,
                "summary": summary,
                "fallback": True,
                "warning": "Hugging Face API is currently unavailable. Using basic summarization instead."
            })

    except Exception as e:
        print(f"Error in summarize: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

def basic_summarization(text, min_length, max_length):
    # Split text into sentences
    sentences = text.split('. ')
    
    # Simple scoring based on word frequency
    words = text.lower().split()
    word_freq = {}
    for word in words:
        if word not in word_freq:
            word_freq[word] = 1
        else:
            word_freq[word] += 1
    
    # Score sentences
    sentence_scores = {}
    for sentence in sentences:
        for word in sentence.lower().split():
            if word in word_freq:
                if sentence not in sentence_scores:
                    sentence_scores[sentence] = word_freq[word]
                else:
                    sentence_scores[sentence] += word_freq[word]
    
    # Get top sentences
    summary_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)
    summary = '. '.join([s[0] for s in summary_sentences[:3]])
    
    return summary

@app.route("/test", methods=["GET"])
def test():
    """Direct test route to verify the API is working correctly"""
    print("Test route accessed")
    try:
        # Test text
        test_text = "The quick brown fox jumps over the lazy dog. This is a test sentence to verify that the API is working correctly."
        
        # Prepare the output
        output = {
            "inputs": test_text,
            "parameters": {
                "min_length": 10,
                "max_length": 30,
                "do_sample": False,
                "num_beams": 4,
            }
        }
        
        print("Sending request to Hugging Face API")
        print(f"Request payload: {output}")
        print(f"Request headers: {headers}")
        print(f"API URL: {API_URL}")
        
        response = requests.post(API_URL, headers=headers, json=output)
        print(f"API response status: {response.status_code}")
        print(f"API response headers: {dict(response.headers)}")
        print(f"API response body: {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"API response data: {response_data}")
            summary = response_data[0]['summary_text']
            print(f"Summary generated: {summary[:50]}...")
            
            # Return the summary directly
            return f"""
            <html>
            <head>
                <title>API Test</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    pre {{ background: #f5f5f5; padding: 10px; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <h1>API Test Result</h1>
                <h2>Input Text:</h2>
                <pre>{test_text}</pre>
                <h2>Summary:</h2>
                <pre>{summary}</pre>
                <h2>Response Data:</h2>
                <pre>{response_data}</pre>
                <p><a href="/">Back to Home</a></p>
            </body>
            </html>
            """
        else:
            error_msg = f"API Error: {response.status_code} - {response.text}"
            print(f"Error: {error_msg}")
            return f"""
            <html>
            <head>
                <title>API Test Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    pre {{ background: #f5f5f5; padding: 10px; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <h1>API Test Error</h1>
                <pre>{error_msg}</pre>
                <h2>Request Details:</h2>
                <pre>Headers: {headers}
URL: {API_URL}
Payload: {output}</pre>
                <p><a href="/">Back to Home</a></p>
            </body>
            </html>
            """
            
    except Exception as e:
        print(f"Exception in test route: {str(e)}")
        return f"""
        <html>
        <head>
            <title>API Test Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                pre {{ background: #f5f5f5; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h1>API Test Error</h1>
            <pre>{str(e)}</pre>
            <p><a href="/">Back to Home</a></p>
        </body>
        </html>
        """

@app.route('/api/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        print("Starting profile update process...")
        
        # Get the authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            print("No valid authorization header found")
            return jsonify({'error': 'No token provided'}), 401
        
        # Get the token
        id_token = auth_header.split('Bearer ')[1]
        print("Token extracted from header")
        
        try:
            # Verify the token
            decoded_token = auth.verify_id_token(id_token)
            user_id = decoded_token['uid']
            print(f"Token verified for user: {user_id}")
        except Exception as e:
            print(f"Token verification failed: {str(e)}")
            return jsonify({'error': f'Invalid token: {str(e)}'}), 401
        
        # Get the request data
        data = request.get_json()
        if not data:
            print("No JSON data received")
            return jsonify({'error': 'No data provided'}), 400
            
        display_name = data.get('displayName')
        photo_file = data.get('photoFile')
        
        print(f"Received data - display_name: {display_name}, photo_file: {'present' if photo_file else 'not present'}")
        
        try:
            # Update the user's display name
            print(f"Updating display name to: {display_name}")
            auth.update_user(user_id, display_name=display_name)
            print("Display name updated successfully")
        except Exception as e:
            print(f"Error updating display name: {str(e)}")
            return jsonify({'error': f'Failed to update display name: {str(e)}'}), 500
        
        photo_url = None
        # Handle photo upload if provided
        if photo_file:
            try:
                print("Processing photo upload...")
                # Remove the data URL prefix
                photo_data = photo_file.split(',')[1]
                photo_bytes = base64.b64decode(photo_data)
                
                # Generate a unique filename
                filename = f"{uuid.uuid4()}.jpg"
                user_photo_dir = os.path.join(PROFILE_PHOTOS_DIR, user_id)
                os.makedirs(user_photo_dir, exist_ok=True)
                file_path = os.path.join(user_photo_dir, filename)
                
                print(f"Saving photo to: {file_path}")
                # Save the file locally
                with open(file_path, 'wb') as f:
                    f.write(photo_bytes)
                
                # Generate the URL for the photo
                photo_url = request.host_url.rstrip('/') + url_for('static', filename=f'profile_photos/{user_id}/{filename}')
                print(f"Generated photo URL: {photo_url}")
                
                # Update the user's photo URL in Firebase Auth
                print("Updating user photo URL in Firebase Auth")
                auth.update_user(user_id, photo_url=photo_url)
                print("Photo URL updated successfully")
            except Exception as e:
                print(f"Error uploading photo: {str(e)}")
                return jsonify({'error': f'Failed to upload photo: {str(e)}'}), 500
        
        # Update session data
        print("Updating session data")
        session['user_name'] = display_name
        if photo_url:
            session['photo_url'] = photo_url
        
        print("Profile update completed successfully")
        return jsonify({
            'success': True,
            'displayName': display_name,
            'photoURL': photo_url
        })
        
    except Exception as e:
        print(f"Unexpected error in update_profile: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-token', methods=['GET'])
@login_required
def get_token():
    try:
        # Get the user ID from the session
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Create a custom token
        custom_token = auth.create_custom_token(user_id)
        
        return jsonify({'token': custom_token.decode('utf-8')})
    except Exception as e:
        print(f"Error creating custom token: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.debug = True
    app.run()