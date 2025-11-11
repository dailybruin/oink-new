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
    cached_article_preview = models.TextField(blank=True, default='')
    images = models.JSONField(default=dict, blank=True)
    data = models.JSONField(default=dict, blank=True)
    processing = models.BooleanField(default=False)

    class Meta:
        ordering = ['-publish_date', 'slug']

    def __str__(self):
        return self.slug

    def _get_drive_settings(self):
        """Get Google Drive settings from Django settings."""
        return {
            'service_account_file': getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', None),
            'impersonate_user': getattr(settings, 'GOOGLE_IMPERSONATE_USER', None),
            'share_public': getattr(settings, 'GOOGLE_SHARE_PUBLIC', False),
            'share_domain': getattr(settings, 'GOOGLE_SHARE_DOMAIN', None),
            'parent_id': getattr(settings, 'REPOSITORY_FOLDER_ID', None),
            'share_role': 'writer',
        }

    def save(self, *args, **kwargs):
        if self.google_drive_url and not self.google_drive_id:
            url = self.google_drive_url.strip()
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

        if not self.google_drive_url:
            drive_settings = self._get_drive_settings()
            folder_name = self.slug
            created = None
            try:
                created = drive.create_drive_folder(
                    folder_name,
                    parent_id=drive_settings['parent_id'],
                    service_account_file=drive_settings['service_account_file'],
                    impersonate_user=drive_settings['impersonate_user'],
                    share_public=drive_settings['share_public'],
                    share_domain=drive_settings['share_domain'],
                    share_role=drive_settings['share_role'],
                )
            except Exception:
                created = None

            if created and isinstance(created, dict):
                self.google_drive_id = created.get('id', '')
                self.google_drive_url = created.get('url') or ''
            elif isinstance(created, str) and created.strip():
                url = created.strip()
                self.google_drive_url = url
                if not self.google_drive_id and url.startswith('http'):
                    try:
                        self.google_drive_id = url.rstrip('/').split('/')[-1]
                    except Exception:
                        self.google_drive_id = ''
            else:
                root = getattr(settings, 'GOOGLE_DRIVE_ROOT', 'https://drive.google.com/drive/folders') or 'https://drive.google.com/drive/folders'
                if not isinstance(root, str) or not root.startswith('http'):
                    root = 'https://drive.google.com/drive/folders'
                root = root.rstrip('/')
                safe = slugify(self.slug)
                self.google_drive_url = f"{root}/{safe}"
        super().save(*args, **kwargs)

    def setup_and_save(self, user, pset_slug: str = ''):
        """Ensure Drive folder exists (id/url) and create starter doc if missing."""
        created_now = False
        if not (self.google_drive_url and self.google_drive_id):
            drive_settings = self._get_drive_settings()
            try:
                created = drive.create_drive_folder(
                    self.slug, 
                    parent_id=drive_settings['parent_id'],
                    service_account_file=drive_settings['service_account_file'],
                    impersonate_user=drive_settings['impersonate_user'],
                    share_public=drive_settings['share_public'],
                    share_domain=drive_settings['share_domain'],
                    share_role=drive_settings['share_role']
                )
            except Exception:
                created = None
            if created and isinstance(created, dict):
                self.google_drive_id = created.get('id', '')
                self.google_drive_url = created.get('url') or self.google_drive_url
                created_now = True
        self.save()
        try:
            if self.google_drive_id:
                drive_settings = self._get_drive_settings()
                drive.ensure_article_doc_in_folder(
                    self.google_drive_id,
                    service_account_file=drive_settings['service_account_file'],
                    impersonate_user=drive_settings['impersonate_user'],
                    share_role=drive_settings['share_role']
                )
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
        
        """ added to support GridFS storage of images and AML files """
        gridfs_images = []
        gridfs_aml = {}
        gridfs_image_assets = []
        gridfs_aml_assets = []

        try:
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
                print(f"[FETCH] Found {len(items)} files in Drive folder")
                try:
                    import archieml as _arch
                    print(f"[FETCH] ArchieML imported successfully")
                except Exception as e:
                    _arch = None
                    print(f"[FETCH] ArchieML import failed: {e}")
                for it in items:
                    name = it.get('name') or ''
                    mime = it.get('mimeType') or ''
                    fid = it.get('id')
                    print(f"[FETCH] Processing file: {name} (mime: {mime})")
                    # Check for .aml files FIRST (even if they're Google Docs)
                    if name.lower().endswith('.aml'):
                        print(f"[FETCH] Downloading AML file: {name}")
                        try:
                            # If it's a Google Doc, export it; otherwise download directly
                            if mime == 'application/vnd.google-apps.document':
                                print(f"[FETCH] Exporting Google Doc as plain text")
                                media = service.files().export(fileId=fid, mimeType='text/plain').execute()
                            else:
                                print(f"[FETCH] Downloading file directly")
                                media = service.files().get_media(fileId=fid).execute()
                            txt = media.decode('utf-8') if isinstance(media, bytes) else media
                            print(f"[FETCH] Downloaded {len(txt)} bytes of AML")
                            if getattr(settings, 'MONGODB_FILESTORE_ENABLED', False):
                                try:
                                    from .file_store import store_text
                                    file_id = store_text(
                                        name=name,
                                        text=txt,
                                        content_type='text/plain; charset=utf-8',
                                        slug=self.slug,
                                        asset_type='aml',
                                        extra_metadata={'sourceId': fid, 'source': 'drive'},
                                    )
                                    gridfs_aml[name] = file_id
                                    gridfs_aml_assets.append({
                                        'name': name,
                                        'file_id': file_id,
                                        'asset_type': 'aml',
                                        'content_type': 'text/plain; charset=utf-8',
                                        'source': 'drive',
                                        'source_id': fid,
                                    })
                                except Exception:
                                    pass
                            if _arch:
                                try:
                                    parsed = _arch.loads(txt)
                                    # Fix malformed pull quotes from ArchieML parser
                                    if isinstance(parsed, dict) and 'content' in parsed and isinstance(parsed['content'], list):
                                        fixed_content = []
                                        i = 0
                                        while i < len(parsed['content']):
                                            block = parsed['content'][i]
                                            # Check if next block exists
                                            next_block = parsed['content'][i + 1] if i + 1 < len(parsed['content']) else None

                                            # Detect malformed pull quote split:
                                            # 1. {"type": "pull", "value": {}}
                                            # 2. {"value": {"caption": "..."}} (missing type)
                                            if (isinstance(block, dict) and
                                                block.get('type') == 'pull' and
                                                (not block.get('value') or not block['value'].get('caption')) and
                                                next_block and isinstance(next_block, dict) and
                                                'type' not in next_block and
                                                'value' in next_block and
                                                isinstance(next_block.get('value'), dict) and
                                                'caption' in next_block['value']):
                                                # Merge the two objects
                                                fixed_content.append({
                                                    'type': 'pull',
                                                    'value': {
                                                        'caption': next_block['value']['caption']
                                                    }
                                                })
                                                i += 2  # Skip both blocks
                                            else:
                                                fixed_content.append(block)
                                                i += 1
                                        parsed['content'] = fixed_content
                                        print(f"[FETCH] Fixed malformed pull quotes in content")

                                    # Reorder image block fields (alt, url, credit, caption)
                                    if isinstance(parsed, dict) and 'content' in parsed and isinstance(parsed['content'], list):
                                        for block in parsed['content']:
                                            if isinstance(block, dict) and block.get('type') == 'image' and isinstance(block.get('value'), dict):
                                                image_val = block['value']
                                                ordered_image = {}
                                                image_field_order = ['alt', 'url', 'credit', 'caption']
                                                for key in image_field_order:
                                                    if key in image_val:
                                                        ordered_image[key] = image_val[key]
                                                # Add any remaining fields
                                                for key in image_val.keys():
                                                    if key not in ordered_image:
                                                        ordered_image[key] = image_val[key]
                                                block['value'] = ordered_image

                                    # Reorder fields to match Kerckhoff format:
                                    # author, content, then metadata in specific order
                                    if isinstance(parsed, dict):
                                        ordered = {}
                                        # Define exact field order
                                        field_order = [
                                            'author', 'content', 'excerpt', 'updated', 'coveralt',
                                            'coverimg', 'headline', 'authorbio', 'covercred',
                                            'articleType', 'authoremail', 'authortwitter'
                                        ]
                                        # Add fields in specified order
                                        for key in field_order:
                                            if key in parsed:
                                                ordered[key] = parsed[key]
                                        # Add any remaining fields not in the order list
                                        for key in parsed.keys():
                                            if key not in ordered:
                                                ordered[key] = parsed[key]
                                        parsed = ordered

                                    aml_files[name] = parsed
                                    print(f"[FETCH] Successfully parsed AML with ArchieML")
                                except Exception as e:
                                    aml_files[name] = txt
                                    print(f"[FETCH] ArchieML parsing failed: {e}, storing raw text")
                            else:
                                aml_files[name] = txt
                                print(f"[FETCH] No ArchieML, storing raw text")
                            
                            # Optionally persist AML to MongoDB GridFS
                            if getattr(settings, 'MONGODB_FILESTORE_ENABLED', False):
                                try:
                                    from .file_store import store_text
                                    file_id = store_text(
                                        name=name,
                                        text=txt,
                                        content_type='text/plain; charset=utf-8',
                                        slug=self.slug,
                                        asset_type='aml',
                                        extra_metadata={'sourceId': fid, 'source': 'drive'},
                                    )
                                    gridfs_aml[name] = file_id
                                    gridfs_aml_assets.append({
                                        'name': name,
                                        'file_id': file_id,
                                        'asset_type': 'aml',
                                        'content_type': 'text/plain; charset=utf-8',
                                        'source': 'drive',
                                        'source_id': fid,
                                    })
                                except Exception:
                                    pass
                        except Exception:
                            aml_files[name] = ''
                    elif name.lower().startswith('article') and mime == 'application/vnd.google-apps.document':
                        # Article file that is NOT .aml (e.g., just "article" or "Article doc")
                        print(f"[FETCH] Exporting article Google Doc (not .aml)")
                        try:
                            exported = service.files().export(fileId=fid, mimeType='text/plain').execute()
                            article_text = exported.decode('utf-8') if isinstance(exported, bytes) else exported
                            print(f"[FETCH] Exported {len(article_text)} bytes of article text")
                        except Exception as e:
                            article_text = ''
                            print(f"[FETCH] Failed to export article: {e}")
                    elif mime.startswith('image'):
                        gdrive_images.append({'name': name, 'url': f'/packages/{self.slug}/image/{fid}/'})
                        
                        # Optionally persist image bytes to MongoDB GridFS
                        if getattr(settings, 'MONGODB_FILESTORE_ENABLED', False):
                            try:
                                content = service.files().get_media(fileId=fid).execute()
                                if isinstance(content, str):
                                    content = content.encode('utf-8')
                                from .file_store import store_bytes
                                file_id = store_bytes(
                                    name=name,
                                    content_type=mime or 'application/octet-stream',
                                    data=content,
                                    slug=self.slug,
                                    asset_type='image',
                                    extra_metadata={'sourceId': fid, 'source': 'drive'},
                                )
                                gridfs_images.append({'name': name, 'id': file_id, 'content_type': mime or 'application/octet-stream'})
                                gridfs_image_assets.append({
                                    'name': name,
                                    'file_id': file_id,
                                    'asset_type': 'image',
                                    'content_type': mime or 'application/octet-stream',
                                    'source': 'drive',
                                    'source_id': fid,
                                })
                            except Exception:
                                pass
        except Exception:
            pass

        """ Replace cached fields with the freshly fetched content,
        
        just in case if we want to edit the .aml and images later """
        self.cached_article_preview = article_text
        images_payload = {'gdrive': gdrive_images}
        if getattr(settings, 'MONGODB_FILESTORE_ENABLED', False) and gridfs_images:
            images_payload['gridfs'] = gridfs_images
        self.images = images_payload
        
        fallback_text = self.cached_article_preview or ''
        if getattr(settings, 'MONGODB_FILESTORE_ENABLED', False) and not gridfs_aml_assets and fallback_text.strip():
            try:
                from .file_store import store_text
                fallback_name = f"{self.slug}-article.aml"
                file_id = store_text(
                    name=fallback_name,
                    text=fallback_text,
                    content_type='text/plain; charset=utf-8',
                    slug=self.slug,
                    asset_type='aml',
                    extra_metadata={'source': 'drive', 'generated': 'doc-export'},
                )
                gridfs_aml[fallback_name] = file_id
                gridfs_aml_assets.append({
                    'name': fallback_name,
                    'file_id': file_id,
                    'asset_type': 'aml',
                    'content_type': 'text/plain; charset=utf-8',
                    'source': 'drive',
                    'source_id': None,
                    'generated': 'doc-export',
                })
                if fallback_name not in aml_files:
                    aml_files[fallback_name] = fallback_text
            except Exception:
                pass

        """ Store AML data exactly as fetched so subsequent loads match Drive content """
        data_out = aml_files
        if getattr(settings, 'MONGODB_FILESTORE_ENABLED', False) and gridfs_aml:
            data_out['_gridfs_aml'] = gridfs_aml
        self.data = data_out
        print(f"[FETCH] Saving data to database: {list(data_out.keys())}")
        print(f"[FETCH] Image count - gdrive: {len(gdrive_images)}, gridfs: {len(gridfs_images)}")
        self.last_fetched_date = dj_tz.now()
        self.processing = False
        self.save()
        print(f"[FETCH] Fetch completed successfully!")

        if getattr(settings, 'MONGODB_FILESTORE_ENABLED', False):
            try:
                from .file_store import update_package_asset_index
                update_package_asset_index(
                    self.slug,
                    aml_assets=gridfs_aml_assets,
                    image_assets=gridfs_image_assets,
                )
            except Exception:
                pass

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
