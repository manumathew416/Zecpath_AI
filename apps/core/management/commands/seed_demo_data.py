"""Day 14 - fill the database with fake data so pagination, search and speed
can be tested on a LARGE table.

    python manage.py seed_demo_data                       # 20 employers, 300 candidates, 3000 jobs
    python manage.py seed_demo_data --jobs 20000 --candidates 2000
    python manage.py seed_demo_data --clear               # remove the demo data again

All demo accounts use the email ending @demo.local, so --clear removes only them.
Demo password for every account: Demo#Pass123
"""
import random
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Candidate, Employer, Role, User
from apps.applications.models import Application
from apps.jobs.models import Job

CITIES = ["Kochi", "Bengaluru", "Chennai", "Hyderabad", "Pune", "Mumbai", "Delhi",
          "Kozhikode", "Trivandrum", "Remote"]
SKILLS = ["python", "django", "react", "node", "sql", "docker", "aws", "java",
          "spring", "git", "rest", "postgres", "javascript", "html", "css", "linux"]
TITLES = ["Backend Developer", "Frontend Developer", "Full Stack Developer",
          "Python Developer", "Data Analyst", "DevOps Engineer", "QA Engineer",
          "Django Developer", "Software Engineer", "Support Engineer"]
DEMO_DOMAIN = "@demo.local"


class Command(BaseCommand):
    help = "Create (or remove with --clear) fake employers, candidates, jobs and applications."

    def add_arguments(self, parser):
        parser.add_argument("--employers", type=int, default=20)
        parser.add_argument("--candidates", type=int, default=300)
        parser.add_argument("--jobs", type=int, default=3000)
        parser.add_argument("--applications", type=int, default=6000)
        parser.add_argument("--clear", action="store_true", help="delete demo data and stop")

    @transaction.atomic
    def handle(self, *args, **o):
        if o["clear"]:
            n, _ = User.objects.filter(email__endswith=DEMO_DOMAIN).delete()
            self.stdout.write(self.style.SUCCESS(f"Removed {n} demo rows."))
            return

        rnd = random.Random(14)                     # same data on every run
        now = timezone.now()
        pw = make_password("Demo#Pass123")          # hash ONCE; hashing 300 times is slow

        # ---- users (bulk_create skips signals, so profiles are made below) ----
        emp_users = User.objects.bulk_create([
            User(email=f"employer{i}{DEMO_DOMAIN}", role=Role.EMPLOYER, password=pw)
            for i in range(o["employers"])])
        cand_users = User.objects.bulk_create([
            User(email=f"candidate{i}{DEMO_DOMAIN}", role=Role.CANDIDATE, password=pw)
            for i in range(o["candidates"])])
        emp_users = list(User.objects.filter(email__endswith=DEMO_DOMAIN, role=Role.EMPLOYER))
        cand_users = list(User.objects.filter(email__endswith=DEMO_DOMAIN, role=Role.CANDIDATE))

        Employer.objects.bulk_create([
            Employer(user=u, company_name=f"Demo Company {u.pk}", domain=f"company{u.pk}.com",
                     industry=rnd.choice(["IT", "Finance", "Health", "Retail"]),
                     location=rnd.choice(CITIES)) for u in emp_users])
        Candidate.objects.bulk_create([
            Candidate(user=u, location=rnd.choice(CITIES),
                      skills=", ".join(rnd.sample(SKILLS, 4)),
                      education=rnd.choice(["B.Tech", "BCA", "MCA", "M.Tech", "B.Sc"]),
                      experience_years=rnd.randint(0, 10)) for u in cand_users])
        employers = list(Employer.objects.filter(user__in=emp_users))
        candidates = list(Candidate.objects.filter(user__in=cand_users))

        # ---- jobs ----
        jobs = Job.objects.bulk_create([
            Job(employer=rnd.choice(employers),
                title=rnd.choice(TITLES),
                description=f"We need a {rnd.choice(SKILLS)} person for our team.",
                location=rnd.choice(CITIES),
                skills_required=", ".join(rnd.sample(SKILLS, 3)),
                min_experience=rnd.randint(0, 6),
                status=rnd.choices([Job.Status.OPEN, Job.Status.CLOSED], [8, 2])[0])
            for _ in range(o["jobs"])], batch_size=500)
        # auto_now_add ignores given dates, so spread the dates with an update
        for j in jobs:
            j.posted_at = now - timedelta(days=rnd.randint(0, 180), minutes=rnd.randint(0, 1439))
        Job.objects.bulk_update(jobs, ["posted_at"], batch_size=500)

        # ---- applications (one per job+candidate pair) ----
        pairs = set()
        job_ids = [j.pk for j in jobs]
        while len(pairs) < min(o["applications"], len(job_ids) * len(candidates)):
            pairs.add((rnd.choice(job_ids), rnd.choice(candidates).pk))
        apps = Application.objects.bulk_create([
            Application(job_id=j, candidate_id=c,
                        status=rnd.choice(list(Application.Status.values)),
                        ats_score=round(rnd.uniform(20, 99), 1)) for j, c in pairs],
            batch_size=500)
        for a in apps:
            a.applied_at = now - timedelta(days=rnd.randint(0, 120), minutes=rnd.randint(0, 1439))
        Application.objects.bulk_update(apps, ["applied_at"], batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f"Created {len(emp_users)} employers, {len(cand_users)} candidates, "
            f"{len(jobs)} jobs, {len(apps)} applications. Password: Demo#Pass123"))
