# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django import template
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.urls import reverse
import csv
import io
import os
from django.shortcuts import render
from django.contrib import messages
from django.db.models import Count, Max
from django.utils import timezone
import pandas as pd
import plotly.express as px
import plotly.io as pio
from .forms import CsvUploadForm
from .models import CsvData, MessageType
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .forms import CsvUploadForm 



@login_required(login_url="/login/")
def index(request):
    context = {'segment': 'index'}
    return render(request, 'home/index.html', context)


@login_required(login_url="/login/")
def dynamic_view(request):
    load_template = request.path.split('/')[-1]
    context = {'segment': load_template}

    # Custom logic for specific pages
    if load_template == 'upload.html':
        return upload_and_classify(request, context)
    elif load_template in ['international.html', 'national.html']:
        return display_file_charts(request, load_template)

    try:
        # Redirect to admin if path is /admin
        if load_template == 'admin':
            return HttpResponseRedirect(reverse('admin:index'))

        html_template = loader.get_template('home/' + load_template)
        return HttpResponse(html_template.render(context, request))

    except template.TemplateDoesNotExist:
        html_template = loader.get_template('home/page-404.html')
        return HttpResponse(html_template.render(context, request))

    except Exception:
        html_template = loader.get_template('home/page-500.html')
        return HttpResponse(html_template.render(context, request))


@login_required(login_url="/login/")
def upload_and_classify(request):
    if request.method == 'POST':
        form = CsvUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'This is not a CSV file')
                return render(request, 'upload_csv.html', {'form': form})

            file_name = csv_file.name
            uploaded_at = timezone.now()
            data_set = csv_file.read().decode('UTF-8')
            io_string = io.StringIO(data_set)
            next(io_string)  # Skip header row
            
            type_tickets = set()
            for column in csv.reader(io_string, delimiter=';', quotechar='"'):
                if len(column) == 14:
                    CsvData.objects.update_or_create(
                        file_name=file_name,
                        uploaded_at=uploaded_at,
                        type_ticket=column[0],
                        type_message=column[1],
                        error=column[2],
                        msg_ref=column[3],
                        Routing_domain=column[4],
                        Peer_in=column[5],
                        Peer_out=column[6],
                        timestamp=column[7],
                        calling_party=column[8],
                        called_party=column[9],
                        oa=column[10],
                        da=column[11],
                        IMSI=column[12],
                        server=column[13],
                    )
                    type_tickets.add(column[0])
                else:
                    messages.error(request, f"Skipping malformed row: {column}")

            type_tickets = [ticket.strip().upper() for ticket in type_tickets]

            if "SMS_SUBMIT" in type_tickets and "SMS_DELIVER" in type_tickets:
                file_type = "international"
            elif "SMS_SUBMIT" in type_tickets:
                file_type = "national"
            else:
                file_type = "unknown"

            base_name = os.path.basename(file_name)
            supplement_name = base_name[29:].split('.')[0] if len(base_name) >= 29 else 'Unknown'

            MessageType.objects.create(
                name=supplement_name,
                nom_fichier=file_name,
                type=file_type,
                uploaded_at=uploaded_at
            )
            
            messages.success(request, f'File "{file_name}" uploaded, classified as {file_type}, and supplement name "{supplement_name}" saved.')

    else:
        form = CsvUploadForm()

    return render(request, 'home/upload.html', {'form': form})

def icons(request):
    return render(request, 'home/typography.html')


