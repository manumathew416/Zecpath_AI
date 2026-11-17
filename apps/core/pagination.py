"""Day 14 - pagination classes.

Two styles are available:

  StandardPagination    page-number ("offset") style   ?page=2&page_size=20
  FeedCursorPagination  cursor style                   ?cursor=cD0yMDI2...&page_size=20

Page size is configured in settings.py (API_PAGE_SIZE, API_MAX_PAGE_SIZE),
which read the .env file, so it can change without touching the code.
"""
from django.conf import settings
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response

DEFAULT_PAGE_SIZE = getattr(settings, "API_PAGE_SIZE", 10)
MAX_PAGE_SIZE = getattr(settings, "API_MAX_PAGE_SIZE", 100)


class StandardPagination(PageNumberPagination):
    """Default for every list endpoint (set in REST_FRAMEWORK).

    - ?page_size=N is allowed but capped at MAX_PAGE_SIZE, so nobody can ask for
      a million rows in one request.
    - A bad page_size (abc, 0, -5) falls back to the default instead of failing.
    - A page that does not exist (?page=999) answers 404 in the standard error format.
    """
    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "total_pages": self.page.paginator.num_pages,
            "current_page": self.page.number,
            "page_size": self.get_page_size(self.request),
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })

    def get_paginated_response_schema(self, schema):
        return schema


class FeedCursorPagination(CursorPagination):
    """Cursor ("keyset") pagination for feeds that only move forward/back.

    It never runs COUNT(*) and never uses OFFSET, so page 1000 is as fast as
    page 1, and new rows added while the user scrolls cannot cause duplicates
    or skipped items. The price: no total count and no "jump to page 7".

    The cursor remembers only the FIRST ordering field, so that field must be
    unique. A timestamp is not (two jobs can share the same posted_at, and
    Windows clocks tie often), which would repeat or skip rows between pages.
    That is why the feed is ordered by "-id": unique, and newest first because
    ids only grow.
    """
    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE
    ordering = "-id"

    def get_paginated_response(self, data):
        return Response({
            "page_size": self.get_page_size(self.request),
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })

    def get_paginated_response_schema(self, schema):
        return schema
