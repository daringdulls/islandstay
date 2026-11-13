from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.shortcuts import redirect, render

from .forms import EmailLoginForm, SignupForm


class EmailLoginView(LoginView):
    form_class = EmailLoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def signup(request):
    if request.user.is_authenticated:
        return redirect("directory:dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        nxt = request.POST.get("next") or request.GET.get("next")
        from django.utils.http import url_has_allowed_host_and_scheme

        if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
            messages.success(request, "Welcome to Island Stay! Now tell us about your business.")
            return redirect(nxt)
        messages.success(request, "Welcome to Island Stay! Now add your property or service — our team reviews every listing before it goes live.")
        return redirect("directory:listing_create")
    from directory.models import Island

    islands = Island.objects.filter(is_published=True).select_related("atoll").order_by("name")
    return render(request, "accounts/signup.html", {"form": form, "next": request.GET.get("next", ""), "islands": islands})


class OwnerWelcomeView(PasswordResetConfirmView):
    """The invite link from the team: the owner chooses a password, is signed in, and lands on their dashboard."""
    template_name = "accounts/welcome.html"
    post_reset_login = True
    post_reset_login_backend = "accounts.backends.CaseInsensitiveEmailBackend"
    success_url = reverse_lazy("directory:dashboard")

    def form_valid(self, form):
        messages.success(self.request, "Welcome to Island Stay! Your password is set. Here are your listings.")
        return super().form_valid(form)
