from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
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
    return render(request, "accounts/signup.html", {"form": form, "next": request.GET.get("next", "")})
