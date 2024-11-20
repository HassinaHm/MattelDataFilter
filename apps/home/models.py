from django.db import models
from django.utils import timezone

class CsvData(models.Model):
    file_name = models.CharField(max_length=255, null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)
    type_ticket = models.CharField(max_length=255, null=True, blank=True)
    type_message = models.CharField(max_length=255, null=True, blank=True)
    error = models.CharField(max_length=255, null=True, blank=True)
    msg_ref = models.CharField(max_length=255, null=True, blank=True)
    Routing_domain = models.CharField(max_length=255, null=True, blank=True)
    Peer_in = models.CharField(max_length=255, null=True, blank=True)
    Peer_out = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.CharField(max_length=255, null=True, blank=True)
    calling_party = models.CharField(max_length=255, null=True, blank=True)
    called_party = models.CharField(max_length=255, null=True, blank=True)
    oa = models.CharField(max_length=255, null=True, blank=True)
    da = models.CharField(max_length=255, null=True, blank=True)
    IMSI = models.CharField(max_length=255, null=True, blank=True)
    server = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.file_name} - {self.uploaded_at}"

class OaStatistics(models.Model):
    oa_number = models.CharField(max_length=255)
    count = models.IntegerField()
    file_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.oa_number} - {self.count}"


class MessageType(models.Model):
    name = models.CharField(max_length=255, blank=True)
    nom_fichier = models.CharField(max_length=255)  
    type = models.CharField(max_length=255)  
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.nom_fichier} - {self.name} - {self.type}"
    




