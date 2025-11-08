from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
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

    page_obj, visible_page_range = paginate_package_list(request, packages)

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
        'packages': page_obj,
        'visible_page_range': visible_page_range,
        'form': form,
        'categories': categories,
        'active_category': category or '',
    })

def paginate_package_list(request, queryset, items_per_page=10, pages_in_block=3):
    paginator = Paginator(queryset, items_per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    start_page = page_obj.number
    end_page = min(paginator.num_pages, start_page + pages_in_block - 1)
    if end_page == paginator.num_pages:
        start_page = max(1, end_page - pages_in_block + 1)

    visible_page_range = list(range(start_page, end_page + 1))
    return page_obj, visible_page_range

@login_required
def package_create(request):
    return redirect('packages_list')

""" This new function will flatten the stored image in google drive into a simple list for templates """
def _format_images(images_data):

    """ Convert stored images data into a flat list of images with name and URL for templates.
    Deduplicates images by filename, prioritizing GridFS URLs over Drive URLs. """
    if not images_data:
        return []

    # Build a map by filename to deduplicate
    images_by_name = {}

    if isinstance(images_data, dict):
        # First add GridFS images (preferred)
        for item in images_data.get('gridfs', []) or []:
            file_id = item.get('id')
            if file_id:
                name = item.get('name')
                images_by_name[name] = {
                    'name': name,
                    'url': f"/files/{file_id}/",
                    'source': 'gridfs'
                }

        # Then add Drive images only if not already in GridFS
        for item in images_data.get('gdrive', []) or []:
            name = item.get('name')
            if name not in images_by_name:
                images_by_name[name] = {
                    'name': name,
                    'url': item.get('url'),
                    'source': 'gdrive'
                }
    elif isinstance(images_data, list):
        # If it's already a list, return as-is
        return images_data

    return list(images_by_name.values())


def package_detail(request, slug):
    try:
        pkg = Package.objects.get(slug=slug)
    except Package.DoesNotExist:
        return HttpResponseNotFound('Package not found')

    """ This part below will persist the cached data for the template to use directly
        
    Send the cached data so the template can preload without extra fetches 
    
    Also check the package_fetch function below to get the idea """
    initial_payload = {
        'slug': pkg.slug,
        'article': pkg.cached_article_preview or '',
        'aml_files': pkg.data or {},
        'data': pkg.data or {},
        'images': _format_images(pkg.images),
    }

    return render(request, 'packages/package_view.html', {
        'package': pkg,
        'initial_payload': initial_payload, # initial_payload will check for cached fields in the slug
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
    
    """ Pull the latest files from Drive, so the model persists the results for reuse """
    try:
        pkg.fetch_from_gdrive(request.user)
        pkg.refresh_from_db()
    except Exception:
        sample = _read_local_sample(slug)
        if sample['article']:
            return JsonResponse({
                'slug': pkg.slug,
                'article': sample['article'],
                'aml_files': sample['aml_files'],
                'data': sample['aml_files'],
                'images': sample['images'],
            })
        return JsonResponse({'error': 'Unable to fetch package content.'}, status=500)

    return JsonResponse({
        'slug': pkg.slug,
        'article': pkg.cached_article_preview or '',
        'aml_files': pkg.data or {},
        'data': pkg.data or {},
        'images': _format_images(pkg.images),
    })
