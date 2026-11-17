from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated

from apps.core.pagination import FeedCursorPagination
from apps.core.permissions import IsAdmin, IsEmployer, IsJobOwner

from .filters import EmployerJobFilter, JobFilter
from .models import Job
from .serializers import EmployerJobSerializer, JobSerializer


class JobListView(generics.ListAPIView):
    """Any logged-in user can browse open jobs.

    Pagination  ?page=2&page_size=20
    Filters     ?location=kochi &company=zec &experience_from=0 &experience_to=3
                &posted_after=2026-11-01 &posted_before=2026-11-30
    Search      ?search=django remote      (every word must match title, description,
                skills, location or company name)
    Ordering    ?ordering=-posted_at | title | min_experience
    """
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = JobFilter
    search_fields = ["title", "description", "skills_required", "location",
                     "employer__company_name"]
    ordering_fields = ["posted_at", "title", "min_experience"]
    ordering = ["-posted_at", "-id"]            # "-id" keeps pages stable when dates tie

    def get_queryset(self):
        # jobs of a deactivated (soft-deleted) employer are not shown.
        # select_related: the company name comes in the same query (no N+1).
        return (Job.objects
                .filter(status=Job.Status.OPEN, employer__is_deleted=False)
                .select_related("employer"))


class JobFeedView(JobListView):
    """Same jobs and same filters, but with CURSOR pagination: /api/jobs/feed/

    Use it for an infinite-scroll list. Newest first (by id), no total count, fast on any page.
    """
    pagination_class = FeedCursorPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]   # cursor fixes its own ordering
    ordering = None


class JobCreateView(generics.CreateAPIView):
    """Only employers can post jobs."""
    serializer_class = JobSerializer
    permission_classes = [IsEmployer]

    def perform_create(self, serializer):
        profile = self.request.user.employer_profile
        if profile.is_deleted:
            raise PermissionDenied("Your employer profile is deactivated.")
        serializer.save(employer=profile)


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Read: any logged-in user. Edit/delete: the owner employer or an admin."""
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsJobOwner]

    def get_queryset(self):
        qs = Job.objects.select_related("employer")
        if self.request.user.role != "admin":        # admin still sees everything
            qs = qs.filter(employer__is_deleted=False)
        return qs


class EmployerJobListView(generics.ListAPIView):
    """An employer sees only their own jobs (open and closed).

    Extra filter ?status=open|closed. Each row has applications_count.
    """
    serializer_class = EmployerJobSerializer
    permission_classes = [IsEmployer]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EmployerJobFilter
    search_fields = ["title", "description", "skills_required", "location"]
    ordering_fields = ["posted_at", "title", "min_experience", "applications_count"]
    ordering = ["-posted_at", "-id"]

    def get_queryset(self):
        return (Job.objects
                .filter(employer=self.request.user.employer_profile)
                .select_related("employer")
                .annotate(applications_count=Count("applications")))
