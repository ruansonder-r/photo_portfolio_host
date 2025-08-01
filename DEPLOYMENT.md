# Deployment Guide - Django Photographer Portfolio

This guide covers deploying the Django photographer portfolio website to various platforms.

## 🚀 Quick Deployment Options

### Option 1: Vercel (Recommended)

1. **Prepare Repository**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Deploy to Vercel**
   - Go to [vercel.com](https://vercel.com)
   - Connect your GitHub/GitLab repository
   - Vercel will automatically detect Django and deploy

3. **Configure Environment Variables**
   In Vercel dashboard, set these environment variables:
   ```
   DB_NAME=your_db_name
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_HOST=your_db_host
   DB_PORT=5432
   GOOGLE_DRIVE_CREDENTIALS_FILE=your_credentials_json
   GOOGLE_DRIVE_TOKEN_FILE=token.json
   SECRET_KEY=your_secret_key
   DEBUG=False
   ```

### Option 2: Railway

1. **Deploy to Railway**
   - Go to [railway.app](https://railway.app)
   - Connect your repository
   - Add PostgreSQL service
   - Set environment variables

### Option 3: Heroku

1. **Prepare for Heroku**
   ```bash
   # Add Procfile
   echo "web: gunicorn photo_portfolio.wsgi" > Procfile
   
   # Add gunicorn to requirements
   echo "gunicorn==21.2.0" >> requirements.txt
   ```

2. **Deploy to Heroku**
   ```bash
   heroku create your-app-name
   heroku addons:create heroku-postgresql:mini
   heroku config:set SECRET_KEY=your_secret_key
   heroku config:set DEBUG=False
   git push heroku main
   ```

## 🔧 Database Setup

### PostgreSQL (Recommended)

1. **Local Development**
   ```bash
   # Install PostgreSQL
   sudo apt install postgresql postgresql-contrib
   
   # Run setup script
   python setup_database.py
   ```

2. **Production Database**
   - Use managed PostgreSQL service (Railway, Supabase, etc.)
   - Set environment variables for database connection

### Alternative: SQLite (Development Only)

For quick testing, you can use SQLite:

```python
# In settings.py, replace DATABASES with:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

## 🔐 Google Drive API Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable Google Drive API

### 2. Create Service Account

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Fill in service account details
4. Download JSON credentials file

### 3. Set up Google Drive Folders

1. Create these folders in Google Drive:
   - `Public_Portfolio/` (for public galleries)
   - `Private_Albums/` (for client albums)

2. Share folders with service account email:
   - Right-click folder > "Share"
   - Add service account email with "Editor" permissions

### 4. Configure Environment

```bash
# Set credentials file path
export GOOGLE_DRIVE_CREDENTIALS_FILE="path/to/credentials.json"
export GOOGLE_DRIVE_TOKEN_FILE="token.json"
```

## 📱 Mobile-First Design Features

The website is optimized for mobile devices:

- **Responsive Grid**: Adapts from 1 column (mobile) to 3 columns (desktop)
- **Touch-Friendly**: Large buttons and easy navigation
- **Fast Loading**: Optimized images and caching
- **Clean Typography**: Monospace font for professional look

## 🔒 Security Considerations

### Production Checklist

- [ ] Set `DEBUG=False` in production
- [ ] Generate new `SECRET_KEY`
- [ ] Use HTTPS only
- [ ] Configure proper database permissions
- [ ] Set up Google Drive API credentials
- [ ] Enable Django security middleware
- [ ] Set up proper logging

### Environment Variables

```bash
# Required for production
SECRET_KEY=your_secure_secret_key
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_secure_password
DB_HOST=your_db_host
DB_PORT=5432

# Google Drive
GOOGLE_DRIVE_CREDENTIALS_FILE=path/to/credentials.json
GOOGLE_DRIVE_TOKEN_FILE=token.json
```

## 🛠️ Customization

### Update Contact Information

Edit `templates/portfolio/contact.html`:
```html
<a href="mailto:your-email@example.com?subject=Photography%20Inquiry">
    Send Email
</a>
```

### Customize Design

Edit CSS in `templates/base.html`:
```css
/* Change colors */
body { color: #333; }
.btn-primary { background: #your-color; }

/* Change fonts */
body { font-family: 'Your Font', monospace; }
```

### Add Custom Galleries

1. Create subfolder in Google Drive `Public_Portfolio/`
2. Upload images to subfolder
3. Gallery automatically appears on website

## 📊 Monitoring and Maintenance

### Logs

```bash
# View application logs
python manage.py runserver --verbosity=2

# Check for errors
python manage.py check --deploy
```

### Database Maintenance

```bash
# Backup database
pg_dump your_db_name > backup.sql

# Restore database
psql your_db_name < backup.sql
```

### Google Drive Integration

- Monitor API quotas in Google Cloud Console
- Check folder permissions regularly
- Verify service account access

## 🆘 Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check database credentials
   - Verify PostgreSQL is running
   - Test connection manually

2. **Google Drive API Errors**
   - Verify credentials file path
   - Check folder permissions
   - Ensure API is enabled

3. **Static Files Not Loading**
   - Run `python manage.py collectstatic`
   - Check static file configuration
   - Verify web server configuration

4. **Images Not Displaying**
   - Check Google Drive folder structure
   - Verify service account permissions
   - Test API authentication

### Getting Help

1. Check Django logs for errors
2. Verify environment variables
3. Test Google Drive API separately
4. Review deployment platform documentation

## 🎯 Performance Optimization

### Caching

- Django views are cached for 15 minutes
- Static files are cached by web server
- Consider CDN for global performance

### Image Optimization

- Use appropriate image formats (WebP, JPEG)
- Optimize image sizes for web
- Consider lazy loading for large galleries

### Database Optimization

- Use database indexes for frequently queried fields
- Monitor query performance
- Consider read replicas for high traffic

---

**Ready to deploy! 🚀**

For additional help, check the main README.md file or open an issue on GitHub. 
