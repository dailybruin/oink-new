# Oink - Package Management System

A Django application for managing article packages with Google Drive integration.

## Project Structure

```
oink/
├── packages/                 # Main Django app (renamed from 'core')
│   ├── models.py            # Package and GoogleCredential models
│   ├── views.py             # Authentication views (Google OAuth)
│   ├── package_views.py      # Package CRUD views (renamed from packages_views.py)
│   ├── admin.py             # Django admin configuration
│   ├── forms.py             # Package forms
│   ├── drive.py             # Google Drive API integration
│   ├── urls.py              # URL routing
│   └── migrations/          # Database migrations
├── templates/
│   ├── packages/            # Package-related templates
│   └── components/          # Reusable template components
├── oink_project/            # Django project settings
│   ├── settings.py          # Main settings file
│   ├── urls.py             # Root URL configuration
│   └── wsgi.py             # WSGI configuration
├── keys/                    # Google service account credentials
├── staticfiles/             # Collected static files
└── manage.py               # Django management script
```

## Key Improvements Made

### 1. **Eliminated Duplication**

- Removed duplicate `app/` directory (was identical to `core/`)
- Consolidated all functionality into single `packages/` app
- Removed legacy archive directories (`legacy/`, `src/`)

### 2. **Improved Naming**

- Renamed `core/` → `packages/` (more intuitive)
- Renamed `packages_views.py` → `package_views.py` (cleaner)
- Renamed `slack_login()` → `google_login()` (accurate naming)

### 3. **Code Consolidation**

- Created `_get_drive_settings()` helper method to reduce repetitive Google Drive setup code
- Consolidated duplicate template references
- Streamlined admin actions

### 4. **Project Structure**

- Fixed broken settings file (was importing non-existent `src.settings`)
- Updated all references to use correct app names
- Moved templates to proper structure

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Create `.env` file with required settings:

   ```
   SECRET_KEY=your-secret-key
   DJANGO_DEBUG=1
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   EMAIL_DOMAIN=media.ucla.edu
   GOOGLE_SERVICE_ACCOUNT_FILE=path/to/service-account.json
   ```

3. Run migrations:

   ```bash
   python manage.py migrate
   ```

4. Start development server:
   ```bash
   python manage.py runserver
   ```

## Features

- **Package Management**: Create, view, and manage article packages
- **Google Drive Integration**: Automatic folder creation and file management
- **Google OAuth**: Secure authentication with Google accounts
- **Admin Interface**: Django admin for package management
- **Template System**: Clean, organized template structure

## Models

- **Package**: Main article package with Google Drive integration
- **GoogleCredential**: OAuth tokens for Google API access
- **PackageVersion**: Version history for packages
