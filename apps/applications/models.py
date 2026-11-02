from django.db import models


class Application(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        SHORTLISTED = "shortlisted", "Shortlisted"
        REJECTED = "rejected", "Rejected"
        HIRED = "hired", "Hired"

    job = models.ForeignKey(
        "jobs.Job", on_delete=models.CASCADE, related_name="applications")
    candidate = models.ForeignKey(
        "accounts.Candidate", on_delete=models.CASCADE, related_name="applications")
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.APPLIED)
    ats_score = models.FloatField(null=True, blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "candidate"], name="unique_application")
        ]

    def __str__(self):
        return f"{self.candidate} -> {self.job.title}"