def display_file_charts(request, file_type):
    # Select files based on the type (national or international)
    selected_files = MessageType.objects.filter(type=file_type)

    charts = []
    for file in selected_files:
        # Query the CsvData model for the file's OA counts
        oa_counts = CsvData.objects.filter(file_name=file.nom_fichier).values('oa').annotate(count=Count('oa')).order_by('-count')
        
        # Count the occurrences of SMS_SUBMIT and SMS_DELIVER for this file
        sms_submit_count = CsvData.objects.filter(file_name=file.nom_fichier, type_ticket__icontains='SMS_SUBMIT').count()
        sms_deliver_count = CsvData.objects.filter(file_name=file.nom_fichier, type_ticket__icontains='SMS_DELIVER').count()

        # Retrieve the corresponding supplement name from the Type model
        try:
            type_instance = MessageType.objects.get(nom_fichier=file.nom_fichier)
            supplement_name = type_instance.name
        except MessageType.DoesNotExist:
            supplement_name = 'Unknown'

        # Create Plotly bar chart for OA counts
        fig = px.bar(
            x=[oa['oa'] for oa in oa_counts],
            y=[oa['count'] for oa in oa_counts],
            labels={'x': 'Origin app (OA)', 'y': 'Count'},
            title=f"OA Number Counts for {supplement_name}"
        )
        
        # Add counts for SMS_SUBMIT and SMS_DELIVER as another bar chart
        sms_counts_fig = px.bar(
            x=['SMS_SUBMIT', 'SMS_DELIVER'],
            y=[sms_submit_count, sms_deliver_count],
            labels={'x': 'Message Type', 'y': 'Count'},
            title=f"Message Type Counts for {supplement_name}"
        )
        
        # Convert the Plotly chart to HTML
        chart_html = pio.to_html(fig, full_html=False)
        sms_chart_html = pio.to_html(sms_counts_fig, full_html=False)

        # Store the charts for this file
        charts.append({
            'file_name': file.nom_fichier,
            'oa_chart': chart_html,
            'sms_chart': sms_chart_html,
            'supplement_name': supplement_name,
        })

    return render(request, 'home/file_charts.html', {'charts': charts, 'file_type': file_type})

def combined_view(request):
    # Handle file upload
    if request.method == 'POST' and 'upload' in request.POST:
        form = CsvUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'This is not a CSV file')
            else:
                file_name = csv_file.name
                uploaded_at = timezone.now()
                data_set = csv_file.read().decode('UTF-8')
                io_string = io.StringIO(data_set)
                next(io_string) 
                for column in csv.reader(io_string, delimiter=';', quotechar='"'):
                    if len(column) == 14:  
                        CsvData.objects.update_or_create(
                            file_name=file_name,
                            uploaded_at=uploaded_at,
                            type_ticket=column[0],
                            type_message=column[1],
                            error=column[2],
                            msg_ref=column[3],
                            Routing_domain=column[4],
                            Peer_in=column[5],
                            Peer_out=column[6],
                            timestamp=column[7],
                            calling_party=column[8],
                            called_party=column[9],
                            oa=column[10],
                            da=column[11],
                            IMSI=column[12],
                            server=column[13],
                        )
                    else:
                        messages.error(request, f"Skipping malformed row: {column}")
                messages.success(request, 'File uploaded successfully')
    else:
        form = CsvUploadForm()

    # Handle distinct OA counts
    oa_counts = CsvData.objects.values('oa').annotate(count=Count('oa')).order_by('-count')
    oa_count = oa_counts.count()

    # Handle file list
    query = request.GET.get('q', '')
    files = CsvData.objects.filter(file_name__icontains=query).values('file_name').annotate(
        uploaded_at=Max('uploaded_at')
    )

    # Handle view file data
    file_name = request.GET.get('file_name', '')
    data = CsvData.objects.filter(file_name=file_name) if file_name else None
    
    # Monthly OA Chart logic
    month_query = request.GET.get('month', None)
    chart = None  # Initialize chart as None

    if month_query:
        filtered_data = CsvData.objects.filter(uploaded_at__month=month_query)
        monthly_data = (
            filtered_data
            .values('oa', 'uploaded_at__month')
            .annotate(count=Count('oa'))
            .order_by('uploaded_at__month')
        )

        # Convert to DataFrame
        df = pd.DataFrame.from_records(monthly_data)

        if not df.empty:
            # Generate the Plotly chart for the monthly OA counts
            fig = px.bar(df, x='oa', y='count', color='uploaded_at__month', labels={'x': 'OA', 'y': 'Count'})
            chart = pio.to_html(fig, full_html=False)
        else:
            chart = "No data available for the selected month."

    # Date-specific statistics
    date = request.GET.get('date', None)
    date_stats = dictionnaire(request, date) if date else None

    context = {
        'form': form,
        'oa_count': oa_count,
        'oa_counts': oa_counts,
        'files': files,
        'data': data,
        'chart': chart,  # Now only the monthly chart will be shown
        'file_name': file_name,
        'date_stats': date_stats,
        'month_query': month_query,  # Pass month for display in template
    }

    return render(request, 'home/home2.html', context)
 


