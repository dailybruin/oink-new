from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Package
from .forms import PackageForm
from django.conf import settings
from . import drive
from django.http import JsonResponse, HttpResponseNotFound, HttpResponseForbidden
import os
import logging
from django.contrib import messages
try:
    import archieml
except Exception:
    archieml = None
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except Exception:
    service_account = None
    build = None
    HttpError = Exception


def packages_list(request):
    category = request.GET.get('category')
    if category:
        packages = Package.objects.filter(category=category)
    else:
        packages = Package.objects.all()

    form = PackageForm()
    if request.method == 'POST':
        form = PackageForm(request.POST)
        logger = logging.getLogger(__name__)
        valid = form.is_valid()
        logger.info('Package form submitted, valid=%s', valid)
        if not valid:
            logger.warning('Package form errors: %s', form.errors.as_json())
        if valid:
            pkg = form.save()
            logger.info('Package saved via form: %s (id=%s)', pkg.slug, pkg.pk)
            messages.success(request, f'Package {pkg.slug} created')
            try:
                pkg.setup_and_save(request.user, '')
            except Exception:
                logging.getLogger(__name__).exception('setup_and_save failed for %s', pkg.slug)

            return redirect('packages_list')

    categories = [
        (Package.CATEGORY_PRIME, 'prime'),
        (Package.CATEGORY_FLATPAGES, 'flatpages'),
        (Package.CATEGORY_ALUMNI, 'alumni-site'),
    ]

    return render(request, 'packages/packages_list.html', {
        'packages': packages,
        'form': form,
        'categories': categories,
        'active_category': category or '',
    })


@login_required
def package_create(request):
    return redirect('packages_list')


def package_detail(request, slug):
    try:
        pkg = Package.objects.get(slug=slug)
    except Package.DoesNotExist:
        return HttpResponseNotFound('Package not found')

    return render(request, 'packages/package_view.html', {
        'package': pkg,
    })


def _parse_aml_plain_text(txt: str) -> dict:
    result = {
        'author': '', 'headline': '', 'excerpt': '', 'updated': '', 'articleType': '',
        'coverimg': '', 'coveralt': '', 'covercred': '', 'authorbio': '',
        'authoremail': '', 'authortwitter': '',
        'content': [],
    }
    lines = (txt or '').splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('[+content]'):
            i += 1
            break
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip().lower()
            val = val.strip()
            if key == 'coverimg' or key == 'cover image':
                result['coverimg'] = val
            elif key == 'coveralt' or key == 'cover alt':
                result['coveralt'] = val
            elif key == 'covercred' or key == 'cover credit':
                result['covercred'] = val
            elif key in result:
                result[key] = val
        i += 1

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s == '{.pull}':
            caption = ''
            i += 1
            while i < len(lines):
                l2 = lines[i].strip()
                if l2 == '{}':
                    break
                if l2.lower().startswith('caption:'):
                    caption = l2.split(':', 1)[1].strip()
                i += 1
            result['content'].append({'type': 'pull', 'value': {'caption': caption}})
            while i < len(lines) and lines[i].strip() != '{}':
                i += 1
            if i < len(lines) and lines[i].strip() == '{}':
                i += 1
            continue
        result['content'].append({'type': 'text', 'value': s})
        i += 1
    return {'article.aml': result}

def _read_local_sample(slug: str):
    base = os.path.join(os.path.dirname(__file__), 'sample_data', slug)
    article_path = os.path.join(base, 'article.aml')
    result = {'article': '', 'aml_files': {}, 'images': []}
    if os.path.exists(article_path):
        with open(article_path, 'r', encoding='utf-8') as fh:
            txt = fh.read()
        result['article'] = txt
        if archieml:
            try:
                parsed = archieml.loads(txt)
                result['aml_files']['article.aml'] = parsed
            except Exception:
                result['aml_files']['article.aml'] = txt
        else:
            result['aml_files']['article.aml'] = txt
    return result


def package_fetch(request, slug):
    try:
        pkg = Package.objects.get(slug=slug)
    except Package.DoesNotExist:
        return JsonResponse({'error': 'Package not found'}, status=404)

    folder_id = pkg.google_drive_id or (pkg.google_drive_url or '').rstrip('/').split('/')[-1]

    sa_file = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', None)
    if sa_file and service_account and build:
        try:
            scopes = ['https://www.googleapis.com/auth/drive']
            creds = service_account.Credentials.from_service_account_file(sa_file, scopes=scopes)
            service = build('drive', 'v3', credentials=creds, cache_discovery=False)

            q = f"'{folder_id}' in parents"
            resp = service.files().list(q=q, fields='files(id,name,mimeType,webViewLink,webContentLink)').execute()
            items = resp.get('files', [])

            article_text = ''
            aml_files = {}
            images = []

            for it in items:
                name = it.get('name')
                mime = it.get('mimeType')
                fid = it.get('id')
                if name and name.lower().startswith('article') and mime == 'application/vnd.google-apps.document':
                    try:
                        exported_txt = service.files().export(fileId=fid, mimeType='text/plain').execute()
                        plain = exported_txt.decode('utf-8') if isinstance(exported_txt, bytes) else exported_txt
                        # article_text = plain
                        parsed = None
                        if archieml:
                            try:
                                parsed = archieml.loads(plain)
                            except Exception:
                                parsed = None
                        if not parsed or not isinstance(parsed, dict) or 'content' not in parsed:
                            parsed = _parse_aml_plain_text(plain).get('article.aml')
                        aml_files['article.aml'] = parsed
                        article_text = _parse_plain_text_preview(plain)
                    except Exception:
                        article_text = ''
                elif name and name.lower().endswith('.aml'):
                    try:
                        media = service.files().get_media(fileId=fid).execute()
                        txt = media.decode('utf-8') if isinstance(media, bytes) else media
                        if archieml:
                            try:
                                parsed = archieml.loads(txt)
                                aml_files[name] = parsed
                            except Exception:
                                aml_files[name] = txt
                        else:
                            aml_files[name] = txt
                    except Exception:
                        aml_files[name] = ''
                elif mime and mime.startswith('image'):
                    images.append({'name': name, 'url': it.get('webContentLink') or it.get('webViewLink') or ''})

            return JsonResponse({'slug': pkg.slug, 'article': article_text, 'aml_files': aml_files, 'data': aml_files, 'images': images})
        except Exception:
            pass

    sample = _read_local_sample(slug)
    if sample['article']:
        return JsonResponse({'slug': pkg.slug, 'article': sample['article'], 'aml_files': sample['aml_files'], 'data': sample['aml_files'], 'images': sample['images']})

    return JsonResponse({'error': 'Unable to fetch package content from Drive and no local sample available.'}, status=500)