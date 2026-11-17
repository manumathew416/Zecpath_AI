"""Day 14 - job filters.  Example:  /api/jobs/?location=kochi&experience_to=2&posted_after=2026-11-01"""
import django_filters

from apps.core.filters import DateAfterFilter, DateBeforeFilter, RangeCheckedFilterSet

from .models import Job


class JobFilter(RangeCheckedFilterSet):
    location = django_filters.CharFilter(lookup_expr="icontains")
    company = django_filters.CharFilter(field_name="employer__company_name", lookup_expr="icontains")
    experience_from = django_filters.NumberFilter(field_name="min_experience", lookup_expr="gte")
    experience_to = django_filters.NumberFilter(field_name="min_experience", lookup_expr="lte")
    posted_after = DateAfterFilter(field_name="posted_at")
    posted_before = DateBeforeFilter(field_name="posted_at")

    range_pairs = [("experience_from", "experience_to"), ("posted_after", "posted_before")]

    class Meta:
        model = Job
        fields = []


class EmployerJobFilter(JobFilter):
    """Employers also see closed jobs, so they can filter by status."""
    status = django_filters.ChoiceFilter(choices=Job.Status.choices)

    class Meta(JobFilter.Meta):
        fields = ["status"]
