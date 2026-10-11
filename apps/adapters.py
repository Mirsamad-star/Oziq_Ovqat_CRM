from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter - redirects all login/signup/logout to home (mijos.html)."""

    def get_login_redirect_url(self, request):
        return "/"

    def get_logout_redirect_url(self, request):
        return "/"

    def get_signup_redirect_url(self, request):
        return "/"


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter for Google/GitHub login."""

    def get_login_redirect_url(self, request):
        return "/"

    def get_connect_redirect_url(self, request, socialaccount):
        return "/"

    def populate_user(self, request, sociallogin, data):
        """Extract name from Google/GitHub profile data."""
        user = super().populate_user(request, sociallogin, data)
        extra = sociallogin.account.extra_data or {}

        # Google / GitHub name extraction
        full_name = extra.get("name") or ""
        given_name = extra.get("given_name") or data.get("first_name") or ""
        family_name = extra.get("family_name") or data.get("last_name") or ""

        # GitHub: name is full name in "name" field
        if not given_name and full_name:
            parts = full_name.strip().split(" ", 1)
            given_name = parts[0]
            if len(parts) > 1 and not family_name:
                family_name = parts[1]

        if not user.first_name:
            if given_name:
                user.first_name = given_name
            elif full_name:
                user.first_name = full_name

        if not user.last_name and family_name:
            user.last_name = family_name

        # If username is email-based, clean it up
        if user.username and "@" in user.username:
            user.username = user.username.split("@")[0]

        return user

    def pre_social_login(self, request, sociallogin):
        """Link social account to existing user with same email."""
        # Already linked - skip
        if sociallogin.is_existing:
            return

        extra = sociallogin.account.extra_data or {}
        email = extra.get("email") or getattr(sociallogin.user, "email", None)

        if email:
            try:
                existing_user = User.objects.get(email__iexact=email)
                # Link social account to existing user with the same email
                sociallogin.connect(request, existing_user)

                # Update name if empty
                name = extra.get("name") or extra.get("given_name")
                if name and not existing_user.first_name:
                    existing_user.first_name = name.strip().split()[0]
                    existing_user.save(update_fields=["first_name"])
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                pass
