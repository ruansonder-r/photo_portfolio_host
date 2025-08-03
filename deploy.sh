#!/bin/bash

# Photo Portfolio Deployment Script
# This script handles the deployment process including Google Drive sync

echo "Starting Photo Portfolio deployment..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "Running database migrations..."
python manage.py migrate

# Download public images from Google Drive
echo "Syncing Google Drive and downloading public images..."
python manage.py sync_google_drive --download-public

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Deployment completed successfully!"
echo "You can now start the server with: python manage.py runserver" 
