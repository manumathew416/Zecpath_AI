"""Day 11 - profile module tests.

Run with:  python manage.py test apps.accounts
"""
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Candidate, Employer, Role, User
from apps.jobs.models import Job


class ProfileBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.pw = "Str0ng#Pass99"
        self.admin = User.objects.create_superuser(email="admin@z.com", password=self.pw)
        self.cand1 = User.objects.create_user(
            email="c1@z.com", password=self.pw, role=Role.CANDIDATE, phone="9000000001")
        self.cand2 = User.objects.create_user(
            email="c2@z.com", password=self.pw, role=Role.CANDIDATE, phone="9000000002")
        self.emp1 = User.objects.create_user(email="e1@z.com", password=self.pw, role=Role.EMPLOYER)
        self.emp2 = User.objects.create_user(email="e2@z.com", password=self.pw, role=Role.EMPLOYER)

    def login(self, user):
        r = self.client.post(reverse("login"), {"email": user.email, "password": self.pw})
        self.assertEqual(r.status_code, 200, r.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def anon(self):
        self.client.credentials()

    cand_data = {"skills": "python, Django ,python", "education": "B.Tech CSE",
                 "experience_years": 1, "expected_salary": "350000", "location": "Kochi"}
    emp_data = {"company_name": "Zecpath", "domain": "zecpath.com", "company_size": "11-50",
                "website": "https://www.zecpath.com", "industry": "HR Tech", "location": "Kochi"}


class CandidateProfileTests(ProfileBase):
    url = property(lambda self: reverse("candidate-profile"))

    def test_signup_creates_blank_profile_and_view_works(self):
        self.login(self.cand1)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["email"], "c1@z.com")
        self.assertEqual(r.data["phone"], "9000000001")
        self.assertFalse(r.data["profile_complete"])

    def test_create_completes_profile_and_cleans_skills(self):
        self.login(self.cand1)
        r = self.client.post(self.url, self.cand_data, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["skills"], "python, Django")     # trimmed, no duplicate
        self.assertTrue(r.data["profile_complete"])
        self.assertEqual(self.client.post(self.url, self.cand_data, format="json").status_code, 400)

    def test_update_patch_and_put(self):
        self.login(self.cand1)
        self.client.post(self.url, self.cand_data, format="json")
        r = self.client.patch(self.url, {"expected_salary": "400000", "experience_years": 2}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["experience_years"], 2)
        r = self.client.put(self.url, {"skills": "Python"}, format="json")      # education missing
        self.assertEqual(r.status_code, 400)

    def test_validation_rules(self):
        self.login(self.cand1)
        bad = [
            {"expected_salary": "-5"},
            {"expected_salary": "0"},
            {"expected_salary": "999999999"},
            {"experience_years": 80},
            {"skills": "py<script>"},
            {"skills": " , , "},
            {"skills": ",".join(f"skill{i}" for i in range(31))},
            {"skills": ""},
            {"education": ""},
        ]
        for payload in bad:
            data = {**self.cand_data, **payload}
            r = self.client.post(self.url, data, format="json")
            self.assertEqual(r.status_code, 400, payload)

    def test_phone_and_email_cannot_be_changed_here(self):
        self.login(self.cand1)
        self.client.post(self.url, self.cand_data, format="json")
        self.client.patch(self.url, {"phone": "1111111111", "email": "x@x.com"}, format="json")
        self.cand1.refresh_from_db()
        self.assertEqual(self.cand1.phone, "9000000001")
        self.assertEqual(self.cand1.email, "c1@z.com")

    def test_each_candidate_only_sees_and_edits_own_profile(self):
        self.login(self.cand1)
        self.client.post(self.url, self.cand_data, format="json")
        self.login(self.cand2)
        r = self.client.get(self.url)
        self.assertEqual(r.data["email"], "c2@z.com")
        self.assertEqual(r.data["skills"], "")
        self.client.patch(self.url, {"location": "Pune"}, format="json")
        self.assertEqual(Candidate.objects.get(user=self.cand1).location, "Kochi")   # untouched

    def test_soft_delete_lifecycle(self):
        self.login(self.cand1)
        self.client.post(self.url, self.cand_data, format="json")
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        profile = Candidate.objects.get(user=self.cand1)            # row still exists
        self.assertTrue(profile.is_deleted)
        self.assertIsNotNone(profile.deleted_at)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.patch(self.url, {"location": "X"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(self.url).status_code, 404)
        r = self.client.post(self.url, self.cand_data, format="json")      # restore
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertFalse(Candidate.objects.get(user=self.cand1).is_deleted)

    def test_deleted_candidate_cannot_apply(self):
        job = Job.objects.create(employer=self.emp1.employer_profile, title="T",
                                 description="d", location="k")
        self.login(self.cand1)
        self.client.delete(self.url)
        self.assertEqual(self.client.post(reverse("apply", args=[job.pk])).status_code, 403)


class EmployerProfileTests(ProfileBase):
    url = property(lambda self: reverse("employer-profile"))

    def test_create_view_update(self):
        self.login(self.emp1)
        self.assertEqual(self.client.get(self.url).data["profile_complete"], False)
        r = self.client.post(self.url, self.emp_data, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["domain"], "zecpath.com")
        r = self.client.patch(self.url, {"company_size": "51-200"}, format="json")
        self.assertEqual(r.data["company_size"], "51-200")

    def test_validation_rules(self):
        self.login(self.emp1)
        bad = [
            {"company_name": "A"},
            {"company_name": ""},
            {"domain": "https://zecpath.com"},
            {"domain": "zecpath"},
            {"domain": "zec path.com"},
            {"company_size": "huge"},
            {"website": "not-a-url"},
            {"website": "https://other-site.com"},          # does not match the domain
        ]
        for payload in bad:
            r = self.client.post(self.url, {**self.emp_data, **payload}, format="json")
            self.assertEqual(r.status_code, 400, payload)

    def test_domain_is_normalised(self):
        self.login(self.emp1)
        r = self.client.post(self.url, {**self.emp_data, "domain": "WWW.Zecpath.COM"}, format="json")
        self.assertEqual(r.data["domain"], "zecpath.com")

    def test_employer_cannot_verify_themselves(self):
        self.login(self.emp1)
        r = self.client.post(self.url, {**self.emp_data, "is_verified": True}, format="json")
        self.assertFalse(r.data["is_verified"])
        r = self.client.patch(self.url, {"is_verified": True}, format="json")
        self.assertFalse(r.data["is_verified"])
        self.assertFalse(Employer.objects.get(user=self.emp1).is_verified)

    def test_soft_delete_and_deleted_employer_cannot_post_jobs(self):
        self.login(self.emp1)
        self.client.post(self.url, self.emp_data, format="json")
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        r = self.client.post(reverse("job-create"),
                             {"title": "x", "description": "d", "location": "k"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.post(self.url, self.emp_data, format="json").status_code, 201)
        r = self.client.post(reverse("job-create"),
                             {"title": "x", "description": "d", "location": "k"})
        self.assertEqual(r.status_code, 201)


class ProfileSecurityTests(ProfileBase):
    def test_no_token_is_401(self):
        for name in ("candidate-profile", "employer-profile"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 401)

    def test_wrong_role_is_403(self):
        self.login(self.cand1)
        self.assertEqual(self.client.get(reverse("employer-profile")).status_code, 403)
        self.login(self.emp1)
        self.assertEqual(self.client.get(reverse("candidate-profile")).status_code, 403)

    def test_non_admin_cannot_use_admin_profile_endpoints(self):
        pk = self.cand1.candidate_profile.pk
        for u in (self.cand1, self.emp1):
            self.login(u)
            self.assertEqual(self.client.get(reverse("admin-candidates")).status_code, 403)
            self.assertEqual(self.client.get(reverse("admin-employers")).status_code, 403)
            r = self.client.delete(reverse("admin-candidate-detail", args=[pk]))
            self.assertEqual(r.status_code, 403)
        self.assertFalse(Candidate.objects.get(pk=pk).is_deleted)


class AdminOverrideTests(ProfileBase):
    def test_admin_list_view_and_edit_any_profile(self):
        self.login(self.cand1)
        self.client.post(reverse("candidate-profile"), self.cand_data, format="json")
        self.login(self.admin)
        r = self.client.get(reverse("admin-candidates"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 2)
        pk = self.cand1.candidate_profile.pk
        r = self.client.patch(reverse("admin-candidate-detail", args=[pk]),
                              {"location": "Delhi"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["location"], "Delhi")
        r = self.client.patch(reverse("admin-candidate-detail", args=[pk]),
                              {"expected_salary": "-1"}, format="json")
        self.assertEqual(r.status_code, 400)                     # same rules apply to admin

    def test_admin_soft_delete_filter_and_restore(self):
        pk = self.cand1.candidate_profile.pk
        self.login(self.admin)
        self.assertEqual(self.client.delete(reverse("admin-candidate-detail", args=[pk])).status_code, 204)
        self.assertEqual(self.client.get(reverse("admin-candidates")).data["count"], 1)
        r = self.client.get(reverse("admin-candidates") + "?deleted=true")
        self.assertEqual([p["id"] for p in r.data["results"]], [pk])
        self.assertEqual(self.client.get(reverse("admin-candidates") + "?deleted=all").data["count"], 2)
        r = self.client.post(reverse("admin-candidate-restore", args=[pk]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_deleted"])

    def test_user_cannot_undo_an_admin_deletion(self):
        pk = self.cand1.candidate_profile.pk
        self.login(self.admin)
        self.client.delete(reverse("admin-candidate-detail", args=[pk]))
        self.login(self.cand1)
        self.assertEqual(self.client.get(reverse("candidate-profile")).status_code, 404)
        r = self.client.post(reverse("candidate-profile"), self.cand_data, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Candidate.objects.get(pk=pk).is_deleted)

    def test_admin_verifies_employer_and_it_survives_login(self):
        pk = self.emp1.employer_profile.pk
        self.login(self.admin)
        r = self.client.patch(reverse("admin-employer-detail", args=[pk]),
                              {"is_verified": True}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_verified"])
        self.login(self.emp1)             # login saves the user; the flag must not reset
        self.assertTrue(self.client.get(reverse("employer-profile")).data["is_verified"])
        self.login(self.admin)
        self.client.patch(reverse("admin-employer-detail", args=[pk]),
                          {"is_verified": False}, format="json")
        self.assertFalse(Employer.objects.get(pk=pk).is_verified)
