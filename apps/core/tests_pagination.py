"""Day 14 - pagination, filters, search and query-count tests.

Run with:  python manage.py test apps.core.tests_pagination
"""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Candidate, Role, User
from apps.applications.models import Application
from apps.core.pagination import StandardPagination
from apps.jobs.models import Job


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.client.raise_request_exception = False
        self.pw = "Str0ng#Pass99"
        self.admin = User.objects.create_superuser(email="admin@z.com", password=self.pw)
        self.emp = User.objects.create_user(email="e1@z.com", password=self.pw, role=Role.EMPLOYER)
        self.emp2 = User.objects.create_user(email="e2@z.com", password=self.pw, role=Role.EMPLOYER)
        self.cand = User.objects.create_user(email="c1@z.com", password=self.pw, role=Role.CANDIDATE)
        for e, name in [(self.emp, "Zecpath Tech"), (self.emp2, "Other Corp")]:
            p = e.employer_profile
            p.company_name = name
            p.save()
        self.cand_tokens = {}

    def login(self, user):
        r = self.client.post(reverse("login"), {"email": user.email, "password": self.pw})
        self.assertEqual(r.status_code, 200, r.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['data']['access']}")

    def make_jobs(self, n, employer=None, **extra):
        employer = employer or self.emp.employer_profile
        jobs = [Job(employer=employer, title=extra.get("title", f"Job {i}"),
                    description=extra.get("description", "text"),
                    location=extra.get("location", "Kochi"),
                    skills_required=extra.get("skills_required", "python"),
                    min_experience=extra.get("min_experience", 0),
                    status=extra.get("status", "open")) for i in range(n)]
        return Job.objects.bulk_create(jobs)

    def get(self, name, query="", *args):
        r = self.client.get(reverse(name, args=args) + query)
        return r

    def data(self, r):
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertIs(body["success"], True)
        return body["data"]

    def ids(self, r):
        return [x["id"] for x in self.data(r)["results"]]


# ---------------------------------------------------------------- pagination
class PageNumberTests(Base):
    def setUp(self):
        super().setUp()
        self.make_jobs(25)
        self.login(self.cand)

    def test_default_page_shape_and_size(self):
        d = self.data(self.get("job-list"))
        self.assertEqual(set(d), {"count", "total_pages", "current_page", "page_size",
                                  "next", "previous", "results"})
        self.assertEqual(d["count"], 25)
        self.assertEqual(d["total_pages"], 3)
        self.assertEqual(d["current_page"], 1)
        self.assertEqual(d["page_size"], 10)
        self.assertEqual(len(d["results"]), 10)
        self.assertIsNone(d["previous"])
        self.assertIn("page=2", d["next"])

    def test_walking_all_pages_gives_every_row_once(self):
        seen = []
        for page in (1, 2, 3):
            seen += self.ids(self.get("job-list", f"?page={page}"))
        self.assertEqual(len(seen), 25)
        self.assertEqual(len(set(seen)), 25)           # no duplicates between pages

    def test_last_page_has_no_next(self):
        d = self.data(self.get("job-list", "?page=3"))
        self.assertEqual(len(d["results"]), 5)
        self.assertIsNone(d["next"])
        self.assertIn("page=2", d["previous"])

    def test_page_size_parameter(self):
        d = self.data(self.get("job-list", "?page_size=5"))
        self.assertEqual((len(d["results"]), d["total_pages"], d["page_size"]), (5, 5, 5))

    def test_page_size_is_capped(self):
        with mock.patch.object(StandardPagination, "max_page_size", 12):
            d = self.data(self.get("job-list", "?page_size=1000"))
        self.assertEqual(len(d["results"]), 12)
        self.assertEqual(d["page_size"], 12)

    def test_bad_page_size_falls_back_to_default(self):
        for bad in ("abc", "0", "-5", ""):
            d = self.data(self.get("job-list", f"?page_size={bad}"))
            self.assertEqual(len(d["results"]), 10, bad)

    def test_page_that_does_not_exist_is_a_clean_404(self):
        for bad in ("99", "0", "abc"):
            r = self.get("job-list", f"?page={bad}")
            body = r.json()
            self.assertEqual(r.status_code, 404, bad)
            self.assertIs(body["success"], False)
            self.assertEqual(body["error_code"], "not_found")

    def test_empty_result_is_a_valid_empty_page(self):
        d = self.data(self.get("job-list", "?search=nothing-matches-this"))
        self.assertEqual((d["count"], d["results"]), (0, []))


