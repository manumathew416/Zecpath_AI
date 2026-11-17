from rest_framework import serializers

from .models import Application


class ApplicationSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job.title", read_only=True)
    company_name = serializers.CharField(source="job.employer.company_name", read_only=True)

    class Meta:
        model = Application
        fields = ["id", "job", "job_title", "company_name", "candidate", "status",
                  "ats_score", "applied_at"]
        read_only_fields = ["id", "candidate", "status", "ats_score", "applied_at"]


class ApplicantSerializer(serializers.ModelSerializer):
    """What an employer sees in the applicants list of their own job."""
    candidate_email = serializers.EmailField(source="candidate.user.email", read_only=True)
    candidate_skills = serializers.CharField(source="candidate.skills", read_only=True)
    candidate_experience_years = serializers.IntegerField(
        source="candidate.experience_years", read_only=True)
    candidate_location = serializers.CharField(source="candidate.location", read_only=True)

    class Meta:
        model = Application
        fields = ["id", "job", "candidate", "candidate_email", "candidate_skills",
                  "candidate_experience_years", "candidate_location", "status",
                  "ats_score", "applied_at"]
        read_only_fields = fields


class ApplicationStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ["status"]
