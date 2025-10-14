from django.db import models
from django.utils.text import slugify
from django.conf import settings
from . import drive
import re
from django.contrib.auth.models import User
from django.utils import timezone


class GoogleCredential(models.Model):
    """Stores OAuth2 tokens for a user to call Google APIs as that user.

    This is intentionally minimal: it stores access_token, refresh_token,
    expiry and scope. The token values are stored in plain text here for
    convenience; in production consider encrypting or using a secrets store.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='google_credential')
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_type = models.CharField(max_length=32, blank=True)
    scope = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'GoogleCredential({self.user.username})'


class Package(models.Model):
    CATEGORY_PRIME = 'prime'
    CATEGORY_FLATPAGES = 'flatpages'
    CATEGORY_ALUMNI = 'alumni'

    CATEGORY_CHOICES = [
        (CATEGORY_PRIME, 'Prime'),
        (CATEGORY_FLATPAGES, 'Flatpages'),
        (CATEGORY_ALUMNI, 'Alumni'),
    ]

    slug = models.SlugField(max_length=255, unique=True, help_text='The article slug (e.g. sports.mbb.oregon)')
    description = models.TextField(blank=True)
    google_drive_url = models.URLField(blank=True, help_text="(Optional) Link to the Google Drive folder. We'll generate one if left blank.")
    google_drive_id = models.CharField(max_length=128, blank=True)
    publish_date = models.DateField(null=True, blank=True)
    last_fetched_date = models.DateTimeField(null=True, blank=True)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default=CATEGORY_PRIME)
    created_at = models.DateTimeField(auto_now_add=True)
    # Workflow/cache fields for fetch pipeline
    cached_article_preview = models.TextField(blank=True, default='')
    images = models.JSONField(default=dict, blank=True)
    data = models.JSONField(default=dict, blank=True)
    processing = models.BooleanField(default=False)

    class Meta:
        ordering = ['-publish_date', 'slug']

    def __str__(self):
        return self.slug

    def save(self, *args, **kwargs):
        # If the user supplied a Drive URL, try to normalize it to the canonical
        # folder link and extract the folder id. This allows users to paste a
        # variety of Drive links (drive/folders/<id>, open?id=<id>, docs links)
        # and still have a consistent `google_drive_url` and `google_drive_id`.
        if self.google_drive_url and not self.google_drive_id:
            url = self.google_drive_url.strip()
            # Try several common patterns to extract an id
            patterns = [
                r"/folders/([a-zA-Z0-9_-]+)",
                r"[?&]id=([a-zA-Z0-9_-]+)",
                r"/d/([a-zA-Z0-9_-]+)",
            ]
            found = None
            for p in patterns:
                m = re.search(p, url)
                if m:
                    found = m.group(1)
                    break
            if found:
                self.google_drive_id = found
                self.google_drive_url = f"https://drive.google.com/drive/folders/{found}"

        # Auto-generate a Google Drive URL when none is provided.
        if not self.google_drive_url:
            # First try to create a real Drive folder (service account impersonating a user)
            sa_file = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', None)
            impersonate = getattr(settings, 'GOOGLE_IMPERSONATE_USER', None)
            share_public = getattr(settings, 'GOOGLE_SHARE_PUBLIC', False)
            share_domain = getattr(settings, 'GOOGLE_SHARE_DOMAIN', None)

            # Attempt to create via Drive API; fallback to slug-based URL if unavailable
            folder_name = self.slug
            created = None
            try:
                parent = getattr(settings, 'REPOSITORY_FOLDER_ID', None)
                # Use writer role when public sharing is enabled
                share_role = 'writer' if share_public else 'reader'
                created = drive.create_drive_folder(
                    folder_name,
                    parent_id=parent,
                    service_account_file=sa_file,
                    impersonate_user=impersonate,
                    share_public=share_public,
                    share_domain=share_domain,
                    share_role=share_role,
                )
            except Exception:
                created = None

            if created and isinstance(created, dict):
                self.google_drive_id = created.get('id', '')
                self.google_drive_url = created.get('url') or ''
            elif isinstance(created, str) and created.strip():
                # Be tolerant if the Drive helper returns a URL string
                url = created.strip()
                self.google_drive_url = url
                if not self.google_drive_id and url.startswith('http'):
                    try:
                        self.google_drive_id = url.rstrip('/').split('/')[-1]
                    except Exception:
                        self.google_drive_id = ''
            else:
                # Fallback to a predictable folder URL under the standard Drive root.
                # Guard against misconfiguration like GOOGLE_DRIVE_ROOT="/" producing "/<slug>".
                root = getattr(settings, 'GOOGLE_DRIVE_ROOT', 'https://drive.google.com/drive/folders') or 'https://drive.google.com/drive/folders'
                if not isinstance(root, str) or not root.startswith('http'):
                    root = 'https://drive.google.com/drive/folders'
                root = root.rstrip('/')
                safe = slugify(self.slug)
                self.google_drive_url = f"{root}/{safe}"
        super().save(*args, **kwargs)

    # High-level creation/setup hook matching older flow naming
    def setup_and_save(self, user, pset_slug: str = ''):
        """Ensure Drive folder exists (id/url) and create starter doc if missing."""
        # If a folder URL was pasted, validation/normalization already handled in save()
        created_now = False
        if not (self.google_drive_url and self.google_drive_id):
            sa_file = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', None)
            impersonate = getattr(settings, 'GOOGLE_IMPERSONATE_USER', None)
            share_public = getattr(settings, 'GOOGLE_SHARE_PUBLIC', False)
            share_domain = getattr(settings, 'GOOGLE_SHARE_DOMAIN', None)
            parent = getattr(settings, 'REPOSITORY_FOLDER_ID', None)
            share_role = 'writer' if share_public else 'reader'
            try:
                created = drive.create_drive_folder(self.slug, parent_id=parent, service_account_file=sa_file,
                                                    impersonate_user=impersonate,
                                                    share_public=share_public,
                                                    share_domain=share_domain,
                                                    share_role=share_role)
            except Exception:
                created = None
            if created and isinstance(created, dict):
                self.google_drive_id = created.get('id', '')
                self.google_drive_url = created.get('url') or self.google_drive_url
                created_now = True
        # Save any updates
        self.save()
        # Create starter Google Doc
        try:
            if self.google_drive_id:
                sa_file = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', None)
                impersonate = getattr(settings, 'GOOGLE_IMPERSONATE_USER', None)
                # Ensure an article doc exists (create if missing)
                drive.ensure_article_doc_in_folder(self.google_drive_id,
                                                   service_account_file=sa_file,
                                                   impersonate_user=impersonate,
                                                   share_role='writer')
        except Exception:
            pass
        return self

    def fetch_from_gdrive(self, user):
        """Fetch article text, AML, and images from Drive and update cache fields.

        Note: S3 transfer is not implemented here; can be added behind settings later.
        """
        from django.utils import timezone as dj_tz
        self.processing = True
        self.save()
        folder_id = self.google_drive_id or (self.google_drive_url or '').rstrip('/').split('/')[-1]

        article_text = ''
        aml_files = {}
        gdrive_images = []

        try:
            # Prefer service account for server-side access
            from google.oauth2 import service_account as _sa
            from googleapiclient.discovery import build as _gbuild
            sa_file = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', None)
            if sa_file:
                scopes = ['https://www.googleapis.com/auth/drive']
                creds = _sa.Credentials.from_service_account_file(sa_file, scopes=scopes)
                service = _gbuild('drive', 'v3', credentials=creds, cache_discovery=False)
                q = f"'{folder_id}' in parents"
                resp = service.files().list(q=q, fields='files(id,name,mimeType,webViewLink,webContentLink)').execute()
                items = resp.get('files', [])
                try:
                    import archieml as _arch
                except Exception:
                    _arch = None
                for it in items:
                    name = it.get('name') or ''
                    mime = it.get('mimeType') or ''
                    fid = it.get('id')
                    if name.lower().startswith('article') and mime == 'application/vnd.google-apps.document':
                        try:
                            exported = service.files().export(fileId=fid, mimeType='text/plain').execute()
                            article_text = exported.decode('utf-8') if isinstance(exported, bytes) else exported
                        except Exception:
                            article_text = ''
                    elif name.lower().endswith('.aml'):
                        try:
                            media = service.files().get_media(fileId=fid).execute()
                            txt = media.decode('utf-8') if isinstance(media, bytes) else media
                            if _arch:
                                try:
                                    parsed = _arch.loads(txt)
                                    aml_files[name] = parsed
                                except Exception:
                                    aml_files[name] = txt
                            else:
                                aml_files[name] = txt
                        except Exception:
                            aml_files[name] = ''
                    elif mime.startswith('image'):
                        gdrive_images.append({'name': name, 'url': it.get('webContentLink') or it.get('webViewLink') or ''})
        except Exception:
            # Leave fields as defaults and finish below
            pass

        self.cached_article_preview = article_text or self.cached_article_preview
        existing_images = self.images or {}
        existing_images['gdrive'] = gdrive_images
        # Keep s3 map if present
        self.images = existing_images
        # Simple mapping: store AML files dict under data
        self.data = aml_files or self.data
        self.last_fetched_date = dj_tz.now()
        self.processing = False
        self.save()

        # Create a lightweight version snapshot
        try:
            PackageVersion.objects.create(
                package=self,
                article_data=self.cached_article_preview or '',
                data=self.data or {},
                creator=user if getattr(user, 'is_authenticated', False) else None,
                version_description=f"New PackageVersion created on {dj_tz.now().strftime('%Y-%m-%d %H:%M:%S')}",
            )
        except Exception:
            pass

        return self


class PackageVersion(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='versions')
    article_data = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    version_description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Version {self.pk} of {self.package.slug}"
