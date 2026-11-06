"""Day 10 - Unauthorized access testing.

Run with:  python manage.py test apps.core
"""
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.applications.models import Application
from apps.jobs.models import Job


class RBACTests(APITestCase):
    def setUp(self):
        cache.clear()   # reset rate-limit counters between tests
        self.pw = "Str0ng#Pass99"
        self.admin = User.objects.create_superuser(email="admin@z.com", password=self.pw)
        self.emp1 = User.objects.create_user(email="e1@z.com", password=self.pw, role=Role.EMPLOYER)
        self.emp2 = User.objects.create_user(email="e2@z.com", password=self.pw, role=Role.EMPLOYER)
        self.cand = User.objects.create_user(email="c1@z.com", password=self.pw, role=Role.CANDIDATE)
        self.cand2 = User.objects.create_user(email="c2@z.com", password=self.pw, role=Role.CANDIDATE)
        self.job = Job.objects.create(employer=self.emp1.employer_profile, title="Django Dev",
                                      description="x", location="Kochi")

    def login(self, user):
        r = self.client.post(reverse("login"), {"email": user.email, "password": self.pw})
        self.assertEqual(r.status_code, 200, r.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def anon(self):
        self.client.credentials()

    # ---- no token ----
    def test_no_token_is_401_everywhere(self):
        for name, args in [("job-list", []), ("job-create", []), ("admin-users", []),
                           ("my-applications", []), ("employer-jobs", [])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 401, name)

    def test_garbage_token_is_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not.a.real.token")
        self.assertEqual(self.client.get(reverse("job-list")).status_code, 401)
        self.assertEqual(self.client.get(reverse("admin-users")).status_code, 401)

    # ---- employer rules ----
    def test_employer_can_post_job_and_owns_it(self):
        self.login(self.emp1)
        r = self.client.post(reverse("job-create"),
                             {"title": "QA", "description": "d", "location": "Kochi",
                              "employer": self.emp2.employer_profile.pk})   # attempt to spoof owner
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["employer"], self.emp1.employer_profile.pk)   # spoof ignored

    def test_candidate_cannot_post_job(self):
        self.login(self.cand)
        r = self.client.post(reverse("job-create"), {"title": "x", "description": "d", "location": "k"})
        self.assertEqual(r.status_code, 403)

    def test_employer_cannot_edit_or_delete_other_employers_job(self):
        self.login(self.emp2)
        url = reverse("job-detail", args=[self.job.pk])
        self.assertEqual(self.client.patch(url, {"title": "hacked"}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, "Django Dev")

    def test_owner_can_edit_own_job(self):
        self.login(self.emp1)
        r = self.client.patch(reverse("job-detail", args=[self.job.pk]), {"status": "closed"})
        self.assertEqual(r.status_code, 200)

    # ---- candidate rules ----
    def test_candidate_can_apply_once(self):
        self.login(self.cand)
        url = reverse("apply", args=[self.job.pk])
        self.assertEqual(self.client.post(url).status_code, 201)
        self.assertEqual(self.client.post(url).status_code, 400)   # duplicate

    def test_employer_and_admin_cannot_apply(self):
        for u in (self.emp1, self.admin):
            self.login(u)
            self.assertEqual(self.client.post(reverse("apply", args=[self.job.pk])).status_code, 403)

    def test_candidate_sees_only_own_applications(self):
        Application.objects.create(job=self.job, candidate=self.cand.candidate_profile)
        self.login(self.cand2)
        r = self.client.get(reverse("my-applications"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 0)

    def test_employer_sees_applicants_only_for_own_job(self):
        Application.objects.create(job=self.job, candidate=self.cand.candidate_profile)
        self.login(self.emp2)
        self.assertEqual(self.client.get(reverse("job-applicants", args=[self.job.pk])).status_code, 404)
        self.login(self.emp1)
        r = self.client.get(reverse("job-applicants", args=[self.job.pk]))
        self.assertEqual(len(r.data), 1)

    def test_employer_cannot_change_status_of_other_jobs_application(self):
        app = Application.objects.create(job=self.job, candidate=self.cand.candidate_profile)
        self.login(self.emp2)
        r = self.client.patch(reverse("application-status", args=[app.pk]), {"status": "hired"})
        self.assertEqual(r.status_code, 404)
        self.login(self.emp1)
        r = self.client.patch(reverse("application-status", args=[app.pk]), {"status": "shortlisted"})
        self.assertEqual(r.status_code, 200)

    def test_candidate_cannot_set_own_status_or_score(self):
        self.login(self.cand)
        self.client.post(reverse("apply", args=[self.job.pk]), {"status": "hired", "ats_score": 99})
        app = Application.objects.get()
        self.assertEqual(app.status, "applied")
        self.assertIsNone(app.ats_score)

    # ---- admin rules ----
    def test_admin_can_list_and_block_users(self):
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse("admin-users")).status_code, 200)
        r = self.client.patch(reverse("admin-user-active", args=[self.cand.pk]), {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.anon()
        r = self.client.post(reverse("login"), {"email": self.cand.email, "password": self.pw})
        self.assertEqual(r.status_code, 401)   # blocked user cannot log in

    def test_admin_cannot_block_self(self):
        self.login(self.admin)
        r = self.client.patch(reverse("admin-user-active", args=[self.admin.pk]), {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_non_admin_blocked_from_admin_area_by_middleware(self):
        for u in (self.cand, self.emp1):
            self.login(u)
            r = self.client.get(reverse("admin-users"))
            self.assertEqual(r.status_code, 403)
            r = self.client.patch(reverse("admin-user-active", args=[self.admin.pk]), {"is_active": False}, format="json")
            self.assertEqual(r.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_wrong_role_blocked_in_other_role_area(self):
        self.login(self.cand)
        self.assertEqual(self.client.get(reverse("employer-jobs")).status_code, 403)
        self.login(self.emp1)
        self.assertEqual(self.client.get(reverse("my-applications")).status_code, 403)

    # ---- privilege escalation at signup ----
    def test_cannot_register_as_admin(self):
        r = self.client.post(reverse("register"), {"email": "x@z.com", "phone": "9999999999",
                                                   "password": self.pw, "role": "admin"})
        self.assertEqual(r.status_code, 400)

    # ---- API abuse prevention ----
    def test_login_is_rate_limited(self):
        codes = [self.client.post(reverse("login"), {"email": "c1@z.com", "password": "wrong"}).status_code
                 for _ in range(7)]
        self.assertEqual(codes[:5], [401] * 5)
        self.assertIn(429, codes[5:])
