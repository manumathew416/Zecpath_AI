"""Day 14 - small building blocks shared by all filter sets.

Date filters work with whole days (YYYY-MM-DD) and are turned into a datetime
RANGE:

    posted_after=2026-11-01   ->  posted_at >= 2026-11-01 00:00
    posted_before=2026-11-10  ->  posted_at <  2026-11-11 00:00

A range keeps the index on the datetime column usable. The shortcut
`posted_at__date__gte` would run DATE(posted_at) on every row, and the
database could no longer use the index.
"""
from datetime import datetime, time, timedelta

import django_filters
from django.utils import timezone
from rest_framework.exceptions import ValidationError


def start_of_day(day):
    return timezone.make_aware(datetime.combine(day, time.min))


class DateAfterFilter(django_filters.DateFilter):
    """From the start of that day (inclusive)."""

    def filter(self, qs, value):
        if value is None:
            return qs
        return qs.filter(**{f"{self.field_name}__gte": start_of_day(value)})


class DateBeforeFilter(django_filters.DateFilter):
    """Until the end of that day (inclusive)."""

    def filter(self, qs, value):
        if value is None:
            return qs
        return qs.filter(**{f"{self.field_name}__lt": start_of_day(value + timedelta(days=1))})


class RangeCheckedFilterSet(django_filters.FilterSet):
    """FilterSet that rejects reversed ranges with a 400 error.

    Subclasses list their (low, high) filter names in `range_pairs`,
    for example  range_pairs = [("posted_after", "posted_before")].
    """
    range_pairs = []

    def filter_queryset(self, queryset):
        data = self.form.cleaned_data
        for low, high in self.range_pairs:
            a, b = data.get(low), data.get(high)
            if a is not None and b is not None and a > b:
                raise ValidationError({high: [f"Must not be earlier than {low}."]})
        return super().filter_queryset(queryset)