class CursorTests(Base):
    def setUp(self):
        super().setUp()
        self.make_jobs(25)
        self.login(self.cand)

    def walk(self, query="?page_size=10"):
        seen, url, pages = [], reverse("job-feed") + query, 0
        while url:
            d = self.data(self.client.get(url))
            seen += [x["id"] for x in d["results"]]
            url, pages = d["next"], pages + 1
        return seen, pages

    def test_cursor_shape_has_no_count(self):
        d = self.data(self.get("job-feed", "?page_size=10"))
        self.assertEqual(set(d), {"page_size", "next", "previous", "results"})
        self.assertEqual(len(d["results"]), 10)
        self.assertIn("cursor=", d["next"])

    def test_cursor_walk_gives_every_row_once_newest_first(self):
        seen, pages = self.walk()
        self.assertEqual((len(seen), pages), (25, 3))
        self.assertEqual(len(set(seen)), 25)
        self.assertEqual(seen, sorted(seen, reverse=True))    # same timestamps -> id order

    def test_new_row_between_pages_causes_no_duplicate(self):
        first = self.ids(self.get("job-feed", "?page_size=10"))
        d = self.data(self.get("job-feed", "?page_size=10"))
        self.make_jobs(3)                       # new jobs arrive while the user scrolls
        second = [x["id"] for x in self.data(self.client.get(d["next"]))["results"]]
        self.assertFalse(set(first) & set(second))

    def test_cursor_is_stable_when_all_timestamps_tie(self):
        """Coarse clocks (Windows) give many jobs the exact same posted_at.
        The feed must still never repeat or skip a job."""
        same = timezone.now()
        Job.objects.update(posted_at=same)
        first = self.ids(self.get("job-feed", "?page_size=10"))
        d = self.data(self.get("job-feed", "?page_size=10"))
        new = self.make_jobs(3)
        Job.objects.update(posted_at=same)      # the new rows tie as well
        second = [x["id"] for x in self.data(self.client.get(d["next"]))["results"]]
        self.assertFalse(set(first) & set(second))
        self.assertEqual(len(first), 10)

    def test_cursor_works_with_filters_and_search(self):
        self.make_jobs(4, title="Django Dev", location="Pune")
        seen, _ = self.walk("?page_size=3&search=django&location=pune")
        self.assertEqual(len(seen), 4)

    def test_bad_cursor_is_404_in_standard_format(self):
        r = self.client.get(reverse("job-feed") + "?cursor=garbage")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error_code"], "not_found")


