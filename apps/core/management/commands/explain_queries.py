"""Day 14 - show how the database runs the main list queries.

    python manage.py explain_queries

For each query it prints the SQL and the database's own plan (EXPLAIN).
Read the plan like this (SQLite):
    SEARCH ... USING INDEX name     good: the index finds the rows directly
    SCAN ...                        bad on a big table: every row is read
    USE TEMP B-TREE FOR ORDER BY    an extra sort: the index did not give the order
Run `python manage.py seed_demo_data` first, or the tables are too small to matter.
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.accounts.models import Candidate, Role, User
from apps.applications.models import Application
from apps.jobs.models import Job


def queries():
    since = timezone.now() - timedelta(days=30)
    yield "Public job list (open jobs, newest first)", \
        Job.objects.filter(status="open", employer__is_deleted=False).order_by("-posted_at", "-id")[:10]
    yield "Jobs posted in the last 30 days", \
        Job.objects.filter(status="open", posted_at__gte=since).order_by("-posted_at")[:10]
    yield "Employer's own jobs", \
        Job.objects.filter(employer_id=1).order_by("-posted_at", "-id")[:10]
    yield "Candidate's own applications", \
        Application.objects.filter(candidate_id=1).order_by("-applied_at", "-id")[:10]
    yield "Applicants of a job by status", \
        Application.objects.filter(job_id=1, status="applied")
    yield "Admin: users by role, newest first", \
        User.objects.filter(role=Role.EMPLOYER).order_by("-created_at")[:10]
    yield "Candidate search by experience range", \
        Candidate.objects.filter(is_deleted=False, experience_years__gte=3, experience_years__lte=5).order_by("-experience_years", "-id")[:10]
    yield "Keyword search (icontains) - cannot use an index", \
        Job.objects.filter(title__icontains="django").order_by("-posted_at")[:10]


class Command(BaseCommand):
    help = "Print the SQL and the query plan of the main list queries."

    def handle(self, *args, **options):
        if connection.vendor == "sqlite":
            with connection.cursor() as c:
                c.execute("ANALYZE")      # gives SQLite table statistics so it can pick indexes well
        else:
            self.stdout.write("Plans below use the generic EXPLAIN of your database.")
        for title, qs in queries():
            sql, params = qs.query.sql_with_params()
            prefix = "EXPLAIN QUERY PLAN " if connection.vendor == "sqlite" else "EXPLAIN "
            with connection.cursor() as c:
                c.execute(prefix + sql, params)
                plan = c.fetchall()
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{title}"))
            for row in plan:
                self.stdout.write("   " + str(row[-1] if connection.vendor == "sqlite" else row))
