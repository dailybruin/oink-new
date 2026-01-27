import json
from packages.models import Package
from django.forms.models import model_to_dict
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def list_packages_from_pset(request: HttpRequest, pset_slug: str) -> JsonResponse:
    package_list = (
        Package.objects.filter(category=pset_slug)
        .order_by('-publish_date')
        .all()
    )
    
    results = [model_to_dict(model) for model in package_list]
    return JsonResponse({'data': results})

@require_GET
def show_one(request: HttpRequest, pset_slug: str, id: str) -> JsonResponse:
    package = Package.objects.get(category=pset_slug, slug=id)
    return JsonResponse(model_to_dict(package))