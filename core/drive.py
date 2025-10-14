import os
import logging
from typing import Optional
try:
    from requests_oauthlib import OAuth2Session
except Exception:
    OAuth2Session = None

logger = logging.getLogger(__name__)

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except Exception:
    service_account = None
    build = None
    HttpError = Exception


def create_drive_folder(folder_name: str, *, parent_id: Optional[str] = None,
                        service_account_file: Optional[str] = None,
                        impersonate_user: Optional[str] = None,
                        share_public: bool = False,
                        share_domain: Optional[str] = None,
                        share_role: str = 'reader') -> Optional[dict]:
    """
    Create a Google Drive folder and optionally set sharing.

    Requirements:
    - A service account JSON key file path provided via service_account_file.
    - Service account must have domain-wide delegation enabled and the
      Drive API scope granted, if impersonating a user.

    Returns the folder URL on success, or None on failure.
    """
    if service_account_file is None:
        # Support both our explicit var and the standard Google ADC env var
        service_account_file = (
            os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
            or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        )

    if not service_account_file:
        logger.info('No service account credentials configured; skipping Drive folder creation')
        return None

    if service_account is None or build is None:
        logger.exception('google API libraries are not installed')
        return None

    scopes = ['https://www.googleapis.com/auth/drive']

    try:
        # Allow passing a JSON blob via env var in addition to a file path
        creds = None
        try:
            if service_account_file.strip().startswith('{'):
                import json as _json
                info = _json.loads(service_account_file)
                creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
            else:
                creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=scopes)
        except Exception:
            # Fall back to file loading if JSON parsing failed
            creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=scopes)
        if impersonate_user:
            creds = creds.with_subject(impersonate_user)

        service = build('drive', 'v3', credentials=creds, cache_discovery=False)

        file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent_id:
            file_metadata['parents'] = [parent_id]
        created = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = created.get('id')
        if not folder_id:
            logger.error('Failed to get folder id after creation for %s', folder_name)
            return None

        # Set sharing permissions
        if share_public:
            perm = {'type': 'anyone', 'role': share_role}
            service.permissions().create(fileId=folder_id, body=perm, fields='id').execute()
        elif share_domain and share_domain.strip():
            perm = {'type': 'domain', 'role': 'writer', 'domain': share_domain}
            service.permissions().create(fileId=folder_id, body=perm, fields='id').execute()

        url = f'https://drive.google.com/drive/folders/{folder_id}'
        return {'id': folder_id, 'url': url}

    except HttpError as e:
        logger.exception('Google Drive API error creating folder %s: %s', folder_name, e)
        return None
    except Exception:
        logger.exception('Unexpected error creating Drive folder for %s', folder_name)
        return None


def create_google_doc_in_folder(folder_id: str, title: str = 'article.aml', *,
                                service_account_file: Optional[str] = None,
                                impersonate_user: Optional[str] = None,
                                share_role: str = 'reader') -> Optional[dict]:
    """
    Create a Google Doc in an existing Drive folder using a service account.

    Returns a dict with 'id' and 'url' on success or None on failure.
    """
    if service_account_file is None:
        service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')

    if not service_account_file:
        logger.info('No service account file configured; skipping Google Doc creation')
        return None

    if service_account is None or build is None:
        logger.exception('google API libraries are not installed')
        return None

    scopes = ['https://www.googleapis.com/auth/drive']

    try:
        creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=scopes)
        if impersonate_user:
            creds = creds.with_subject(impersonate_user)

        service = build('drive', 'v3', credentials=creds, cache_discovery=False)

        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document',
        }
        if folder_id:
            file_metadata['parents'] = [folder_id]
        created = service.files().create(body=file_metadata, fields='id,webViewLink').execute()
        file_id = created.get('id')
        webview = created.get('webViewLink')
        if not file_id:
            logger.error('Failed to create Google Doc %s in folder %s', title, folder_id)
            return None

        try:
            perm = {'type': 'anyone', 'role': share_role}
            service.permissions().create(fileId=file_id, body=perm, fields='id').execute()
        except Exception:
            pass

        return {'id': file_id, 'url': webview or f'https://docs.google.com/document/d/{file_id}/edit'}

    except HttpError as e:
        logger.exception('Google Drive API error creating doc %s in %s: %s', title, folder_id, e)
        return None
    except Exception:
        logger.exception('Unexpected error creating Google Doc %s in folder %s', title, folder_id)
        return None


def get_oauth2_session(user, token_updater=True):
    """
    Build an OAuth2Session for the given Django user using saved
    GoogleCredential tokens. Returns None if credentials are missing.

    If token_updater is True, a callback will persist refreshed tokens
    back into the GoogleCredential model.
    """
    if OAuth2Session is None:
        logger.error('requests-oauthlib not installed; cannot create OAuth2Session')
        return None

    try:
        from .models import GoogleCredential
    except Exception:
        logger.exception('Failed to import GoogleCredential model')
        return None

    try:
        cred = user.google_credential
    except Exception:
        logger.info('No GoogleCredential for user %s', getattr(user, 'username', 'unknown'))
        return None

    if not cred.refresh_token and not cred.access_token:
        logger.info('GoogleCredential missing tokens for user %s', user.username)
        return None

    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    token = {
        'access_token': cred.access_token,
        'refresh_token': cred.refresh_token,
        'token_type': cred.token_type or 'Bearer',
        'scope': cred.scope or 'https://www.googleapis.com/auth/drive',
    }

    def _token_updater(new_token):
        try:
            cred.access_token = new_token.get('access_token') or cred.access_token
            if new_token.get('refresh_token'):
                cred.refresh_token = new_token.get('refresh_token')
            expires_in = new_token.get('expires_in')
            if expires_in:
                from django.utils import timezone
                cred.expires_at = timezone.now() + timezone.timedelta(seconds=int(expires_in))
            cred.save()
        except Exception:
            logger.exception('Failed to update GoogleCredential for user %s', user.username)

    session = OAuth2Session(client_id, token=token, scope=token.get('scope'))
    # requests_oauthlib expects a dict for auto-refresh info
    session._client_id = client_id
    session._client_secret = client_secret

    if token_updater:
        session.token_updater = _token_updater

    return session


def ensure_article_doc_in_folder(folder_id: str, *,
                                 service_account_file: Optional[str] = None,
                                 impersonate_user: Optional[str] = None,
                                 share_role: str = 'writer') -> Optional[dict]:
    """Ensure a Google Doc named like 'article.aml' exists in the folder; create if missing."""
    if service_account_file is None:
        service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
    if not service_account_file or service_account is None or build is None:
        return None
    try:
        creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=['https://www.googleapis.com/auth/drive'])
        if impersonate_user:
            creds = creds.with_subject(impersonate_user)
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        q = f"name contains 'article' and mimeType = 'application/vnd.google-apps.document' and '{folder_id}' in parents"
        found = service.files().list(q=q, fields='files(id,name,webViewLink)').execute().get('files', [])
        if found:
            return {'id': found[0].get('id'), 'url': found[0].get('webViewLink')}
        return create_google_doc_in_folder(folder_id, title='article.aml', service_account_file=service_account_file,
                                           impersonate_user=impersonate_user, share_role=share_role)
    except Exception:
        logger.exception('ensure_article_doc_in_folder failed for %s', folder_id)
        return None