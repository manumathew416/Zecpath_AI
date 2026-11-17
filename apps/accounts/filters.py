"""Day 14 - filters for the admin user list, the admin profile lists and the
employer's candidate search."""
import django_filters

from apps.core.filters import DateAfterFilter, DateBeforeFilter, RangeCheckedFilterSet

from .models import Candidate, Employer, Role, User


class UserFilter(RangeCheckedFilterSet):
    """Filter by role, state and signup date:  /api/admin/users/?role=employer&joined_after=2026-11-01"""
    role = django_filters.ChoiceFilter(choices=Role.choices)
    is_active = django_filters.BooleanFilter()
    is_verified = django_filters.BooleanFilter()
    joined_after = DateAfterFilter(field_name="created_at")
    joined_before = DateBeforeFilter(field_name="created_at")

    range_pairs = [("joined_after", "joined_before")]

    class Meta:
        model = User
        fields = ["role", "is_active", "is_verified"]


class CandidateFilter(RangeCheckedFilterSet):
    location = django_filters.CharFilter(lookup_expr="icontains")
    experience_from = django_filters.NumberFilter(field_name="experience_years", lookup_expr="gte")
    experience_to = django_filters.NumberFilter(field_name="experience_years", lookup_expr="lte")
    joined_after = DateAfterFilter(field_name="created_at")
    joined_before = DateBeforeFilter(field_name="created_at")

    range_pairs = [("experience_from", "experience_to"), ("joined_after", "joined_before")]

    class Meta:
        model = Candidate
        fields = []


class EmployerFilter(RangeCheckedFilterSet):
    industry = django_filters.CharFilter(lookup_expr="icontains")
    location = django_filters.CharFilter(lookup_expr="icontains")
    company_size = django_filters.ChoiceFilter(choices=Employer.CompanySize.choices)
    is_verified = django_filters.BooleanFilter()
    joined_after = DateAfterFilter(field_name="created_at")
    joined_before = DateBeforeFilter(field_name="created_at")

    range_pairs = [("joined_after", "joined_before")]

    class Meta:
        model = Employer
        fields = ["company_size", "is_verified"]
