from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Print stored GoogleCredential records for debugging'

    def handle(self, *args, **options):
        from core.models import GoogleCredential
        qs = GoogleCredential.objects.all()
        if not qs:
            self.stdout.write('No GoogleCredential records found')
            return
        for g in qs:
            has_refresh = bool(g.refresh_token)
            expires = g.expires_at.isoformat() if g.expires_at else 'unknown'
            self.stdout.write(f'user={g.user.username} refresh={has_refresh} expires_at={expires}')