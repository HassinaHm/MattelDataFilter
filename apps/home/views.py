# -*- encoding: utf-8 -*-
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
from django.shortcuts import render
from elasticsearch.helpers import bulk
from elasticsearch import Elasticsearch, helpers
from datetime import datetime
import uuid
import logging
from elasticsearch_dsl import Search

from django.shortcuts import render
from .search import DataInterIndex

# Configure logging to capture debug messages
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


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
    file_name = None 
    io_string = None  

    if request.method == 'POST':
        form = CsvUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'This is not a CSV file')
                return render(request, 'upload_csv.html', {'form': form})

            # Prepare metadata
            file_id = str(uuid.uuid4())
            file_name = csv_file.name
            uploaded_at = datetime.now().isoformat()
            base_name = os.path.basename(file_name)
            supplement_name = base_name[29:].split('.')[0] if len(base_name) >= 29 else 'Unknown'

            # Elasticsearch connection
            es = Elasticsearch(
                ["https://localhost:9200"],
                ca_certs="C:/Users/HP/Desktop/Elasticsearch/elasticsearch-8.17.0/config/certs/http_ca.crt",  # Path to CA certificate
                basic_auth=("elastic", "Fv*hf7yk*pIPr1D9U_4B"),  # Replace with your username and password
                timeout=120,
                max_retries=5,
                retry_on_timeout=True
            )

            # Read CSV and prepare batches
            data_set = csv_file.read().decode('UTF-8')
            io_string = io.StringIO(data_set)
            next(io_string)  # Skip header row

            batch_size = 100  # Process 100 rows at a time
            rows = []

            try:
                # Process each row in the CSV
                for column in csv.reader(io_string, delimiter=';', quotechar='"'):
                    if len(column) == 14:  # Check if row has all columns
                        # Build the document for Elasticsearch
                        row = {
                            "_index": "data_mattel",  # Replace with your index name
                            "_source": {
                                "file_id": file_id,
                                "uploaded_at": uploaded_at,
                                "type": "international" if "SMS_DELIVER" in column[0] else "national",
                                "supplement_name": supplement_name,
                                "type_ticket": column[0],
                                "type_message": column[1],
                                "error": column[2] if column[2] else "UNKNOWN",  # Handle null/empty values
                                "msg_ref": column[3] if column[3] else "UNKNOWN",
                                "Routing_domain": column[4] if column[4] else "UNKNOWN",
                                "Peer_in": column[5] if column[5] else "UNKNOWN",
                                "Peer_out": column[6] if column[6] else "UNKNOWN",
                                "timestamp": column[7],
                                "calling_party": column[8] if column[8] else "UNKNOWN",
                                "called_party": column[9] if column[9] else "UNKNOWN",
                                "oa": column[10] if column[10] else "UNKNOWN",
                                "da": int(column[11]),  # Ensure da is integer
                                "IMSI": column[12] if column[12] else "UNKNOWN",
                                "server": column[13] if column[13] else "UNKNOWN"
                            }
                        }
                        rows.append(row)

                    else:
                        messages.error(request, f"Skipping malformed row: {column}")
                        logger.warning(f"Skipping malformed row: {column}")  # Debugging: log skipped rows

                    # Upload batch to Elasticsearch
                    if len(rows) >= batch_size:
                        # Log the batch before uploading
                        logger.debug(f"Uploading batch of size {len(rows)}: {rows}")
                        try:
                            # Perform bulk upload
                            response = helpers.bulk(es, rows)
                            logger.info(f"Successfully uploaded {len(rows)} rows")
                            rows = []  # Reset batch after uploading
                        except Exception as upload_error:
                            logger.error(f"Error uploading batch: {upload_error}")  # Log error
                            messages.error(request, f"Error uploading batch: {upload_error}")
                            break  # Stop processing if error occurs

                # Upload remaining rows
                if rows:
                    try:
                        logger.debug(f"Uploading remaining rows: {rows}")
                        response = helpers.bulk(es, rows)
                        logger.info(f"Successfully uploaded remaining {len(rows)} rows")
                    except Exception as upload_error:
                        logger.error(f"Error uploading remaining rows: {upload_error}")
                        messages.error(request, f"Error uploading remaining rows: {upload_error}")

                # If everything succeeded, show success message
                messages.success(request, f'File "{file_name}" uploaded successfully!')

            except Exception as e:
                logger.error(f'Unexpected error: {str(e)}')  # Log unexpected errors
                messages.error(request, f'Error uploading file "{file_name}". Unexpected error: {str(e)}')

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


