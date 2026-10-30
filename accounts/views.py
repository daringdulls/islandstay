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
        messages.success(request, "Welcome to IslandStay! Now add your property or service — our team reviews every listing before it goes live.")
        return redirect("directory:listing_create")
    return render(request, "accounts/signup.html", {"form": form})
