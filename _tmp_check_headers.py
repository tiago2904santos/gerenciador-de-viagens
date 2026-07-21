import os
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.dev"
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import Client, RequestFactory

settings.ALLOWED_HOSTS = ["*", "testserver", "localhost", "127.0.0.1"]

User = get_user_model()
user, _ = User.objects.get_or_create(
    username="header_check_user",
    defaults={"is_staff": True, "is_superuser": True},
)
user.is_superuser = True
user.is_staff = True
user.set_password("testpass123")
user.save()

client = Client(HTTP_HOST="localhost")
assert client.login(username="header_check_user", password="testpass123")

from usuarios.models import AreaTrabalho

area = AreaTrabalho.objects.first()
session = client.session
if area:
    session["area_id"] = area.pk
    session.save()

checks = [
    ("/oficios/", "cards"),
    ("/cadastros/servidores/", "standard"),
    ("/cadastros/estados/", "quick_add"),
]

for url, kind in checks:
    response = client.get(url, follow=True, HTTP_HOST="localhost")
    html = response.content.decode("utf-8", errors="replace")
    print(f"=== {kind} {url} status={response.status_code} ===")
    print("has list-header:", "list-header" in html)
    print("page-header-band:", "page-header-band" in html)
    print("list-header__title:", "list-header__title" in html)
    print("quick-add-footer-button:", "quick-add-footer-button" in html)
    print("oficios-rail:", "oficios-rail" in html)
    print("oficios-filter-bar:", "oficios-filter-bar" in html)
    print("list-header.css:", "list-header.css" in html)
    if kind == "quick_add":
        print("list-header--quick-add:", "list-header--quick-add" in html)
        print("data-quick-add-toggle:", "data-quick-add-toggle" in html)
    idx = html.find("list-header")
    if idx >= 0:
        print("snippet:", html[idx : idx + 220].replace("\n", " "))
    else:
        print("redirects:", response.redirect_chain)
        print("has login form:", 'name="username"' in html or "Entrar" in html)
    print()

factory = RequestFactory()
request = factory.get("/oficios/")
request.user = user
html_filters = render_to_string(
    "components/ui/headers/header_stack_filters.html",
    {
        "request": request,
        "title": "Ofícios",
        "eyebrow": "OFÍCIOS",
        "advanced": True,
        "form_action": "/oficios/",
        "search_placeholder": "Buscar",
        "q": "",
        "hide_date_filter": True,
    },
    request=request,
)
print("=== direct advanced header ===")
print("list-header:", 'class="list-header' in html_filters)
print("page-header-band:", "page-header-band" in html_filters)
print("oficios-rail:", "oficios-rail" in html_filters)
print("list-header__filters--advanced:", "list-header__filters--advanced" in html_filters)
print("snippet:", html_filters[:280].replace("\n", " "))