# ------------------------------------------------------------------- filters
class JobFilterTests(Base):
    def setUp(self):
        super().setUp()
        self.make_jobs(2, title="Python Dev", location="Kochi", min_experience=0)
        self.make_jobs(2, title="Java Dev", location="Pune", min_experience=3)
        self.make_jobs(1, employer=self.emp2.employer_profile, title="Go Dev",
                       location="Kochi Infopark", min_experience=5)
        self.make_jobs(3, title="Closed Job", status="closed")
        self.login(self.cand)

    def count(self, query):
        return self.data(self.get("job-list", query))["count"]

    def test_closed_jobs_never_appear_in_public_list(self):
        self.assertEqual(self.count(""), 5)

    def test_location_filter_is_partial_and_case_insensitive(self):
        self.assertEqual(self.count("?location=kochi"), 3)
        self.assertEqual(self.count("?location=PUNE"), 2)

    def test_company_filter(self):
        self.assertEqual(self.count("?company=other"), 1)

    def test_experience_range(self):
        self.assertEqual(self.count("?experience_from=3"), 3)
        self.assertEqual(self.count("?experience_to=2"), 2)
        self.assertEqual(self.count("?experience_from=3&experience_to=4"), 2)

    def test_reversed_ranges_are_400(self):
        for q in ("?experience_from=5&experience_to=1", "?posted_after=2026-12-01&posted_before=2026-01-01"):
            r = self.get("job-list", q)
            body = r.json()
            self.assertEqual(r.status_code, 400, q)
            self.assertEqual(body["error_code"], "validation_error")
            self.assertTrue(body["errors"])

    def test_date_filters_use_whole_days(self):
        old = Job.objects.filter(title="Java Dev")
        old.update(posted_at=timezone.now() - timedelta(days=40))
        today = timezone.localdate()
        self.assertEqual(self.count(f"?posted_after={today}"), 3)
        cutoff = (today - timedelta(days=10)).isoformat()
        self.assertEqual(self.count(f"?posted_before={cutoff}"), 2)
        # a job posted today is included when posted_before is today (end of day)
        self.assertEqual(self.count(f"?posted_before={today}"), 5)

    def test_bad_date_and_number_are_400_not_500(self):
        for q in ("?posted_after=yesterday", "?posted_after=2026-13-45", "?experience_from=abc"):
            r = self.get("job-list", q)
            self.assertEqual(r.status_code, 400, q)
            self.assertEqual(r.json()["error_code"], "validation_error")

    def test_filters_combine(self):
        self.assertEqual(self.count("?location=kochi&experience_to=1"), 2)

    def test_unknown_query_params_are_ignored(self):
        self.assertEqual(self.count("?color=red"), 5)

    def test_filters_run_before_pagination(self):
        d = self.data(self.get("job-list", "?location=kochi&page_size=2"))
        self.assertEqual((d["count"], len(d["results"]), d["total_pages"]), (3, 2, 2))

    def test_employer_status_filter_and_isolation(self):
        self.login(self.emp)
        d = self.data(self.get("employer-jobs"))
        self.assertEqual(d["count"], 7)                        # own open + closed, not Other Corp's
        self.assertEqual(self.data(self.get("employer-jobs", "?status=closed"))["count"], 3)
        self.assertEqual(self.data(self.get("employer-jobs", "?status=open"))["count"], 4)
        r = self.get("employer-jobs", "?status=banana")
        self.assertEqual(r.status_code, 400)

    def test_filter_cannot_expose_another_employers_jobs(self):
        self.login(self.emp)
        self.assertEqual(self.data(self.get("employer-jobs", "?company=other"))["count"], 0)
        self.assertEqual(self.data(self.get("employer-jobs", "?employer=" + str(self.emp2.employer_profile.pk)))["count"], 7)


class ApplicationFilterTests(Base):
    def setUp(self):
        super().setUp()
        self.job = self.make_jobs(1, title="Backend")[0]
        self.cands = []
        for i, (st, score) in enumerate([("applied", 40), ("shortlisted", 70), ("hired", 90), ("rejected", 20)]):
            u = User.objects.create_user(email=f"cc{i}@z.com", password=self.pw, role=Role.CANDIDATE)
            cp = u.candidate_profile
            cp.skills = "python, django" if i % 2 == 0 else "java"
            cp.save()
            Application.objects.create(job=self.job, candidate=cp, status=st, ats_score=score)
            self.cands.append(u)

    def applicants(self, query=""):
        return self.get("job-applicants", query, self.job.pk)

    def test_employer_filters(self):
        self.login(self.emp)
        self.assertEqual(self.data(self.applicants())["count"], 4)
        self.assertEqual(self.data(self.applicants("?status=shortlisted"))["count"], 1)
        self.assertEqual(self.data(self.applicants("?min_score=50"))["count"], 2)
        self.assertEqual(self.data(self.applicants("?min_score=30&max_score=80"))["count"], 2)
        self.assertEqual(self.applicants("?min_score=90&max_score=10").status_code, 400)
        self.assertEqual(self.applicants("?status=nope").status_code, 400)

    def test_order_by_score(self):
        self.login(self.emp)
        scores = [x["ats_score"] for x in self.data(self.applicants("?ordering=-ats_score"))["results"]]
        self.assertEqual(scores, [90, 70, 40, 20])

    def test_search_candidates_by_skill(self):
        self.login(self.emp)
        self.assertEqual(self.data(self.applicants("?search=django"))["count"], 2)
        self.assertEqual(self.data(self.applicants("?search=django java"))["count"], 0)   # every word must match

    def test_deactivated_candidates_are_hidden_from_employer(self):
        self.cands[0].candidate_profile.soft_delete()
        self.login(self.emp)
        self.assertEqual(self.data(self.applicants())["count"], 3)

    def test_other_employer_still_gets_404(self):
        self.login(self.emp2)
        self.assertEqual(self.applicants("?status=applied").status_code, 404)

    def test_candidate_filters_own_applications_only(self):
        self.login(self.cands[1])
        d = self.data(self.get("my-applications"))
        self.assertEqual(d["count"], 1)
        self.assertEqual(d["results"][0]["company_name"], "Zecpath Tech")
        self.assertEqual(self.data(self.get("my-applications", "?status=hired"))["count"], 0)
        self.assertEqual(self.data(self.get("my-applications", "?search=backend"))["count"], 1)
        self.assertEqual(self.data(self.get("my-applications", "?search=zecpath"))["count"], 1)


