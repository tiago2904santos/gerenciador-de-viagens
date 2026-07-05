from datetime import date

from django.test import SimpleTestCase

from integracoes.google_drive import naming


class _Servidor:
    def __init__(self, nome):
        self.nome = nome


class _TiposManager:
    def __init__(self, nomes):
        self._nomes = nomes

    def values_list(self, field, flat=False):
        return list(self._nomes)


class _Evento:
    def __init__(self, **kw):
        self.pk = 1
        tipos_nomes = kw.pop("tipos_nomes", None)
        self.__dict__.update(kw)
        if tipos_nomes is not None:
            self.tipos = _TiposManager(tipos_nomes)


class _Oficio:
    def __init__(self, numero=None, ano=None, protocolo="", evento=None):
        self.numero = numero
        self.ano = ano
        self.protocolo = protocolo
        self.evento = evento


class NamingTests(SimpleTestCase):
    def test_num_doc(self):
        self.assertEqual(naming.num_doc(1, 2026), "01-2026")
        self.assertEqual(naming.num_doc(1, 2026, width=3), "001-2026")
        self.assertEqual(naming.num_doc(None, 2026), "")

    def test_primeiro_nome_title_case(self):
        self.assertEqual(naming.primeiro_nome(_Servidor("TIAGO SANTOS")), "Tiago")
        self.assertEqual(naming.primeiro_nome(_Servidor("")), "")

    def test_nomes_servidores(self):
        a, b, c = _Servidor("ANA"), _Servidor("BRUNO"), _Servidor("CARLA")
        self.assertEqual(naming.nomes_servidores([a]), "Ana")
        self.assertEqual(naming.nomes_servidores([a, b]), "Ana e Bruno")
        self.assertEqual(naming.nomes_servidores([a, b, c]), "Ana, Bruno e Carla")

    def test_sanitize_troca_barra_por_hifen(self):
        self.assertEqual(naming.sanitize_drive_name("Ofício 01/2026"), "Ofício 01-2026")
        self.assertEqual(naming.sanitize_drive_name('a:b"c|d?e*f'), "abcdef")
        self.assertEqual(naming.sanitize_drive_name("   "), "documento")

    def test_periodo_pasta_mesmo_mes(self):
        ev = _Evento(data_inicio=date(2026, 7, 22), data_fim=date(2026, 7, 23))
        self.assertEqual(naming.periodo_pasta(ev), "22 a 23 jul 2026")

    def test_periodo_pasta_um_dia(self):
        ev = _Evento(data_inicio=date(2026, 7, 22), data_fim=date(2026, 7, 22))
        self.assertEqual(naming.periodo_pasta(ev), "22 jul 2026")

    def test_pasta_evento(self):
        ev = _Evento(
            tipos_nomes=["PCPR na Comunidade"],
            titulo="",
            destino_cidade="Maringá",
            data_inicio=date(2026, 7, 22),
            data_fim=date(2026, 7, 23),
        )
        self.assertEqual(naming.pasta_evento(ev), "PCPR na Comunidade - Maringá - 22 a 23 jul 2026")

    def test_pasta_evento_com_multiplos_tipos(self):
        ev = _Evento(
            tipos_nomes=["PCPR na Comunidade", "Justiça no Bairro"],
            titulo="",
            destino_cidade="Maringá",
            data_inicio=date(2026, 7, 22),
            data_fim=date(2026, 7, 23),
        )
        self.assertEqual(
            naming.pasta_evento(ev),
            "PCPR na Comunidade, Justiça no Bairro - Maringá - 22 a 23 jul 2026",
        )

    def test_pasta_oficio(self):
        of = _Oficio(numero=1, ano=2026, protocolo="123456789")
        nome = naming.pasta_oficio(of, [_Servidor("ANA"), _Servidor("BRUNO")])
        self.assertEqual(nome, "Ofício 01 protocolo 12.345.678-9 Ana e Bruno")

    def test_pasta_oficio_com_destino(self):
        of = _Oficio(numero=1, ano=2026, protocolo="123456789")
        nome = naming.pasta_oficio(of, [_Servidor("ANA"), _Servidor("BRUNO")], "Maringá")
        self.assertEqual(nome, "Ofício 01 protocolo 12.345.678-9 Ana e Bruno (Maringá)")

    def test_capitalizar_cidade(self):
        self.assertEqual(naming.capitalizar_cidade("MARINGÁ"), "Maringá")
        self.assertEqual(naming.capitalizar_cidade("SÃO JOSÉ DOS PINHAIS"), "São José dos Pinhais")
        self.assertEqual(naming.capitalizar_cidade(""), "")

    def test_nome_oficio(self):
        of = _Oficio(numero=1, ano=2026, protocolo="123456789")
        nome = naming.nome_oficio(of, [_Servidor("ANA"), _Servidor("BRUNO")], "Maringá")
        self.assertEqual(
            nome, "Ofício 01-2026 protocolo 12.345.678-9 Ana e Bruno (Maringá).pdf"
        )

    def test_nome_termo(self):
        of = _Oficio(numero=1, ano=2026, protocolo="123456789")
        nome = naming.nome_termo(of, _Servidor("ANA"), "Maringá")
        self.assertEqual(nome, "Termo de autorização 01-2026 protocolo 12.345.678-9 Ana (Maringá).pdf")

    def test_nome_os_usa_tres_digitos(self):
        of = _Oficio(numero=1, ano=2026, protocolo="123456789")
        nome = naming.nome_os(of, [_Servidor("ANA")], "Maringá")
        self.assertTrue(nome.startswith("Ordem de serviço 001-2026"))

    def test_nome_anexo_solicitacao(self):
        of = _Oficio(numero=1, ano=2026, protocolo="123456789")
        nome = naming.nome_anexo_solicitacao(of, _Servidor("ANA"), "123456", "Maringá", "pdf")
        self.assertEqual(
            nome,
            "Anexo solicitação 123456 Ofício 01-2026 protocolo 12.345.678-9 Ana (Maringá).pdf",
        )

    def test_pasta_prestacao_servidor(self):
        self.assertEqual(naming.pasta_prestacao_servidor(_Servidor("ANA SILVA")), "Prestação Ana")
