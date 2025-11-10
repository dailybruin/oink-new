from django.urls import path
from . import views
from . import package_views

urlpatterns = [
    path('', views.index, name='index'),
    path('google/login/', views.google_login, name='google_login'),
    path('google/callback/', views.google_callback, name='google_callback'),
    path('signout/', views.signout, name='signout'),
    path('packages/', package_views.packages_list, name='packages_list'),
    path('packages/new/', package_views.package_create, name='package_create'),
    path('packages/<slug:slug>/', package_views.package_detail, name='package_detail'),
    path('packages/<slug:slug>/fetch/', package_views.package_fetch, name='package_fetch'),
    path('packages/<slug:slug>/image/<str:file_id>/', package_views.package_image, name='package_image'),
    
    # Serve files connected and stored in MongoDB GridFS
    path('files/<str:file_id>/', views.serve_gridfs_file, name='serve_gridfs_file'),
]