#  ELASTIC PART 
def combined_view(request):
    search = DataInterIndex.search()

    # Aggregation for distinct OA counts
    search.aggs.bucket('oa_counts', 'terms', field='oa', size=1000)

    # Execute the query
    response = search.execute()

    # Process results
    oa_counts = response.aggregations.oa_counts.buckets
    oa_numbers = [bucket.key for bucket in oa_counts]
    counts = [bucket.doc_count for bucket in oa_counts]

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
        'oa_count': len(oa_numbers),
        'oa_counts': zip(oa_numbers, counts),
        'files': files,
        'data': data,
        'chart': chart,  # Now only the monthly chart will be shown
        'file_name': file_name,
        'date_stats': date_stats,
        'month_query': month_query,  # Pass month for display in template
    }

    return render(request, 'home/home2.html', context)
 
def file_type(request, file_type):
    search = DataInterIndex.search()

    # Step 1: Filter documents by the given file type
    search = Search(index="data_mattel-ma").using('default')
    search = search.filter('term', file_type__keyword=file_type)
    search = search.params(size=10000)  # Retrieve all matching documents

    # Step 2: Execute the search and fetch results
    response = search.execute()

    # Debug: Print raw response from Elasticsearch
    print("Elasticsearch Response:", response.to_dict())

    # Step 3: Process `oa` counts per matching document
    oa_counts = {}
    for hit in response.hits:
        # Safely retrieve the `oa` value from the document
        oa_value = getattr(hit, 'oa', None)
        if oa_value:
            oa_counts[oa_value] = oa_counts.get(oa_value, 0) + 1

    # Debug: Print the aggregated `oa_counts`
    print("OA Counts:", oa_counts)

    # Step 4: Prepare data for the template
    oa_counts_list = [{"oa": key, "count": value} for key, value in oa_counts.items()]
    file_type_data = {"file_type": file_type, "oa_counts": oa_counts_list}

    # Debug: Print the final data sent to the template
    print("Data for Template:", file_type_data)

    # Step 5: Render the template with the results
    return render(request, 'home/file_charts.html', {"file_type_data": [file_type_data]})


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
    # Query Elasticsearch using the DataInterIndex class
    search = DataInterIndex.search()

    # Aggregation for distinct OA counts
    search.aggs.bucket('oa_counts', 'terms', field='oa', size=1000)

    # Execute the query
    response = search.execute()

    # Process results
    oa_counts = response.aggregations.oa_counts.buckets
    oa_numbers = [bucket.key for bucket in oa_counts]
    counts = [bucket.doc_count for bucket in oa_counts]

    context = {
        'oa_count': len(oa_numbers),
        'oa_counts': zip(oa_numbers, counts),
    }

    return render(request, 'home/home2.html', context)

# def distinct_da(request):
#     # Get distinct OA counts
#     oa_counts = CsvData.objects.values('oa').annotate(count=Count('oa')).order_by('-count')
#     oa_count = oa_counts.count()

#     # Prepare data for Plotly
#     oa_numbers = [oa['oa'] for oa in oa_counts]
#     counts = [oa['count'] for oa in oa_counts]

#     # Create Plotly bar chart
#     fig = px.bar(x=oa_numbers, y=counts, labels={'x': 'Origin app', 'y': 'Count'}, title="OA Number Counts")

#     # Convert Plotly figure to JSON for rendering in the template
#     chart = pio.to_html(fig, full_html=False)

#     context = {
#         'oa_count': oa_count,
#         'oa_counts': oa_counts,
#         'chart': chart,  # Pass the chart to the template
#     }

#     return render(request, 'combined_template.html', context)


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