class AdminFilterTests(Base):
    def setUp(self):
        super().setUp()
        blocked = User.objects.create_user(email="blocked@z.com", password=self.pw, role=Role.CANDIDATE, phone="9111111111")
        blocked.is_active = False
        blocked.save()
        User.objects.filter(pk=self.cand.pk).update(created_at=timezone.now() - timedelta(days=60))
        self.login(self.admin)

    def test_user_filters_by_role_state_and_date(self):
        self.assertEqual(self.data(self.get("admin-users"))["count"], 5)
        self.assertEqual(self.data(self.get("admin-users", "?role=employer"))["count"], 2)
        self.assertEqual(self.data(self.get("admin-users", "?role=candidate&is_active=false"))["count"], 1)
        self.assertEqual(self.data(self.get("admin-users", "?role=admin"))["count"], 1)
        today = timezone.localdate()
        self.assertEqual(self.data(self.get("admin-users", f"?joined_before={today - timedelta(days=30)}"))["count"], 1)
        self.assertEqual(self.get("admin-users", "?role=hacker").status_code, 400)

    def test_user_search_and_ordering(self):
        self.assertEqual(self.data(self.get("admin-users", "?search=blocked"))["count"], 1)
        self.assertEqual(self.data(self.get("admin-users", "?search=9111111111"))["count"], 1)
        emails = [u["email"] for u in self.data(self.get("admin-users", "?ordering=-email"))["results"]]
        self.assertEqual(emails, sorted(emails, reverse=True))

    def test_only_whitelisted_ordering_is_used(self):
        for bad in ("password", "-is_superuser", "nonsense"):
            r = self.get("admin-users", f"?ordering={bad}")
            self.assertEqual(r.status_code, 200)          # ignored, never a 500
            self.assertNotIn("password", r.content.decode())

    def test_admin_profile_lists_filter_and_search(self):
        cp = self.cand.candidate_profile
        cp.skills, cp.location, cp.experience_years, cp.education = "python", "Kochi", 4, "BCA"
        cp.save()
        self.assertEqual(self.data(self.get("admin-candidates", "?search=python"))["count"], 1)
        self.assertEqual(self.data(self.get("admin-candidates", "?experience_from=3&location=koch"))["count"], 1)
        self.assertEqual(self.data(self.get("admin-candidates", "?experience_from=5"))["count"], 0)
        self.assertEqual(self.data(self.get("admin-employers", "?search=zecpath"))["count"], 1)
        self.assertEqual(self.data(self.get("admin-employers", "?is_verified=true"))["count"], 0)
        self.cand.candidate_profile.soft_delete()
        self.assertEqual(self.data(self.get("admin-candidates", "?deleted=true"))["count"], 1)    # old rule still works

    def test_admin_list_does_not_leak_big_resume_text(self):
        Candidate.objects.filter(pk=self.cand.candidate_profile.pk).update(resume_text="SECRET " * 100)
        self.assertNotIn("SECRET", self.get("admin-candidates").content.decode())


