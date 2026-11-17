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
        # Day 14 - each index matches a real query
        indexes = [
            # employer's applicants: WHERE job_id=? AND status=?
            models.Index(fields=["job", "status"], name="app_job_status_idx"),
            # candidate's own list: WHERE candidate_id=? ORDER BY applied_at DESC
            models.Index(fields=["candidate", "-applied_at", "-id"], name="app_cand_applied_idx"),
        ]

    def __str__(self):
        return f"{self.candidate} -> {self.job.title}"