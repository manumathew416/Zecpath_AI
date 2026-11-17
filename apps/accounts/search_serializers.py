from rest_framework import serializers

from .models import Candidate


class CandidateSearchSerializer(serializers.ModelSerializer):
    """What an employer may see in search results.

    Deliberately NOT included: email, phone, salary, resume. Those stay private
    until the candidate applies to that employer's job.
    """

    class Meta:
        model = Candidate
        fields = ["id", "location", "skills", "education", "experience_years", "updated_at"]
        read_only_fields = fields
