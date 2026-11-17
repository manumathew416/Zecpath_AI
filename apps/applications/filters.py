"""Day 14 - application filters.  Example:  ?status=shortlisted&min_score=60&applied_after=2026-11-01"""
import django_filters

from apps.core.filters import DateAfterFilter, DateBeforeFilter, RangeCheckedFilterSet

from .models import Application


class ApplicationFilter(RangeCheckedFilterSet):
    status = django_filters.ChoiceFilter(choices=Application.Status.choices)
    min_score = django_filters.NumberFilter(field_name="ats_score", lookup_expr="gte")
    max_score = django_filters.NumberFilter(field_name="ats_score", lookup_expr="lte")
    applied_after = DateAfterFilter(field_name="applied_at")
    applied_before = DateBeforeFilter(field_name="applied_at")

    range_pairs = [("min_score", "max_score"), ("applied_after", "applied_before")]

    class Meta:
        model = Application
        fields = ["status"]
