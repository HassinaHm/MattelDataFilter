from elasticsearch_dsl import Document, Date, Integer, Keyword, Text, connections

# Connect to Elasticsearch
connections.create_connection(hosts=['https://localhost:9200'], http_auth=('elastic', 'Fv*hf7yk*pIPr1D9U_4B'))

class DataInterIndex(Document):
    type_ticket = Keyword()
    type_message = Keyword()
    oa = Keyword()
    da = Integer()
    IMSI = Keyword()
    calling_party = Keyword()
    uploaded_at = Date()
    column14 = Keyword()

    class Index:
        name = 'data_mattel-ma'  # Index name in Elasticsearch
