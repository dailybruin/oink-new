from django import forms
from .models import Package


class PackageForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = ['slug', 'description', 'google_drive_url', 'publish_date', 'category']
        widgets = {
             'description': forms.TextInput(attrs={
                 'class': 'custom-input',
                 'placeholder': 'Brief description',
                 'style':'width: 100%;',
                 'rows': 3,
             }),
             'slug': forms.TextInput(attrs={
                 'class': 'custom-input',
                 'placeholder': 'Slug (e.g. sports.mbb.oregon)',
                 'style':'width: 100%;',
             }),
             'google_drive_url': forms.TextInput(attrs={
                 'class': 'custom-input',
                 'placeholder': 'Google Drive URL',
                 'style':'width: 100%;',
             }),
            'publish_date': forms.DateInput(attrs={
                 'class': 'custom-input',
                'type': 'date',
                'style':'width: 100%;'
             }),
             
        }