from django import forms
from .models import Package


class PackageForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = ['slug', 'description', 'google_drive_url', 'publish_date', 'category']
