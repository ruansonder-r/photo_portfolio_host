#!/bin/bash
# Manual build script for Vercel Django deployment

set -e  # Exit on any error

echo "🚀 Starting manual Django build for Vercel..."

# Set environment variables
export DJANGO_SETTINGS_MODULE=photo_portfolio.settings
export PYTHONPATH=/var/task

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Copy Google Drive credentials if they exist
if [ -f ".creds/photoportfolioruansonder-08e05af6152b.json" ]; then
    echo "🔐 Copying Google Drive credentials..."
    cp .creds/photoportfolioruansonder-08e05af6152b.json /tmp/credentials.json
    export GOOGLE_DRIVE_CREDENTIALS_FILE=/tmp/credentials.json
fi

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Run migrations
echo "🗄️ Running database migrations..."
python manage.py migrate --noinput

# Verify Django setup
echo "🔍 Verifying Django configuration..."
python manage.py check --deploy

echo "✅ Manual build completed successfully!"
echo "📊 Build Summary:"
echo "   - Dependencies installed"
echo "   - Static files collected"
echo "   - Database migrations applied"
echo "   - Django configuration verified" 
