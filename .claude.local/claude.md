# Oink - Daily Bruin CMS

## Project Overview

Oink is a complete rewrite of Kerckhoff, the content management system (CMS) used by the Daily Bruin (UCLA's student newspaper) for [prime.dailybruin.com](https://prime.dailybruin.com/) and flatpages. It serves as a proxy/middleman for Google Drive, fetching AML files and images from Drive folders and making them accessible as JSON for static site generation.

**Key Difference from Kerckhoff**: Modern tech stack (Django 5, Python 3.11) replacing legacy Node.js v6 implementation.

### Tech Stack
- **Backend**: Django 5.0
- **Databases**: SQLite (primary), MongoDB with GridFS (file storage)
- **Authentication**: Google OAuth 2.0
- **External APIs**: Google Drive API
- **Deployment**: Docker, Gunicorn
- **Frontend**: Bootstrap 5, Vanilla JavaScript (no Vue.js despite initial plans)

---

## Current Branch: oink-3

### What Your Partner Worked On
1. **Fixed Data Persistence**: Identified that slugs are stored in `db.sqlite3`, while fetched data (images/AML) are stored in MongoDB
2. **MongoDB Integration**: Implemented GridFS for storing images and `.aml` files
3. **New Files Created**:
   - `oink_project/mongo.py` - MongoDB connection manager with connection pooling
   - `packages/file_store.py` - GridFS storage helpers (store_bytes, store_text, read_file)
4. **Client-Side Rendering**: Modified `package_view.html` to render fetched data on the client side using cached data from database
5. **Database Models Updated**: Added `cached_article_preview`, `data`, `images`, and `processing` fields to Package model

---

## Architecture Overview

### Database Architecture (Dual Database System)

**SQLite (db.sqlite3)** - Primary Database
- **Location**: `/Users/bryanzhang/Documents/GitHub/oink-new/db.sqlite3`
- **Stores**: Package metadata, slugs, user data, OAuth tokens
- **Key Tables**:
  - `packages_package` - Package slugs, Drive URLs, cached data
  - `packages_packageversion` - Version history snapshots
  - `packages_googlecredential` - OAuth access/refresh tokens
  - Django auth tables

**Package Model Schema**:
```python
slug (unique, varchar 255)          # URL-friendly identifier
description (text)                  # Package description
google_drive_url (varchar 200)      # Link to Drive folder
google_drive_id (varchar 128)       # Extracted folder ID
publish_date (date, nullable)       # Publication date
last_fetched_date (datetime)        # Last successful fetch
category (varchar 32)               # prime/flatpages/alumni
cached_article_preview (text)       # Plain text article content
data (JSON)                         # Parsed AML files + GridFS IDs
images (JSON)                       # Image URLs/GridFS IDs
processing (bool)                   # Fetch operation in progress
```

**MongoDB (GridFS)** - File Storage (Optional)
- **Connection**: MongoDB Atlas (`oink-1.y83rav2.mongodb.net`)
- **Database**: `oink`
- **Bucket**: `files`
- **Stores**: Images (binary), AML files (text)
- **Enabled by**: `MONGODB_FILESTORE_ENABLED` environment variable (currently False by default)

**Data Flow**:
```
Google Drive Folder
      ↓
fetch_from_gdrive() in models.py
      ↓
   ┌──────┴──────┐
   ↓             ↓
SQLite          MongoDB (optional)
- slug          - image bytes
- metadata      - AML file text
- Drive URLs
- GridFS IDs
```

### Key Components

**1. Google Drive Integration** (`packages/drive.py`)
- Service account authentication with `service-account.json`
- Functions:
  - `create_drive_folder()` - Creates shared folders
  - `create_google_doc_in_folder()` - Creates article.aml docs
  - `ensure_article_doc_in_folder()` - Checks/creates article.aml
  - `get_oauth2_session()` - User OAuth for Drive access

**2. Data Fetching** (`packages/models.py:160-273`)
- `Package.fetch_from_gdrive()` - Main fetch operation
- Process:
  1. Set `processing=True` flag
  2. List files in Drive folder by ID
  3. Download and process each file type:
     - **Article files** → `cached_article_preview` (plain text)
     - **AML files** → Parse with ArchieML → store in `data` JSON
     - **Images** → Store Drive URLs in `images['gdrive']`
  4. Optionally upload to GridFS (if `MONGODB_FILESTORE_ENABLED=True`)
  5. Update `last_fetched_date` and set `processing=False`
  6. Create `PackageVersion` snapshot

**3. File Storage** (`packages/file_store.py`)
- `store_bytes(name, content_type, data)` → Returns ObjectId
- `store_text(name, text, content_type)` → Returns ObjectId
- `read_file(file_id)` → Returns (bytes, content_type, filename)

**4. File Serving** (`packages/views.py:98-126`)
- Route: `/files/<file_id>/`
- Streams files from GridFS by ObjectId
- Sets correct Content-Type from metadata
- Returns as inline (not attachment)

**5. Authentication** (`packages/views.py`)
- Google OAuth 2.0 flow:
  1. `/google/login/` → Redirects to Google accounts
  2. `/google/callback/` → Exchanges code for tokens
  3. Validates email domain (`@media.ucla.edu`)
  4. Stores tokens in `GoogleCredential` model
  5. Auto-refreshes access tokens when expired

**6. Package Views** (`packages/package_views.py`)
- `packages_list()` - List all packages + create form
- `package_detail()` - View package detail page with cached data
- `package_fetch()` - AJAX endpoint to trigger fresh fetch
- `_format_images()` - Converts GridFS IDs to `/files/<id>/` URLs

**7. Client-Side Rendering** (`templates/packages/package_view.html`)
```javascript
// Embedded initial payload from database
{{ initial_payload|json_script:"initial-payload" }}

// Hydrate page immediately with cached data
const initialPayload = JSON.parse(
  document.getElementById("initial-payload").textContent
);
renderPackageData(initialPayload);

// "Fetch from Drive" button refreshes data
fetch(`/packages/${slug}/fetch/`)
  .then(r => r.json())
  .then(renderPackageData)
```

---

## Project Structure

```
oink-new/
├── oink_project/              # Django project settings
│   ├── settings.py            # Database config, middleware
│   ├── urls.py                # Root URL routing
│   ├── wsgi.py                # WSGI application
│   └── mongo.py               # MongoDB connection manager (NEW)
│
├── packages/                  # Main Django app
│   ├── models.py              # Package, PackageVersion, GoogleCredential
│   ├── views.py               # Authentication + GridFS file serving
│   ├── package_views.py       # Package CRUD operations
│   ├── drive.py               # Google Drive API integration
│   ├── file_store.py          # GridFS storage helpers (NEW)
│   ├── forms.py               # PackageForm
│   ├── admin.py               # Django admin configuration
│   ├── urls.py                # App URL routing
│   ├── templatetags/          # Custom template tags
│   ├── migrations/            # Database migrations
│   │   ├── 0003_googlecredential.py
│   │   └── 0004_package_cached_article_preview_package_data_and_more.py
│   ├── management/commands/   # Custom Django commands
│   └── tests/                 # Test files
│
├── templates/packages/        # Django templates
│   ├── base.html              # Base template with Bootstrap 5
│   ├── index.html             # Landing/login page
│   ├── packages_list.html     # Package listing + create modal
│   └── package_view.html      # Slug detail page (CLIENT-SIDE RENDERING)
│
├── static/                    # Static source files
│   └── app.css                # Custom CSS
│
├── staticfiles/               # Collected static files (Django admin + custom)
│
├── keys/                      # Google credentials
│   └── service-account.json   # Service account key
│
├── db.sqlite3                 # SQLite database
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # Docker configuration
├── Dockerfile                 # Docker image
├── entrypoint.sh              # Docker entrypoint
└── .env                       # Environment variables
```

---

## Critical Issues to Fix

### 1. Login Page Internal Server Error (First Load Issue)

**Symptom**: Users experience an internal server error on the first page load after logging in, but it works after refreshing.

**Potential Root Causes**:
1. **Missing GoogleCredential Creation**:
   - If `views.google_callback()` fails to create GoogleCredential before redirect
   - Check `packages/views.py:78` - uses `get_or_create()` (should be safe)

2. **Database Migration Not Run**:
   - Verify migrations are applied: `python manage.py migrate`
   - Check: `python manage.py showmigrations packages`

3. **Environment Variables Missing/Invalid**:
   - `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` not set in `.env`
   - Would cause OAuth token exchange to fail

4. **Session Cookie Issues**:
   - Django session not properly initialized
   - Check `SESSION_COOKIE_SECURE` settings in production

**Debug Steps**:
- [ ] Enable Django debug toolbar or check logs in console
- [ ] Add print statements in `google_callback()` to trace execution
- [ ] Verify migrations: `python manage.py showmigrations`
- [ ] Test OAuth flow in browser DevTools (Network tab)
- [ ] Check Django logs for exceptions during callback

**Files to Investigate**:
- `packages/views.py:43-89` - `google_callback()` function
- `oink_project/settings.py:127-144` - Session and auth middleware
- `.env` - Verify GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET

---

### 2. Formatting and Display Issues in Slug Pages

**Symptom**: Images and text files are not displaying correctly compared to official Kerckhoff slugs. Comment in `package_view.html:58` says "HOWEVER THIS IS BROKEN FOR NOW".

**Specific Problems**:

#### A. Image Display Broken
- **Current Behavior**: Images may not load or show broken links
- **Expected Behavior**: Images should display as thumbnails with links

**Potential Causes**:
1. **GridFS Images Not Accessible**:
   - `MONGODB_FILESTORE_ENABLED` defaults to False
   - GridFS IDs stored in database but MongoDB not configured
   - `/files/<file_id>/` endpoint returns 404 or errors

2. **Drive Image Permissions**:
   - Images stored as Drive URLs but not publicly accessible
   - Requires authentication to view
   - Check sharing settings in `drive.create_drive_folder()`

3. **Template Image Rendering**:
   - `_format_images()` may not correctly convert data structure
   - Template expects `{url: ..., name: ...}` but receives different format

**Debug Steps**:
- [ ] Check `MONGODB_FILESTORE_ENABLED` in `.env`
- [ ] Verify GridFS files exist: Connect to MongoDB and list `files.files` collection
- [ ] Test `/files/<file_id>/` endpoint directly in browser
- [ ] Check Drive sharing permissions for test images
- [ ] Inspect `initial_payload.images` structure in browser DevTools

**Files to Investigate**:
- `templates/packages/package_view.html:64-92` - Image rendering logic
- `packages/package_views.py:70-88` - `_format_images()` function
- `packages/views.py:98-126` - `serve_gridfs_file()` endpoint
- `packages/models.py:230-256` - Image fetching logic

#### B. Article Text Formatting Issues
- **Current Behavior**: Article preview shows plain text without formatting
- **Expected Behavior**: Rich text with paragraphs, pull quotes, headings

**Potential Causes**:
1. **Plain Text Storage**:
   - `cached_article_preview` stores raw plain text from Drive API
   - No HTML or Markdown conversion

2. **AML Parsing Not Applied**:
   - AML files stored in `data` JSON but not rendered in article-container
   - Template only shows `cached_article_preview`, not parsed AML

3. **Missing Rich Text Renderer**:
   - No Markdown/HTML renderer in client-side JavaScript
   - Need to convert AML structure to HTML

**Solution Approach**:
1. Parse AML `content` blocks and convert to HTML
2. Render pull quotes with Bootstrap card styling
3. Apply proper typography classes from Bootstrap

**Files to Investigate**:
- `templates/packages/package_view.html:35-50` - `renderPackageData()` function
- `packages/package_views.py:116-171` - AML plain text parser
- `packages/models.py:174-229` - AML parsing with ArchieML library

---

### 3. Database Separation and Unification

**Issue**: Images and AML files stored in separate MongoDB database from slug metadata in SQLite, making data management complex.

**Current Architecture**:
- **SQLite**: Package metadata, slugs, Drive URLs
- **MongoDB**: Images (binary), AML files (text) - when `MONGODB_FILESTORE_ENABLED=True`

**Problems**:
1. **Data Consistency**:
   - No CASCADE delete from Package to GridFS files
   - Deleting a package leaves orphaned files in MongoDB
   - No cleanup mechanism

2. **Flag Confusion**:
   - `MONGODB_FILESTORE_ENABLED` defaults to False
   - Some packages have GridFS data, others use Drive URLs
   - Inconsistent behavior across environments

3. **Migration Complexity**:
   - How to migrate existing packages to GridFS?
   - How to revert from GridFS to Drive URLs?
   - No migration scripts provided

4. **Backup/Restore**:
   - Must backup both SQLite and MongoDB
   - Data split across two systems
   - Harder to maintain consistency

**Recommended Solution**:

**Option A: Unify in SQLite (Simpler)**
- Store images and AML files as BLOBs in SQLite
- Single database for backups
- Easier to maintain consistency
- Trade-off: Larger SQLite file size

**Option B: Unify in MongoDB (More Scalable)**
- Migrate Package metadata to MongoDB
- Use MongoDB for all data storage
- Better for large file storage
- Trade-off: More complex setup, requires MongoDB hosting

**Option C: Keep Dual System but Improve**
- Implement CASCADE delete for GridFS files
- Add migration commands:
  - `python manage.py migrate_to_gridfs` - Move all Drive files to GridFS
  - `python manage.py cleanup_orphaned_files` - Remove unused GridFS files
- Make `MONGODB_FILESTORE_ENABLED` consistent across environments
- Add database consistency checks

**Files to Modify**:
- `packages/models.py` - Add `delete()` override to clean up GridFS
- `packages/file_store.py` - Add `delete_file(file_id)` function
- `packages/management/commands/` - Add migration/cleanup commands

**Recommended Approach**:
Start with **Option C** (improve dual system) since your partner already implemented GridFS. Then consider migrating to **Option B** (MongoDB-only) if the project scales.

---

## Development Workflow

### Setup Instructions

1. **Clone and Navigate**:
```bash
cd /Users/bryanzhang/Documents/GitHub/oink-new
git checkout oink-3
```

2. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure Environment Variables** (`.env`):
```bash
SECRET_KEY=your-secret-key
DJANGO_DEBUG=1
EMAIL_DOMAIN=media.ucla.edu
GOOGLE_CLIENT_ID=679499178457-***
GOOGLE_CLIENT_SECRET=GOCSPX-***
MONGODB_URI=mongodb+srv://online_db_user:***@oink-1.y83rav2.mongodb.net/
MONGODB_FILESTORE_ENABLED=True  # Enable GridFS storage
GOOGLE_SHARE_DOMAIN=media.ucla.edu
GOOGLE_SERVICE_ACCOUNT_FILE=/app/keys/service-account.json
```

4. **Run Migrations**:
```bash
python manage.py migrate
```

5. **Create Superuser** (if needed):
```bash
python manage.py createsuperuser
```

6. **Run Development Server**:
```bash
python manage.py runserver
# Or with Docker:
docker-compose up
```

7. **Access Application**:
- Local: http://localhost:8000
- Docker: http://localhost:5001

### Useful Commands

```bash
# Check migrations status
python manage.py showmigrations

# Create new migration
python manage.py makemigrations

# Open Django shell
python manage.py shell

# Collect static files
python manage.py collectstatic

# Run tests
python manage.py test packages

# Database queries
sqlite3 db.sqlite3
> SELECT slug, last_fetched_date, processing FROM packages_package;
```

### Testing GridFS Integration

```python
# In Django shell (python manage.py shell)
from packages.file_store import store_text, read_file

# Store a test file
file_id = store_text("test.txt", "Hello World", "text/plain")
print(f"Stored with ID: {file_id}")

# Read it back
data, content_type, filename = read_file(file_id)
print(f"Retrieved: {data.decode()}")
```

---

## Next Steps and Recommendations

### Immediate Priorities

1. **Fix Login Error** (Critical):
   - Add detailed logging to `google_callback()`
   - Test OAuth flow with fresh user
   - Verify migrations are applied

2. **Fix Image Display** (High Priority):
   - Set `MONGODB_FILESTORE_ENABLED=True` in `.env`
   - Test GridFS file serving endpoint
   - Fix `_format_images()` to properly flatten structure
   - Ensure Drive images have public sharing

3. **Improve Article Rendering** (High Priority):
   - Convert AML content blocks to HTML
   - Add rich text formatting (paragraphs, pull quotes)
   - Apply Bootstrap typography classes

4. **Fix Data Persistence** (Medium Priority):
   - Add comprehensive error handling to `fetch_from_gdrive()`
   - Ensure `processing` flag is always cleared (use finally block)
   - Add logging for fetch operations

5. **Database Cleanup** (Medium Priority):
   - Implement CASCADE delete for GridFS files
   - Add management command to cleanup orphaned files
   - Consider unifying databases (Option C above)

### Code Quality Improvements

- [ ] Add ArchieML to requirements.txt (currently optional)
- [ ] Add comprehensive tests for fetch operations
- [ ] Add error logging throughout application
- [ ] Document MongoDB migration strategy
- [ ] Add API documentation for JSON endpoints

### Feature Enhancements

- [ ] Add async task queue (Celery) for long-running fetches
- [ ] Add real-time progress updates for fetch operations
- [ ] Add file upload UI for manual image/AML uploads
- [ ] Add version comparison view (diff between PackageVersions)
- [ ] Add bulk fetch operation for all packages

---

## Troubleshooting

### Common Issues

**Issue**: "ImproperlyConfigured: Requested setting INSTALLED_APPS"
- **Solution**: Ensure `DJANGO_SETTINGS_MODULE=oink_project.settings` is set

**Issue**: GridFS files not loading (404 error)
- **Solution**: Verify `MONGODB_FILESTORE_ENABLED=True` and MongoDB connection

**Issue**: "google.auth.exceptions.DefaultCredentialsError"
- **Solution**: Check `GOOGLE_SERVICE_ACCOUNT_FILE` path and permissions

**Issue**: Package fetch fails silently
- **Solution**: Check `processing` flag stuck at True, reset in Django admin

**Issue**: Drive API quota exceeded
- **Solution**: Check Google Cloud Console quotas, implement caching

### Debugging Tips

1. **Enable Django Debug Toolbar**:
```python
# settings.py
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

2. **Check Logs**:
```bash
# Docker logs
docker-compose logs -f web

# Django logs (printed to console)
python manage.py runserver
```

3. **Inspect Database**:
```bash
sqlite3 db.sqlite3
> .tables
> .schema packages_package
> SELECT * FROM packages_package;
```

4. **Test Drive API**:
```bash
# Verify service account works
python -c "from packages.drive import list_files_in_folder; print(list_files_in_folder('FOLDER_ID'))"
```

---

## Resources

- **Django Documentation**: https://docs.djangoproject.com/
- **Google Drive API**: https://developers.google.com/drive/api/v3/reference
- **GridFS Documentation**: https://pymongo.readthedocs.io/en/stable/api/gridfs/
- **ArchieML**: http://archieml.org/
- **Bootstrap 5**: https://getbootstrap.com/docs/5.3/

---

## Contact and Support

- **Repository**: `/Users/bryanzhang/Documents/GitHub/oink-new`
- **Branch**: `oink-3`
- **Main Branch**: `main`

For questions about the original Kerckhoff system or Daily Bruin workflows, consult the External Sites team.
