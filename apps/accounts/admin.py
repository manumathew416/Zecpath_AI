from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Candidate, Employer, Role, User


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "phone", "role")


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class EmployerInline(admin.StackedInline):
    model = Employer
    can_delete = False


class CandidateInline(admin.StackedInline):
    model = Candidate
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreateForm
    ordering = ("-created_at",)
    list_display = ("email", "role", "phone", "is_verified", "is_active",
                    "created_at")
    list_filter = ("role", "is_verified", "is_active")
    search_fields = ("email", "phone")
    readonly_fields = ("last_login", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("phone", "role")}),
        ("Status", {"fields": ("is_active", "is_verified", "is_staff",
                               "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "phone", "role",
                           "password1", "password2")}),
    )
    actions = ["mark_verified"]

    def get_inlines(self, request, obj=None):
        # role view: show the matching profile on a user's page
        if obj is None:
            return []
        if obj.role == Role.EMPLOYER:
            return [EmployerInline]
        if obj.role == Role.CANDIDATE:
            return [CandidateInline]
        return []

    @admin.action(description="Mark selected users as verified")
    def mark_verified(self, request, queryset):
        for user in queryset:
            user.is_verified = True
            user.save()          # save() fires the signal, which syncs the profile


admin.site.register(Employer)
admin.site.register(Candidate)