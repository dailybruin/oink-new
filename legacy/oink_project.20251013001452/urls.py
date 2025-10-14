from django.contrib import admin
from django.urls import path, include

# Keep this file as a compatibility shim that points to the new `app` package.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
]
