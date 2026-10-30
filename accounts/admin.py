from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from unfold.admin import ModelAdmin, StackedInline
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import Profile

User = get_user_model()


class ProfileInline(StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Business profile"


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    inlines = [ProfileInline]
    list_display = ("account", "business", "listing_count", "role", "date_joined")
    list_display_links = ("account",)
    list_filter = ("is_staff", "is_superuser", "is_active")
    list_filter_submit = True

    @display(description="Account", header=True, ordering="username")
    def account(self, obj):
        name = obj.get_full_name() or obj.username
        return [name, obj.email or obj.username, "".join(p[0] for p in name.split()[:2]).upper()]

    @display(description="Business")
    def business(self, obj):
        return getattr(getattr(obj, "profile", None), "business_name", "") or "–"

    @display(description="Listings")
    def listing_count(self, obj):
        return obj.listings.count()

    @display(description="Role", label={"admin": "danger", "staff": "warning", "business": "info"})
    def role(self, obj):
        if obj.is_superuser:
            return "admin", "Administrator"
        if obj.is_staff:
            return "staff", "Staff"
        return "business", "Business owner"


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
