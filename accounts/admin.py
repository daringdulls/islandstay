from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "first_name", "last_name", "business", "listing_count", "is_staff", "date_joined")

    @admin.display(description="Business")
    def business(self, obj):
        return getattr(getattr(obj, "profile", None), "business_name", "")

    @admin.display(description="Listings")
    def listing_count(self, obj):
        return obj.listings.count()
