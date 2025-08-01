#!/bin/bash
# Build script for Vercel deployment

echo "Building Django application..."

# Install dependencies
pip install -r requirements.txt

# Copy Google Drive credentials if they exist
if [ -f ".creds/photoportfolioruansonder-08e05af6152b.json" ]; then
    echo "Copying Google Drive credentials..."
    cp .creds/photoportfolioruansonder-08e05af6152b.json /tmp/credentials.json
    export GOOGLE_DRIVE_CREDENTIALS_FILE=/tmp/credentials.json
fi

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate --noinput

echo "Build completed successfully!" 
