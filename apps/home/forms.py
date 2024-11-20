from django import forms
from .models import CsvData

class CsvUploadForm(forms.Form):
    csv_file = forms.FileField(label='Select a CSV file')
