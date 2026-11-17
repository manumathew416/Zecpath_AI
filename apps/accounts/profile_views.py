from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin, IsCandidate, IsEmployer

from .filters import CandidateFilter, EmployerFilter
from .models import Candidate, Employer
from .search_serializers import CandidateSearchSerializer
from .profile_serializers import (
    AdminCandidateSerializer, AdminEmployerSerializer,
    CandidateProfileSerializer, EmployerProfileSerializer)


# =====================================================================
#  Own profile  (self only: there is no id in the URL, the profile is
#  always found from the logged-in user, so nobody can reach another one)
# =====================================================================

class OwnProfileView(APIView):
    model = None
    serializer_class = None

    def get_profile(self, request):
        return self.model.objects.filter(user=request.user).first()

    def get_active_profile(self, request):
        profile = self.get_profile(request)
        if profile is None or profile.is_deleted:
            return None
        return profile

    @staticmethod
    def not_found():
        return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

    # VIEW
    def get(self, request):
        profile = self.get_active_profile(request)
        if profile is None:
            return self.not_found()
        return Response(self.serializer_class(profile).data)

    # CREATE  (also completes the blank profile made at signup, or
    #          restores a profile the user deleted earlier)
    def post(self, request):
        profile = self.get_profile(request)

        if profile is not None and profile.is_deleted:
            if profile.deleted_by_id not in (None, request.user.id):
                return Response(
                    {"detail": "This profile was deactivated by an administrator."},
                    status=status.HTTP_403_FORBIDDEN)
        elif profile is not None and profile.is_complete:
            return Response(
                {"detail": "Profile already exists. Use PATCH to update it."},
                status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        if profile is None:
            profile = serializer.save(user=request.user)
        else:
            profile = serializer.save()
            if profile.is_deleted:
                profile.restore()
        return Response(self.serializer_class(profile).data, status=status.HTTP_201_CREATED)

    # UPDATE
    def put(self, request):
        return self.update(request, partial=False)

    def patch(self, request):
        return self.update(request, partial=True)

    def update(self, request, partial):
        profile = self.get_active_profile(request)
        if profile is None:
            return self.not_found()
        serializer = self.serializer_class(profile, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    # SOFT DELETE
    def delete(self, request):
        profile = self.get_active_profile(request)
        if profile is None:
            return self.not_found()
        profile.soft_delete(by=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CandidateOwnProfileView(OwnProfileView):
    model = Candidate
    serializer_class = CandidateProfileSerializer
    permission_classes = [IsCandidate]


class EmployerOwnProfileView(OwnProfileView):
    model = Employer
    serializer_class = EmployerProfileSerializer
    permission_classes = [IsEmployer]


# =====================================================================
#  Admin override  (admin can list, view, edit, soft delete and restore
#  any profile, and verify employers)
# =====================================================================

class AdminProfileListView(generics.ListAPIView):
    """?deleted=true shows only soft-deleted profiles, ?deleted=all shows both.

    Plus the filters, ?search= and ?ordering= set on each subclass below.
    """
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    model = None
    heavy_fields = ()          # big columns that the list does not show

    def get_queryset(self):
        qs = self.model.objects.select_related("user")
        if self.heavy_fields:
            qs = qs.defer(*self.heavy_fields)     # do not load them for list rows
        flag = self.request.query_params.get("deleted", "false").lower()
        if flag == "all":
            return qs
        return qs.filter(is_deleted=(flag == "true"))


class AdminProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    http_method_names = ["get", "patch", "put", "delete", "head", "options"]
    model = None

    def get_queryset(self):
        return self.model.objects.select_related("user")

    def perform_destroy(self, instance):
        instance.soft_delete(by=self.request.user)


class AdminProfileRestoreView(APIView):
    permission_classes = [IsAdmin]
    model = None
    serializer_class = None

    def post(self, request, pk):
        profile = get_object_or_404(self.model, pk=pk)
        profile.restore()
        return Response(self.serializer_class(profile).data)


class AdminCandidateListView(AdminProfileListView):
    model = Candidate
    serializer_class = AdminCandidateSerializer
    heavy_fields = ("resume_text",)          # whole resume text is never listed
    filterset_class = CandidateFilter
    search_fields = ["user__email", "skills", "education", "location"]
    ordering_fields = ["id", "created_at", "experience_years"]
    ordering = ["id"]


class AdminCandidateDetailView(AdminProfileDetailView):
    model = Candidate
    serializer_class = AdminCandidateSerializer


class AdminCandidateRestoreView(AdminProfileRestoreView):
    model = Candidate
    serializer_class = AdminCandidateSerializer


class AdminEmployerListView(AdminProfileListView):
    model = Employer
    serializer_class = AdminEmployerSerializer
    filterset_class = EmployerFilter
    search_fields = ["user__email", "company_name", "domain", "industry"]
    ordering_fields = ["id", "created_at", "company_name"]
    ordering = ["id"]


class AdminEmployerDetailView(AdminProfileDetailView):
    model = Employer
    serializer_class = AdminEmployerSerializer


class AdminEmployerRestoreView(AdminProfileRestoreView):
    model = Employer
    serializer_class = AdminEmployerSerializer


# =====================================================================
#  Search endpoint for employers: find candidates by keyword
# =====================================================================

class CandidateSearchView(generics.ListAPIView):
    """GET /api/employer/candidates/search/?search=python django&experience_from=2&location=kochi

    Employers can search active candidates. Results show only skills, education,
    location and experience (no email, phone, salary or resume).
    """
    serializer_class = CandidateSearchSerializer
    permission_classes = [IsEmployer]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CandidateFilter
    search_fields = ["skills", "education", "location"]
    ordering_fields = ["experience_years", "updated_at"]
    ordering = ["-experience_years", "-id"]

    def get_queryset(self):
        return (Candidate.objects
                .filter(is_deleted=False, user__is_active=True)
                .only("id", "location", "skills", "education", "experience_years", "updated_at"))
