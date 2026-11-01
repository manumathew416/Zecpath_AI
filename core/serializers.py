from rest_framework import serializers
from .models import Job, Employer


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ['id', 'employer', 'title', 'description', 'location',
                  'skills_required', 'min_experience', 'status', 'posted_at']


class EmployerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employer
        fields = ['id', 'user', 'company_name', 'website',
                  'industry', 'location', 'is_verified', 'created_at']