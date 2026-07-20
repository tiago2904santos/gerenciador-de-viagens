from django.test import Client
from django.test.utils import override_settings
from oficios.models import Oficio

oficio = Oficio.objects.first()
with override_settings(ALLOWED_HOSTS=['*']):
    c = Client()
    resp = c.get(f'/oficios/{oficio.pk}/roteiro/')
    content = resp.content.decode('utf-8', 'ignore')
    idx = content.find('oficio-roteiro-destinos"')
    print(content[max(0, idx-100):idx+800])
