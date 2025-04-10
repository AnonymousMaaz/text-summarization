# Text Summarization App

A Flask-based web application that uses the Hugging Face API to generate summaries of text input. The app features user authentication with Firebase, profile management, and customizable summarization parameters.

## Features

- Text summarization with customizable parameters (min/max length, beam search)
- User authentication with Firebase
- Profile management with photo upload
- Responsive design
- Fallback summarization when API is unavailable

## Prerequisites

- Python 3.8 or higher
- Firebase account
- Hugging Face API key

## Local Development Setup

1. Clone the repository:
   ```bash
   git clone <your-repository-url>
   cd text-summarization
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On Unix or MacOS
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory with your configuration:
   ```
   HUGGINGFACE_API_KEY=your_huggingface_api_key
   FIREBASE_API_KEY=your_firebase_api_key
   FIREBASE_AUTH_DOMAIN=your_firebase_auth_domain
   FIREBASE_PROJECT_ID=your_firebase_project_id
   FIREBASE_STORAGE_BUCKET=your_firebase_storage_bucket
   FIREBASE_MESSAGING_SENDER_ID=your_firebase_messaging_sender_id
   FIREBASE_APP_ID=your_firebase_app_id
   FLASK_ENV=development
   FLASK_APP=app.py
   SECRET_KEY=your_secret_key
   PORT=10000
   ```

5. Set up Firebase configuration:
   - Copy `firebaseConfig.example.js` to `firebaseConfig.js` and update with your Firebase project settings
   - Copy `serviceAccountKey.example.json` to `serviceAccountKey.json` and update with your Firebase service account key
   - You can find these values in your Firebase Console under Project Settings

6. Run the application:
   ```bash
   python app.py
   ```

## Deployment

### Render (Recommended)

1. Create a Render account at [render.com](https://render.com)
2. Connect your GitHub repository
3. Create a new Web Service
4. Configure the service:
   - Name: text-summarizer
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Add your environment variables from `.env`
   - Add your Firebase service account key as a secret file

### Netlify (Frontend Only)

1. Create a Netlify account at [netlify.com](https://www.netlify.com)
2. Connect your GitHub repository
3. Configure the build settings:
   - Build command: `echo 'No build step needed'`
   - Publish directory: `templates`
4. Add your environment variables in Netlify dashboard
5. Add your Firebase configuration in the Netlify environment variables

## Environment Variables

- `HUGGINGFACE_API_KEY`: Your Hugging Face API key
- `FIREBASE_API_KEY`: Firebase API key
- `FIREBASE_AUTH_DOMAIN`: Firebase auth domain
- `FIREBASE_PROJECT_ID`: Firebase project ID
- `FIREBASE_STORAGE_BUCKET`: Firebase storage bucket
- `FIREBASE_MESSAGING_SENDER_ID`: Firebase messaging sender ID
- `FIREBASE_APP_ID`: Firebase app ID
- `FLASK_ENV`: Flask environment (development/production)
- `SECRET_KEY`: Flask secret key
- `PORT`: Port to run the application on

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 