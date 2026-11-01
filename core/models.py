from django.conf import settings
from django.db import models


class Employer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="employer_profile")
    company_name = models.CharField(max_length=150)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name


class Candidate(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="candidate_profile")
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    skills = models.TextField(blank=True)             # for ATS keyword matching
    experience_years = models.PositiveIntegerField(default=0)
    education = models.CharField(max_length=200, blank=True)
    resume = models.FileField(upload_to="resumes/", blank=True)
    resume_text = models.TextField(blank=True)        # parsed text, filled by ATS later
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Job(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    employer = models.ForeignKey(
        Employer, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=150)
    description = models.TextField()
    location = models.CharField(max_length=100)
    skills_required = models.TextField(blank=True)    # for ATS keyword matching
    min_experience = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN)
    posted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} at {self.employer.company_name}"


class Application(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        SHORTLISTED = "shortlisted", "Shortlisted"
        REJECTED = "rejected", "Rejected"
        HIRED = "hired", "Hired"

    job = models.ForeignKey(
        Job, on_delete=models.CASCADE, related_name="applications")
    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="applications")
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.APPLIED)
    ats_score = models.FloatField(null=True, blank=True)  # filled by ATS later
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "candidate"], name="unique_application")
        ]

    def __str__(self):
        return f"{self.candidate} -> {self.job.title}"