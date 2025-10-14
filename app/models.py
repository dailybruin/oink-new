from django.db import models
from django.utils.text import slugify
from django.conf import settings
from . import drive
import re
from django.contrib.auth.models import User
from django.utils import timezone


class GoogleCredential(models.Model):
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

    class Meta:
        ordering = ['-publish_date', 'slug']

    def __str__(self):
        return self.slug

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
            sa_file = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', None)
            impersonate = getattr(settings, 'GOOGLE_IMPERSONATE_USER', None)
            share_public = getattr(settings, 'GOOGLE_SHARE_PUBLIC', False)
            share_domain = getattr(settings, 'GOOGLE_SHARE_DOMAIN', None)

            folder_name = self.slug
            created = None
            try:
                parent = getattr(settings, 'REPOSITORY_FOLDER_ID', None)
                created = drive.create_drive_folder(folder_name, parent_id=parent, service_account_file=sa_file,
                                                    impersonate_user=impersonate,
                                                    share_public=share_public,
                                                    share_domain=share_domain)
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