# -------------------------------------------------------------------- search
class SearchTests(Base):
    def setUp(self):
        super().setUp()
        self.make_jobs(1, title="Django Developer", description="Build REST APIs", location="Kochi", skills_required="python, django")
        self.make_jobs(1, title="React Developer", description="UI work", location="Remote", skills_required="react, css")
        self.make_jobs(1, employer=self.emp2.employer_profile, title="Support", description="Help users", location="Pune", skills_required="communication")
        self.login(self.cand)

    def titles(self, q):
        return sorted(x["title"] for x in self.data(self.get("job-list", q))["results"])

    def test_search_title_description_skills_location_company(self):
        self.assertEqual(self.titles("?search=django"), ["Django Developer"])
        self.assertEqual(self.titles("?search=rest apis"), ["Django Developer"])
        self.assertEqual(self.titles("?search=css"), ["React Developer"])
        self.assertEqual(self.titles("?search=pune"), ["Support"])
        self.assertEqual(self.titles("?search=other corp"), ["Support"])

    def test_search_is_case_insensitive_and_needs_every_word(self):
        self.assertEqual(self.titles("?search=DJANGO"), ["Django Developer"])
        self.assertEqual(self.titles("?search=django kochi"), ["Django Developer"])
        self.assertEqual(self.titles("?search=django pune"), [])

    def test_search_plus_filter_plus_ordering(self):
        self.assertEqual(self.titles("?search=developer&location=remote"), ["React Developer"])
        r = [x["title"] for x in self.data(self.get("job-list", "?search=developer&ordering=title"))["results"]]
        self.assertEqual(r, ["Django Developer", "React Developer"])

    def test_special_characters_in_search_are_safe(self):
        for q in ("%25", "'; DROP TABLE jobs_job; --", "%5C", "_"):
            self.assertEqual(self.get("job-list", f"?search={q}").status_code, 200, q)
        self.assertEqual(Job.objects.count(), 3)


class CandidateSearchTests(Base):
    def setUp(self):
        super().setUp()
        specs = [("a", "python, django", "Kochi", 4), ("b", "python", "Pune", 1),
                 ("c", "java, spring", "Kochi", 6), ("d", "python, flask", "Kochi", 8)]
        self.users = {}
        for key, skills, loc, exp in specs:
            u = User.objects.create_user(email=f"{key}@cand.com", password=self.pw, role=Role.CANDIDATE, phone="95000000" + str(ord(key)))
            Candidate.objects.filter(user=u).update(skills=skills, location=loc, experience_years=exp, education="BCA", expected_salary=500000)
            self.users[key] = u
        self.login(self.emp)

    def test_search_by_keyword_location_and_experience(self):
        self.assertEqual(self.data(self.get("candidate-search", "?search=python"))["count"], 3)
        self.assertEqual(self.data(self.get("candidate-search", "?search=python&location=kochi"))["count"], 2)
        self.assertEqual(self.data(self.get("candidate-search", "?search=python&experience_from=5"))["count"], 1)

    def test_default_order_is_most_experienced_first(self):
        exp = [x["experience_years"] for x in self.data(self.get("candidate-search"))["results"]]
        self.assertEqual(exp, sorted(exp, reverse=True))

    def test_private_fields_are_never_returned(self):
        r = self.get("candidate-search")
        text = r.content.decode()
        for secret in ("@cand.com", "95000000", "expected_salary", "resume", "email", "phone", "500000"):
            self.assertNotIn(secret, text)

    def test_deactivated_and_blocked_candidates_are_hidden(self):
        self.users["a"].candidate_profile.soft_delete()
        User.objects.filter(pk=self.users["b"].pk).update(is_active=False)
        self.assertEqual(self.data(self.get("candidate-search", "?search=python"))["count"], 1)

    def test_only_employers_can_search(self):
        for u in (self.cand, self.admin):
            self.login(u)
            self.assertEqual(self.get("candidate-search").status_code, 403)
        self.client.credentials()
        self.assertEqual(self.get("candidate-search").status_code, 401)


