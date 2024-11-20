# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path
from .views import index,upload_and_classify,combined_view,icons
from . import views

urlpatterns = [
    path('', index, name='home'), 
    path('files-types/<str:file_type>/', views.display_file_charts, name='files-types'),
    path('files-types/international/', views.display_file_charts, name='international'),
    path('files-types/national/', views.display_file_charts, name='national'), 
    path('monthly-oa-chart/', views.monthly_oa_chart, name='monthly_oa_chart'),

    path('upload/', upload_and_classify, name='upload'),  # Ensure this is correct
    path('home/', combined_view, name='home'),  # Ensure this is correct
    path('icons/', icons, name='icons'),  # Ensure this is correct

]

