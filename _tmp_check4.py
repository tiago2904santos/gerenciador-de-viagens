from django.test import Client
from django.test.utils import override_settings
from oficios.models import Oficio

oficio = Oficio.objects.first()
print('oficio', oficio)
with override_settings(ALLOWED_HOSTS=['*']):
    c = Client()
    if oficio:
        resp = c.get(f'/oficios/{oficio.pk}/roteiro/')
        print('STATUS', resp.status_code)
        content = resp.content.decode('utf-8', 'ignore')
        print('has sec-destinos', 'id="sec-destinos"' in content)
        print('has btn-adicionar-destino', 'id="btn-adicionar-destino"' in content)
        print('has destinos-container', 'id="destinos-container"' in content)
