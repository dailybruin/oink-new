import json
from packages.models import Package
from packages.package_views import _strip_footnote_keys
from django.forms.models import model_to_dict
from django.http import HttpRequest, JsonResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET


def _package_to_dict(package):
    d = model_to_dict(package)
    if 'data' in d and d['data']:
        d['data'] = _strip_footnote_keys(d['data'])
    return d


@require_GET
def list_packages_from_pset(request: HttpRequest, pset_slug: str) -> JsonResponse:
    package_list = (
        Package.objects.filter(category=pset_slug)
        .order_by('-publish_date')
        .all()
    )
    results = [_package_to_dict(m) for m in package_list]
    return JsonResponse({'data': results})


@require_GET
def show_one(request: HttpRequest, pset_slug: str, id: str) -> JsonResponse:
    try:
        package = Package.objects.get(category=pset_slug, slug=id)
        return JsonResponse(_package_to_dict(package))
    except Package.DoesNotExist:
        return JsonResponse({'error': 'Package not found'}, status=404)