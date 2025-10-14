from django.contrib import admin
from .models import Package, GoogleCredential


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('slug', 'publish_date', 'category')
    search_fields = ('slug', 'description')


@admin.register(GoogleCredential)
class GoogleCredentialAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
