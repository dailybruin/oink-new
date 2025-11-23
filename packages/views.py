import os
import requests
import urllib.parse
import logging
from django.conf import settings
from django.shortcuts import redirect, render
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import Package

# Additional imports for serving GridFS files
from django.http import HttpResponse, Http404
from bson import ObjectId
from gridfs.errors import NoFile
from oink_project.mongo import get_bucket

logger = logging.getLogger(__name__)

def index(request):
    user = request.user if request.user.is_authenticated else None
    
    if user and user.is_authenticated:
        # Get pinned packages (most recently fetched, limit to 3)
        pinned_packages = Package.objects.filter(
            last_fetched_date__isnull=False
        ).order_by('-last_fetched_date')[:3]
        
        # Get recent packages (by publish date, limit to 3)
        recent_packages = Package.objects.filter(
            publish_date__isnull=False
        ).order_by('-publish_date')[:3]
        
        return render(request, 'packages/index.html', {
            'user': user,
            'pinned_packages': pinned_packages,
            'recent_packages': recent_packages
        })
    
    # Not authenticated - show login page
    return render(request, 'packages/index.html', {'user': user})

def google_login(request):
    client_id = settings.GOOGLE_CLIENT_ID
    redirect_uri = request.build_absolute_uri('/google/callback/')
    scope = 'openid email profile'
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': redirect_uri,
        'access_type': 'offline',
        'prompt': 'consent select_account',
    }
    url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)
    logger.info('Redirecting to Google OAuth URL: %s', url)
    return redirect(url)

def google_callback(request):
    code = request.GET.get('code')
    if not code:
        return render(request, 'packages/error.html', {'error': 'No code from Google'})

    token_url = 'https://oauth2.googleapis.com/token'
    data = {
        'code': code,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': request.build_absolute_uri('/google/callback/'),
        'grant_type': 'authorization_code',
    }
    r = requests.post(token_url, data=data)
    token_resp = r.json()
    if 'error' in token_resp:
        logger.error('Error fetching token from Google: %s', token_resp)
        return render(request, 'packages/error.html', {'error': token_resp})

    id_token = token_resp.get('id_token')
    access_token = token_resp.get('access_token')
    refresh_token = token_resp.get('refresh_token')
    token_type = token_resp.get('token_type')
    expires_in = token_resp.get('expires_in')

    headers = {'Authorization': f'Bearer {access_token}'}
    userinfo = requests.get('https://www.googleapis.com/oauth2/v3/userinfo', headers=headers).json()

    email = userinfo.get('email')
    if not email or not email.endswith('@' + settings.EMAIL_DOMAIN):
        return render(request, 'packages/error.html', {'error': f'Must sign in with a {settings.EMAIL_DOMAIN} email'})

    username = email.split('@')[0]
    user, created = User.objects.get_or_create(username=username, defaults={'email': email, 'first_name': userinfo.get('given_name','')})
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)

    try:
        from .models import GoogleCredential
        from django.utils import timezone
        gc, _ = GoogleCredential.objects.get_or_create(user=user)
        gc.access_token = access_token or ''
        if refresh_token:
            gc.refresh_token = refresh_token
        gc.token_type = token_type or ''
        gc.scope = token_resp.get('scope','')
        if expires_in:
            gc.expires_at = timezone.now() + timezone.timedelta(seconds=int(expires_in))
        gc.save()
    except Exception:
        logger.exception('Failed to save GoogleCredential for user %s', user.username)
    return redirect('/')

def signout(request):
    logout(request)
    return redirect('/')

""" Stream a file from GridFS by its ObjectId (which is stored as a string in mongoDB)

    Example URL: /files/<file_id>/ """
@login_required
def serve_gridfs_file(request, file_id: str):
    try:
        oid = ObjectId(file_id)
    except Exception:
        raise Http404("Invalid file id")

    bucket = get_bucket()
    try:
        stream = bucket.open_download_stream(oid)
    except NoFile:
        raise Http404("File not found")

    """ Memory-efficient file read from GridFS

    This will read content

    In case for very large files, use StreamingHttpResponse with chunks for better memory usage """
    try:
        data = stream.read()
        # Access metadata from the stream's _file property before closing
        metadata = getattr(stream, 'metadata', {}) or {}
        content_type = metadata.get('contentType') or 'application/octet-stream'
        filename = getattr(stream, 'filename', None) or file_id
    finally:
        stream.close()

    response = HttpResponse(data, content_type=content_type)
    
    """ Inline by default but adjusts if you need attachment """
    response["Content-Disposition"] = f"inline; filename=\"{filename}\""
    return response
