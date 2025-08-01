#!/bin/bash
# Build script for Vercel deployment

echo "🚀 Starting Django build for Vercel..."

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Copy Google Drive credentials if they exist
if [ -f ".creds/photoportfolioruansonder-08e05af6152b.json" ]; then
    echo "🔐 Copying Google Drive credentials..."
    cp .creds/photoportfolioruansonder-08e05af6152b.json /tmp/credentials.json
    export GOOGLE_DRIVE_CREDENTIALS_FILE=/tmp/credentials.json
fi

# Set environment variables for Vercel
export DJANGO_SETTINGS_MODULE=photo_portfolio.settings
export PYTHONPATH=/var/task

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Run migrations
echo "🗄️ Running database migrations..."
python manage.py migrate --noinput

echo "✅ Build completed successfully!" 
