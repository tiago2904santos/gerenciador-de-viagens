import json

from django.test import RequestFactory, TestCase

from core.autosave import AutosavePayloadError, parse_autosave_payload


class ParseAutosavePayloadTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.payload = {
            "object_id": "1",
            "form_id": "f",
            "model": "oficio",
            "dirty_fields": ["motivo"],
            "fields": {"motivo": "novo texto"},
            "snapshots": {},
        }

    def test_aceita_corpo_json_do_fetch_normal(self):
        request = self.factory.post(
            "/x/", data=json.dumps(self.payload), content_type="application/json"
        )
        parsed = parse_autosave_payload(request, expected_model="oficio")
        self.assertEqual(parsed.fields, {"motivo": "novo texto"})
        self.assertEqual(parsed.dirty_fields, ["motivo"])

    def test_aceita_campo_payload_do_formdata_do_sendbeacon(self):
        """sendBeacon (flush ao sair da página) não seta headers, então o JS
        envia FormData multipart com csrfmiddlewaretoken + payload em vez de
        JSON puro. parse_autosave_payload precisa entender esse formato."""
        request = self.factory.post(
            "/x/",
            data={"csrfmiddlewaretoken": "tok", "payload": json.dumps(self.payload)},
        )
        parsed = parse_autosave_payload(request, expected_model="oficio")
        self.assertEqual(parsed.fields, {"motivo": "novo texto"})
        self.assertEqual(parsed.dirty_fields, ["motivo"])

    def test_formdata_sem_payload_nao_bate_com_o_modelo_esperado(self):
        request = self.factory.post("/x/", data={"csrfmiddlewaretoken": "tok"})
        with self.assertRaises(AutosavePayloadError):
            parse_autosave_payload(request, expected_model="oficio")
