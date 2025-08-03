# Vercel Deployment Guide

## Overview

This application uses a hybrid approach for image handling:

- **Development**: Images are downloaded and stored locally for faster performance
- **Production (Vercel)**: Images are served directly from Google Drive URLs

## Why This Approach?

Vercel's serverless environment has limitations that make local image storage impractical:

1. **Ephemeral Storage**: Files downloaded during build are wiped after deployment
2. **Size Limits**: Lambda functions have size limits (50mb) that can't hold all images
3. **Cold Starts**: Each serverless function instance starts fresh

## Environment Setup

### Required Environment Variables

Set these in your Vercel project settings:

```
GOOGLE_DRIVE_CREDENTIALS=your_service_account_json_here
SECRET_KEY=your_django_secret_key
DEBUG=False
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=5432
```

### Google Drive Service Account

1. Create a service account in Google Cloud Console
2. Enable Google Drive API
3. Share your Google Drive folders with the service account email
4. Download the JSON credentials
5. Set the entire JSON as the `GOOGLE_DRIVE_CREDENTIALS` environment variable

## Deployment Process

### 1. Database Setup

Ensure your database is set up and migrations are applied:

```bash
python manage.py migrate
```

### 2. Static Files

Collect static files:

```bash
python manage.py collectstatic --noinput
```

### 3. Deploy to Vercel

The application will automatically:
- Use Google Drive URLs in production
- Use local images in development
- Handle authentication via environment variables

## How It Works

### Development Environment
- Images are downloaded to `media/images/`
- Served from local filesystem
- Faster loading times
- Offline capability

### Production Environment (Vercel)
- Images served directly from Google Drive
- No local storage needed
- Automatic authentication via service account
- URLs like: `https://drive.google.com/uc?id=FILE_ID&export=view`

## Troubleshooting

### Images Not Loading in Production

1. **Check Service Account Permissions**
   - Ensure the service account has access to your Google Drive folders
   - Verify the folders are shared with the service account email

2. **Check Environment Variables**
   - Verify `GOOGLE_DRIVE_CREDENTIALS` is set correctly
   - Ensure the JSON is properly formatted

3. **Check Google Drive API**
   - Ensure Google Drive API is enabled in Google Cloud Console
   - Verify the service account has the necessary scopes

### Performance Issues

1. **Image Loading Speed**
   - Google Drive URLs may be slower than local files
   - Consider using a CDN for frequently accessed images
   - Implement image caching strategies

2. **API Rate Limits**
   - Google Drive API has rate limits
   - Consider implementing caching for API responses
   - Monitor API usage in Google Cloud Console

## Monitoring

### Google Drive API Usage

Monitor your API usage in Google Cloud Console:
1. Go to Google Cloud Console
2. Navigate to APIs & Services > Dashboard
3. Check Google Drive API usage

### Vercel Logs

Check Vercel function logs for any errors:
1. Go to your Vercel dashboard
2. Navigate to your project
3. Check the Functions tab for logs

## Security Considerations

1. **Service Account Security**
   - Keep your service account credentials secure
   - Use environment variables, never commit credentials to code
   - Regularly rotate service account keys

2. **Google Drive Permissions**
   - Only share necessary folders with the service account
   - Use the principle of least privilege
   - Regularly audit folder permissions

## Future Improvements

1. **CDN Integration**
   - Consider using a CDN for better image delivery
   - Implement image optimization and compression

2. **Caching Strategy**
   - Implement Redis or similar for API response caching
   - Cache frequently accessed image metadata

3. **Image Optimization**
   - Implement automatic image resizing
   - Add WebP format support
   - Implement lazy loading for better performance 
