from django.contrib import admin
from .models import Package
from django.contrib import messages
from . import drive


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('slug', 'category', 'publish_date', 'last_fetched_date', 'google_drive_url')
    search_fields = ('slug', 'description')
    list_filter = ('category',)
    actions = ['create_drive_folders']

    def create_drive_folders(self, request, queryset):
        created = 0
        errors = []
        
        drive_settings = {
            'service_account_file': getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', None),
            'impersonate_user': getattr(settings, 'GOOGLE_IMPERSONATE_USER', None),
            'share_public': getattr(settings, 'GOOGLE_SHARE_PUBLIC', False),
            'share_domain': getattr(settings, 'GOOGLE_SHARE_DOMAIN', None),
        }

        for pkg in queryset:
            try:
                result = drive.create_drive_folder(
                    pkg.slug, 
                    service_account_file=drive_settings['service_account_file'],
                    impersonate_user=drive_settings['impersonate_user'],
                    share_public=drive_settings['share_public'],
                    share_domain=drive_settings['share_domain']
                )
                if result and isinstance(result, dict):
                    pkg.google_drive_id = result.get('id', '')
                    pkg.google_drive_url = result.get('url', '')
                    pkg.save()
                    created += 1
                else:
                    errors.append(f"{pkg.slug}: creation failed")
            except Exception as e:
                errors.append(f"{pkg.slug}: {e}")

        msg = f"Drive folders created: {created}."
        if errors:
            msg += " Errors: " + "; ".join(errors[:5])
            self.message_user(request, msg, level=messages.WARNING)
        else:
            self.message_user(request, msg)

    create_drive_folders.short_description = 'Create Google Drive folder(s) for selected packages'