def upload(request):
    if request.method == 'POST':
        form = CsvUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'This is not a CSV file')
                return render(request, 'upload_csv.html', {'form': form})
            
            
            file_name = csv_file.name
            uploaded_at = timezone.now()
            data_set = csv_file.read().decode('UTF-8')
            io_string = io.StringIO(data_set)
            next(io_string)  # Skip the header row
            for column in csv.reader(io_string, delimiter=';', quotechar='"'):
                if len(column) == 14:  # Ensure there are 14 columns
                    CsvData.objects.update_or_create(
                        file_name=file_name,
                        uploaded_at=uploaded_at,
                        type_ticket=column[0],
                        type_message=column[1],
                        error=column[2],
                        msg_ref=column[3],
                        Routing_domain=column[4],
                        Peer_in=column[5],
                        Peer_out=column[6],
                        timestamp=column[7],
                        calling_party=column[8],
                        called_party=column[9],
                        oa=column[10],
                        da=column[11],
                        IMSI=column[12],
                        server=column[13],

                    )
                else:
                    messages.error(request, f"Skipping malformed row: {column}")
                    print(f"Skipping malformed row: {column}")
            messages.success(request, 'File uploaded successfully')
    else:
        form = CsvUploadForm()
    return render(request, 'Uploadcsv.html', {'form': form})

def admin(request):
    
    # Handle file list
    query = request.GET.get('q', '')
    files = CsvData.objects.filter(file_name__icontains=query).values('file_name').annotate(
        uploaded_at=Max('uploaded_at')
    )

    # Handle view file data
    file_name = request.GET.get('file_name', '')
    data = CsvData.objects.filter(file_name=file_name) if file_name else None

    context = {
        'files': files,
        'data': data,
        'file_name': file_name,
       
    }

    return render(request, 'admin.html',context)


def distinct_da(request):
    # Get distinct OA counts
    oa_counts = CsvData.objects.values('oa').annotate(count=Count('oa')).order_by('-count')
    oa_count = oa_counts.count()

    # Prepare data for Plotly
    oa_numbers = [oa['oa'] for oa in oa_counts]
    counts = [oa['count'] for oa in oa_counts]

    # Create Plotly bar chart
    fig = px.bar(x=oa_numbers, y=counts, labels={'x': 'Origin app', 'y': 'Count'}, title="OA Number Counts")

    # Convert Plotly figure to JSON for rendering in the template
    chart = pio.to_html(fig, full_html=False)

    context = {
        'oa_count': oa_count,
        'oa_counts': oa_counts,
        'chart': chart,  # Pass the chart to the template
    }

    return render(request, 'combined_template.html', context)


def file_list(request):
    query = request.GET.get('q', '')
    files = CsvData.objects.filter(file_name__icontains=query).values('file_name').annotate(uploaded_at=Max('uploaded_at'))
    return render(request, 'file_list.html', {'files': files})

def view_file_data(request, file_name):
    data = CsvData.objects.filter(file_name=file_name)
    return render(request, 'file_data.html', {'data': data, 'file_name': file_name})


def dictionnaire(request, date):
    try:
        # Parse the date string to a datetime object
        date = timezone.make_aware(timezone.datetime.strptime(date, '%Y-%m-%d'))
    except ValueError:
        messages.error(request, 'Invalid date format. Please use YYYY-MM-DD.')
        return render(request, 'combined_template.html')

    # Filter the data by the given date
    oa_data = CsvData.objects.filter(uploaded_at__date=date).values('oa').annotate(count=Count('oa')).order_by('-count')
    dict_count = oa_data.count()

    context = {
        'dict_oa': oa_data,
        'dict_count': dict_count,
        'selected_date': date
    }

    return context  


def monthly_oa_chart(request):
    # Get the month filter from the request
    month_query = request.GET.get('month', None)
    
    # Filter by the selected month if provided
    if month_query:
        filtered_data = CsvData.objects.filter(uploaded_at__month=month_query)
    else:
        filtered_data = CsvData.objects.all()

    # Annotate the data to get distinct oa counts by month
    monthly_data = (
        filtered_data
        .values('oa', 'uploaded_at__month')
        .annotate(count=Count('oa'))
        .order_by('uploaded_at__month')
    )

    # Convert to DataFrame
    df = pd.DataFrame.from_records(monthly_data)

    # Check if df is not empty
    if not df.empty:
        # Generate the Plotly chart
        fig = px.bar(df, x='oa', y='count', color='uploaded_at__month', labels={'x': 'OA', 'y': 'Count'})
        chart = pio.to_html(fig, full_html=False)
    else:
        chart = "No data available for the selected month."

    context = {
        'chart': chart,
        'month_query': month_query,  # Pass the current month filter to the template
    }

    return render(request, 'monthly_oa_chart.html', context)