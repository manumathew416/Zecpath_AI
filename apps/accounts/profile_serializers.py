from django.urls import reverse
from rest_framework import serializers

from . import validators
from .resume_utils import describe_resume
from .models import Candidate, Employer


class CandidateProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(read_only=True)     # comes from the account
    profile_complete = serializers.BooleanField(source="is_complete", read_only=True)
    resume = serializers.SerializerMethodField()

    def get_resume(self, obj):
        return describe_resume(obj, self.resume_url(obj))

    def resume_url(self, obj):
        return reverse("candidate-resume-download")

    class Meta:
        model = Candidate
        fields = ["id", "email", "phone", "location", "skills", "education",
                  "experience_years", "expected_salary", "resume", "profile_complete",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "skills": {"required": True, "allow_blank": False},
            "education": {"required": True, "allow_blank": False},
        }

    def validate_skills(self, value):
        return validators.clean_skills(value)

    def validate_experience_years(self, value):
        return validators.clean_experience(value)

    def validate_expected_salary(self, value):
        return validators.clean_expected_salary(value)


class EmployerProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    profile_complete = serializers.BooleanField(source="is_complete", read_only=True)

    class Meta:
        model = Employer
        fields = ["id", "email", "company_name", "domain", "company_size",
                  "website", "industry", "location", "is_verified",
                  "profile_complete", "created_at", "updated_at"]
        # an employer can never verify themselves; only an admin can
        read_only_fields = ["id", "is_verified", "created_at", "updated_at"]
        extra_kwargs = {
            "company_name": {"required": True, "allow_blank": False},
            "domain": {"required": True, "allow_blank": False},
        }

    def validate_company_name(self, value):
        return validators.clean_company_name(value)

    def validate_domain(self, value):
        return validators.clean_domain(value)

    def validate(self, attrs):
        website = attrs.get("website", getattr(self.instance, "website", ""))
        domain = attrs.get("domain", getattr(self.instance, "domain", ""))
        if website and domain and not validators.website_matches_domain(website, domain):
            raise serializers.ValidationError(
                {"website": "The website must belong to the company domain."})
        return attrs


# ---------- admin versions: same rules, plus lifecycle fields ----------

class AdminCandidateSerializer(CandidateProfileSerializer):
    def resume_url(self, obj):
        return reverse("admin-candidate-resume", args=[obj.pk])

    class Meta(CandidateProfileSerializer.Meta):
        fields = CandidateProfileSerializer.Meta.fields + ["is_deleted", "deleted_at"]
        read_only_fields = CandidateProfileSerializer.Meta.read_only_fields + [
            "is_deleted", "deleted_at"]
        # admin can fix a profile partially, so nothing is forced on PATCH
        extra_kwargs = CandidateProfileSerializer.Meta.extra_kwargs


class AdminEmployerSerializer(EmployerProfileSerializer):
    is_verified = serializers.BooleanField(required=False)   # admin may change it

    class Meta(EmployerProfileSerializer.Meta):
        fields = EmployerProfileSerializer.Meta.fields + ["is_deleted", "deleted_at"]
        read_only_fields = ["id", "created_at", "updated_at", "is_deleted", "deleted_at"]
        extra_kwargs = EmployerProfileSerializer.Meta.extra_kwargs

    def update(self, instance, validated_data):
        verified = validated_data.pop("is_verified", None)
        instance = super().update(instance, validated_data)
        if verified is not None:
            # the User flag is the source of truth, and the signal copies it
            # to the profile. Saving the user keeps the two in step.
            instance.user.is_verified = verified
            instance.user.save(update_fields=["is_verified"])
            instance.refresh_from_db()
        return instance
