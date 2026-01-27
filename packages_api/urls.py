from django.urls import path
from packages_api import api_views

urlpatterns = [
    path('packages/<str:pset_slug>', api_views.list_packages_from_pset, name='list_packages_from_pset'),
    path('packages/<str:pset_slug>/<str:id>', api_views.show_one, name='get'),
]