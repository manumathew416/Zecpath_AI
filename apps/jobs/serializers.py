from rest_framework import serializers

from .models import Job


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ["id", "employer", "title", "description", "location",
                  "skills_required", "min_experience", "status", "posted_at"]
        read_only_fields = ["id", "employer", "posted_at"]