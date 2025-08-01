# Django Photographer Portfolio Website

A modern, mobile-first Django website for photographers featuring public portfolios and private client albums with Google Drive integration.

## 🎯 Features

### Public Portfolio
- Responsive grid layout (mobile-first design)
- Dynamic galleries from Google Drive `Public_Portfolio/` folder
- Subfolders automatically become individual galleries
- Clean, minimalist design with monospace typography

### Private Client Albums
- URL format: `/album/<uuid>/`
- Secure access to private client photos
- Individual photo downloads
- Complete album ZIP downloads
- Integration with Google Drive `Private_Albums/` folder

### Admin Panel
- Staff-only admin interface
- Create and manage client albums
- Google Drive folder name configuration
- Album preview and management tools

### Contact System
- Simple mailto: integration
- Pre-filled email templates
- No web forms required

## ⚙️ Tech Stack

- **Backend**: Django 5.2.4
- **Database**: PostgreSQL
- **Storage**: Google Drive API
- **Deployment**: Vercel-ready
- **Design**: Mobile-first, minimalist CSS

## 📁 Project Structure

```
photo_portfolio_host/
├── photo_portfolio/          # Main Django project
├── portfolio/               # Public portfolio app
├── albums/                  # Private albums app
├── core/                    # Shared services
├── templates/               # HTML templates
├── static/                  # Static files
├── requirements.txt         # Python dependencies
├── vercel.json             # Vercel deployment config
└── README.md               # This file
```

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

```bash
# Set up PostgreSQL database
# Create database: photo_portfolio
# Update settings.py with your database credentials

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 3. Google Drive Integration

1. **Create Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable Google Drive API

2. **Create Service Account**
   - Go to "APIs & Services" > "Credentials"
   - Create Service Account
   - Download JSON credentials file

3. **Set up Google Drive folders**
   - Create `Public_Portfolio/` folder
   - Create `Private_Albums/` folder
   - Share folders with service account email

4. **Configure Environment Variables**
   ```bash
   export GOOGLE_DRIVE_CREDENTIALS_FILE="path/to/credentials.json"
   export GOOGLE_DRIVE_TOKEN_FILE="token.json"
   ```

### 4. Run Development Server

```bash
python manage.py runserver
```

Visit `http://localhost:8000` to see your portfolio!

## 🔧 Configuration

### Environment Variables

```bash
# Database
DB_NAME=photo_portfolio
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Google Drive
GOOGLE_DRIVE_CREDENTIALS_FILE=path/to/credentials.json
GOOGLE_DRIVE_TOKEN_FILE=token.json
```

### Customization

1. **Update Contact Information**
   - Edit `templates/portfolio/contact.html`
   - Update email address and contact details

2. **Customize Design**
   - Modify CSS in `templates/base.html`
   - Update colors, fonts, and layout

3. **Add Custom Galleries**
   - Create subfolders in Google Drive `Public_Portfolio/`
   - Images automatically appear on the website

## 📱 Mobile-First Design

The website is built with a mobile-first approach:

- **Mobile**: Single-column vertical layout
- **Tablet**: Two-column grid
- **Desktop**: Three-column grid with hover effects

## 🔒 Security Features

- UUID-based album URLs for privacy
- Staff-only admin access
- Secure Google Drive API integration
- No sensitive data in templates

## 🚀 Deployment

### Vercel Deployment

1. **Connect Repository**
   ```bash
   # Push to GitHub/GitLab
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Deploy on Vercel**
   - Connect your repository to Vercel
   - Set environment variables in Vercel dashboard
   - Deploy automatically

### Environment Variables for Production

Set these in your Vercel dashboard:
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `GOOGLE_DRIVE_CREDENTIALS_FILE`, `GOOGLE_DRIVE_TOKEN_FILE`
- `SECRET_KEY` (generate a new one for production)
- `DEBUG=False`

## 📊 Admin Usage

### Creating Client Albums

1. **Access Admin Panel**
   - Go to `/admin/`
   - Login with superuser credentials

2. **Create New Album**
   - Click "Client Albums" > "Add Client Album"
   - Fill in: Title, Date, Description
   - Set Google Drive folder name (must match subfolder in `Private_Albums/`)

3. **Share Album URL**
   - Copy the album URL: `/album/<uuid>/`
   - Send to client for private access

## 🛠️ Development

### Adding New Features

1. **Create New App**
   ```bash
   python manage.py startapp new_app
   ```

2. **Add to INSTALLED_APPS**
   - Update `photo_portfolio/settings.py`

3. **Create Views and URLs**
   - Follow existing patterns in `portfolio/` and `albums/`

### Testing

```bash
# Run tests
python manage.py test

# Check for issues
python manage.py check
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
- Check the Django documentation
- Review Google Drive API documentation
- Open an issue on GitHub

---

**Built with ❤️ using Django and Google Drive API** 
