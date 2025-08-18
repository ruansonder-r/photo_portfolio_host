#!/bin/bash
# Vercel build script

set -e

echo "🚀 Starting Vercel build..."

# Set Django settings
export DJANGO_SETTINGS_MODULE=photo_portfolio.settings

# Install dependencies 
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Run migrations
echo "🗄️ Running migrations..."
python manage.py migrate --noinput

echo "✅ Build completed!"
