from django.db import models


class Job(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    employer = models.ForeignKey(
        "accounts.Employer", on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=150)
    description = models.TextField()
    location = models.CharField(max_length=100)
    skills_required = models.TextField(blank=True)
    min_experience = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN)
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Day 14 - each index matches a real query (see DAY14 notes)
        indexes = [
            # public list: WHERE status='open' ORDER BY posted_at DESC
            models.Index(fields=["status", "-posted_at", "-id"], name="job_status_posted_idx"),
            # employer's own list: WHERE employer_id=? ORDER BY posted_at DESC
            models.Index(fields=["employer", "-posted_at", "-id"], name="job_employer_posted_idx"),
        ]

    def __str__(self):
        return f"{self.title} at {self.employer.company_name}"