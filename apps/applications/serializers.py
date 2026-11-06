from rest_framework import serializers

from .models import Application


class ApplicationSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)

    class Meta:
        model = Application
        fields = ["id", "job", "job_title", "candidate", "status", "ats_score", "applied_at"]
        read_only_fields = ["id", "candidate", "status", "ats_score", "applied_at"]


class ApplicationStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ["status"]
