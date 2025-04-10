#!/bin/bash

# Text Summarization App Deployment Script

echo "Starting deployment process..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please create one based on .env.example"
    exit 1
fi

# Check if serviceAccountKey.json exists
if [ ! -f serviceAccountKey.json ]; then
    echo "Error: serviceAccountKey.json not found. Please add your Firebase service account key"
    exit 1
fi

# Create profile_photos directory if it doesn't exist
mkdir -p static/profile_photos

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Deploy to Render (if render.yaml exists)
if [ -f render.yaml ]; then
    echo "Deploying to Render..."
    # Note: This requires the Render CLI to be installed and configured
    # render deploy
    echo "Please deploy to Render manually using the render.yaml file"
fi

# Deploy to Netlify (if netlify.toml exists)
if [ -f netlify.toml ]; then
    echo "Deploying to Netlify..."
    # Note: This requires the Netlify CLI to be installed and configured
    # netlify deploy --prod
    echo "Please deploy to Netlify manually using the netlify.toml file"
fi

# Deploy to Heroku (if Procfile exists)
if [ -f Procfile ]; then
    echo "Deploying to Heroku..."
    # Note: This requires the Heroku CLI to be installed and configured
    # git push heroku main
    echo "Please deploy to Heroku manually using the Procfile"
fi

echo "Deployment process completed!"
echo "Please check the README.md for detailed deployment instructions." 