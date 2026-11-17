import os

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin, IsCandidate

from .models import Candidate
from .resume_utils import ALLOWED_TYPES, describe_resume, validate_resume_file


class ResumeUploadThrottle(UserRateThrottle):
    """Stops upload spam: 10 uploads per hour per user."""
    scope = "resume_upload"
    rate = "10/hour"


# ---------- helpers ----------

def remove_resume_file(profile):
    """Delete the stored file and clear its details."""
    if profile.resume:
        profile.resume.storage.delete(profile.resume.name)
    profile.resume = ""
    profile.resume_original_name = ""
    profile.resume_size = None
    profile.resume_hash = ""
    profile.resume_uploaded_at = None
    profile.save(update_fields=["resume", "resume_original_name", "resume_size",
                                "resume_hash", "resume_uploaded_at"])


def serve_resume(profile):
    """Send the file only through this view. There is no public /media/ URL."""
    if not profile.resume:
        raise NotFound("No resume uploaded.")
    ext = os.path.splitext(profile.resume.name)[1].lower()
    try:
        handle = profile.resume.open("rb")
    except FileNotFoundError:
        raise NotFound("The resume file is missing.")
    response = FileResponse(
        handle, as_attachment=True,
        filename=profile.resume_original_name or f"resume{ext}",
        content_type=ALLOWED_TYPES.get(ext, "application/octet-stream"))
    response["X-Content-Type-Options"] = "nosniff"      # browser must not guess the type
    response["Cache-Control"] = "private, no-store"
    return response


def get_active_candidate(user):
    profile = Candidate.objects.filter(user=user).first()
    if profile is None or profile.is_deleted:
        raise NotFound("Profile not found.")
    return profile


# ---------- candidate: own resume ----------

class CandidateResumeView(APIView):
    """POST = upload (or replace), GET = details, DELETE = remove."""
    permission_classes = [IsCandidate]
    parser_classes = [MultiPartParser]

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method == "POST":
            throttles.append(ResumeUploadThrottle())
        return throttles

    def get(self, request):
        profile = get_active_candidate(request.user)
        if not profile.resume:
            raise NotFound("No resume uploaded.")
        return Response(describe_resume(profile, reverse("candidate-resume-download")))

    def post(self, request):
        profile = get_active_candidate(request.user)
        upload = request.FILES.get("resume")
        if upload is None:
            return Response(
                {"resume": ["No file sent. Use form-data with the key 'resume'."]},
                status=status.HTTP_400_BAD_REQUEST)

        info = validate_resume_file(upload)

        # duplicate handling: the same file again is not stored twice
        if profile.resume and profile.resume_hash == info["hash"]:
            return Response(
                {"detail": "This file is already your current resume."},
                status=status.HTTP_409_CONFLICT)

        old_name = profile.resume.name if profile.resume else None
        profile.resume.save(f"resume{info['ext']}", upload, save=False)   # server-made name
        new_name = profile.resume.name
        profile.resume_original_name = info["original_name"]
        profile.resume_size = info["size"]
        profile.resume_hash = info["hash"]
        profile.resume_uploaded_at = timezone.now()
        try:
            profile.save(update_fields=["resume", "resume_original_name", "resume_size",
                                        "resume_hash", "resume_uploaded_at"])
        except Exception:
            profile.resume.storage.delete(new_name)      # do not leave an orphan file
            raise

        if old_name:                                     # replacement: remove the old file
            profile.resume.storage.delete(old_name)

        return Response(
            describe_resume(profile, reverse("candidate-resume-download")),
            status=status.HTTP_200_OK if old_name else status.HTTP_201_CREATED)

    def delete(self, request):
        profile = get_active_candidate(request.user)
        if not profile.resume:
            raise NotFound("No resume uploaded.")
        remove_resume_file(profile)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CandidateResumeDownloadView(APIView):
    permission_classes = [IsCandidate]

    def get(self, request):
        return serve_resume(get_active_candidate(request.user))


# ---------- admin override ----------

class AdminCandidateResumeView(APIView):
    """Admin can download or remove any candidate's resume."""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        return serve_resume(get_object_or_404(Candidate, pk=pk))

    def delete(self, request, pk):
        profile = get_object_or_404(Candidate, pk=pk)
        if not profile.resume:
            raise NotFound("No resume uploaded.")
        remove_resume_file(profile)
        return Response(status=status.HTTP_204_NO_CONTENT)
