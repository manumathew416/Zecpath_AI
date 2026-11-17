from django.urls import path

from . import profile_views as v

urlpatterns = [
    # own profile (self only)
    path("candidate/profile/", v.CandidateOwnProfileView.as_view(), name="candidate-profile"),
    path("employer/profile/", v.EmployerOwnProfileView.as_view(), name="employer-profile"),

    # search (employers)
    path("employer/candidates/search/", v.CandidateSearchView.as_view(), name="candidate-search"),

    # admin override
    path("admin/candidates/", v.AdminCandidateListView.as_view(), name="admin-candidates"),
    path("admin/candidates/<int:pk>/", v.AdminCandidateDetailView.as_view(), name="admin-candidate-detail"),
    path("admin/candidates/<int:pk>/restore/", v.AdminCandidateRestoreView.as_view(), name="admin-candidate-restore"),
    path("admin/employers/", v.AdminEmployerListView.as_view(), name="admin-employers"),
    path("admin/employers/<int:pk>/", v.AdminEmployerDetailView.as_view(), name="admin-employer-detail"),
    path("admin/employers/<int:pk>/restore/", v.AdminEmployerRestoreView.as_view(), name="admin-employer-restore"),
]
