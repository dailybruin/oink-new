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
                 'style':'width: 450px;',
                 'rows': 3,
             }),
             'slug': forms.TextInput(attrs={
                 'placeholder': 'Slug (e.g. sports.mbb.oregon)',
                 'style':'width: 450px;',
             }),
             'google_drive_url': forms.TextInput(attrs={
                 'placeholder': 'Google Drive URL',
                 'style':'width: 450px;',
             }),
            'publish_date': forms.DateInput(attrs={
                'type': 'date',
                'style':'width: 450px;'
             }),
             
        }