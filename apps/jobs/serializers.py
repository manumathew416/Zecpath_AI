from rest_framework import serializers

from .models import Job


class JobSerializer(serializers.ModelSerializer):
    # Day 14: the company name is shown in every list row. The views use
    # select_related("employer"), so this adds NO extra query per row.
    company_name = serializers.CharField(source="employer.company_name", read_only=True)

    class Meta:
        model = Job
        fields = ["id", "employer", "company_name", "title", "description", "location",
                  "skills_required", "min_experience", "status", "posted_at"]
        # employer is taken from the logged-in user, never from the request body
        read_only_fields = ["id", "employer", "posted_at"]


class EmployerJobSerializer(JobSerializer):
    """Employer's own list: also shows how many people applied.

    `applications_count` is computed by the database in the SAME query
    (annotate), instead of one COUNT query per job.
    """
    applications_count = serializers.IntegerField(read_only=True)

    class Meta(JobSerializer.Meta):
        fields = JobSerializer.Meta.fields + ["applications_count"]