# ----------------------------------------------------------- query counts (N+1)
class QueryCountTests(Base):
    """The number of SQL queries must NOT grow with the number of rows."""

    def count_queries(self, name, query="?page_size=50", *args):
        with CaptureQueriesContext(connection) as q:
            r = self.get(name, query, *args)
        self.assertEqual(r.status_code, 200, r.content)
        return len(q), len(r.json()["data"]["results"])

    _seq = 0

    def add_applications(self, n, job):
        for _ in range(n):
            QueryCountTests._seq += 1
            u = User.objects.create_user(email=f"x{QueryCountTests._seq}@z.com", password=self.pw, role=Role.CANDIDATE)
            Application.objects.create(job=job, candidate=u.candidate_profile, ats_score=50)

    def assertFlat(self, name, grow, user, *args):
        self.login(user)
        small, rows_small = self.count_queries(name, "?page_size=50", *args)
        grow()
        big, rows_big = self.count_queries(name, "?page_size=50", *args)
        self.assertGreater(rows_big, rows_small + 5)
        self.assertEqual(small, big, f"{name}: {small} queries for {rows_small} rows, {big} for {rows_big} rows (N+1)")
        self.assertLessEqual(big, 8)

    def test_public_job_list(self):
        self.make_jobs(3)
        self.assertFlat("job-list", lambda: self.make_jobs(20, employer=self.emp2.employer_profile), self.cand)

    def test_job_feed(self):
        self.make_jobs(3)
        self.assertFlat("job-feed", lambda: self.make_jobs(20, employer=self.emp2.employer_profile), self.cand)

    def test_employer_jobs_with_application_counts(self):
        jobs = self.make_jobs(3)
        self.add_applications(2, jobs[0])

        def grow():
            for j in self.make_jobs(15):
                self.add_applications(1, j)
        self.assertFlat("employer-jobs", grow, self.emp)

    def test_candidate_applications(self):
        cp = self.cand.candidate_profile

        def add(n):
            for j in self.make_jobs(n):
                Application.objects.create(job=j, candidate=cp)
        add(3)
        self.assertFlat("my-applications", lambda: add(20), self.cand)

    def test_employer_applicants(self):
        job = self.make_jobs(1)[0]
        self.add_applications(3, job)
        self.assertFlat("job-applicants", lambda: self.add_applications(20, job), self.emp, job.pk)

    def test_admin_lists(self):
        def grow():
            for i in range(20):
                User.objects.create_user(email=f"n{i}@z.com", password=self.pw, role=Role.CANDIDATE)
        self.assertFlat("admin-candidates", grow, self.admin)

    def test_candidate_search(self):
        def grow():
            for i in range(20):
                User.objects.create_user(email=f"s{i}@z.com", password=self.pw, role=Role.CANDIDATE)
        self.assertFlat("candidate-search", grow, self.emp)


# --------------------------------------------------------------- index usage
class IndexUsageTests(Base):
    def plan(self, qs):
        sql, params = qs.query.sql_with_params()
        with connection.cursor() as c:
            c.execute("EXPLAIN QUERY PLAN " + sql, params)
            return " | ".join(row[-1] for row in c.fetchall())

    def setUp(self):
        super().setUp()
        if connection.vendor != "sqlite":
            self.skipTest("plan text below is SQLite specific")
        self.make_jobs(400)
        Job.objects.filter(pk__lt=Job.objects.order_by("pk")[100].pk).update(status="closed")
        with connection.cursor() as c:
            c.execute("ANALYZE")

    def test_public_list_uses_the_status_date_index_and_no_extra_sort(self):
        plan = self.plan(Job.objects.filter(status="open").order_by("-posted_at", "-id")[:10])
        self.assertIn("job_status_posted_idx", plan)
        self.assertNotIn("TEMP B-TREE", plan)

    def test_date_filter_is_a_range_that_can_use_the_index(self):
        from apps.core.filters import start_of_day
        since = start_of_day(timezone.localdate() - timedelta(days=7))
        plan = self.plan(Job.objects.filter(status="open", posted_at__gte=since).order_by("-posted_at", "-id")[:10])
        self.assertIn("job_status_posted_idx", plan)

    def test_employer_list_uses_employer_index(self):
        plan = self.plan(Job.objects.filter(employer=self.emp.employer_profile).order_by("-posted_at", "-id")[:10])
        self.assertIn("job_employer_posted_idx", plan)

    def test_leading_wildcard_search_cannot_use_an_index(self):
        plan = self.plan(Job.objects.filter(title__icontains="job").order_by("-posted_at")[:10])
        self.assertNotIn("USING INDEX", plan.replace("USING INTEGER PRIMARY KEY", ""))
