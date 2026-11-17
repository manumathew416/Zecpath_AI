from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager, PermissionsMixin)
import os
import uuid

from django.db import models
from django.utils import timezone

from apps.core.models import SoftDeleteModel


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    EMPLOYER = "employer", "Employer"
    CANDIDATE = "candidate", "Candidate"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, role=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        if not role:
            raise ValueError("Role is required")
        user = self.model(
            email=self.normalize_email(email), role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        return self.create_user(
            email, password, role=Role.ADMIN, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)   # needed for /admin/ access
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        indexes = [
            # admin user list: WHERE role=? ORDER BY created_at DESC
            models.Index(fields=["role", "-created_at"], name="user_role_created_idx"),
        ]

    def __str__(self):
        return self.email


def resume_upload_path(instance, filename):
    """Naming standard: resumes/candidate_<id>/resume_<date>-<time>_<random>.<ext>

    The name is built by the server. The name sent by the user is never used
    for storage, so it cannot overwrite a file or point to another folder.
    """
    ext = os.path.splitext(filename)[1].lower()
    stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
    return f"resumes/candidate_{instance.pk}/resume_{stamp}_{uuid.uuid4().hex[:8]}{ext}"


class Employer(SoftDeleteModel):
    class CompanySize(models.TextChoices):
        S1 = "1-10", "1-10 employees"
        S2 = "11-50", "11-50 employees"
        S3 = "51-200", "51-200 employees"
        S4 = "201-500", "201-500 employees"
        S5 = "501+", "501+ employees"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="employer_profile")
    company_name = models.CharField(max_length=150, blank=True)
    domain = models.CharField(max_length=100, blank=True)      # e.g. zecpath.com
    company_size = models.CharField(
        max_length=10, choices=CompanySize.choices, blank=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)   # only admin can change it
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    @property
    def is_complete(self):
        return bool(self.company_name and self.domain)

    def __str__(self):
        return self.company_name or self.user.email


class Candidate(SoftDeleteModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="candidate_profile")
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    skills = models.TextField(blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    education = models.CharField(max_length=200, blank=True)
    resume = models.FileField(upload_to=resume_upload_path, blank=True)
    resume_original_name = models.CharField(max_length=255, blank=True)
    resume_size = models.PositiveIntegerField(null=True, blank=True)       # bytes
    resume_hash = models.CharField(max_length=64, blank=True)              # SHA-256
    resume_uploaded_at = models.DateTimeField(null=True, blank=True)
    resume_text = models.TextField(blank=True)
    expected_salary = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        indexes = [
            # candidate search: WHERE is_deleted=0 AND experience_years BETWEEN ? AND ? ORDER BY experience_years DESC
            models.Index(fields=["is_deleted", "-experience_years", "-id"], name="cand_deleted_exp_idx"),
        ]

    @property
    def is_complete(self):
        return bool(self.skills and self.education)

    def __str__(self):
        return self.user.email