from __future__ import annotations

from datetime import date

from django.test import TestCase

from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor

from ..docxtpl_context import build_os_docxtpl_context
from ..forms import OrdemServicoForm
from ..models import OrdemServico


class OrdemServicoDocxtplContextTests(TestCase):
    def setUp(self):
        self.estado = Estado.objects.create(nome="PARANA", sigla="PR")
        self.cidade = Cidade.objects.create(nome="CURITIBA", estado=self.estado, uf="PR")
        self.motorista = Servidor.objects.create(nome="MOTORISTA TESTE")
        self.tecnico = Servidor.objects.create(nome="TECNICO TESTE")
        self.montagem = Servidor.objects.create(nome="APOIO MONTAGEM")
        self.escolta = Servidor.objects.create(nome="APOIO ESCOLTA")
        self.apoio_extra = Servidor.objects.create(nome="APOIO EXTRA")
        self.coordenador = Servidor.objects.create(nome="COORDENADOR CERIMONIAL")
        self.apoio = Servidor.objects.create(nome="APOIO CERIMONIAL")
        self.preparacao = Servidor.objects.create(nome="APOIO PREPARACAO")

    def _ordem(self, tipo):
        ordem = OrdemServico.objects.create(
            tipo_necessidade=tipo,
            data_evento_inicio=date(2026, 8, 10),
            data_evento_fim=date(2026, 8, 12),
            motivo="evento institucional",
            motorista_equipe=self.motorista,
            tecnico_equipe=self.tecnico,
            apoio_montagem=self.montagem,
            apoio_escolta=self.escolta,
            coordenador_cerimonial=self.coordenador,
            apoio_cerimonial=self.apoio,
            apoio_preparacao=self.preparacao,
        )
        ordem.destinos.set([self.cidade])
        ordem.servidores.set([
            self.motorista,
            self.tecnico,
            self.montagem,
            self.escolta,
            self.apoio_extra,
        ])
        return ordem

    def test_caminhao_descreve_competencias_por_funcao_e_dois_dias(self):
        ordem = self._ordem(OrdemServico.TIPO_CAMINHAO)
        ordem.funcoes_servidores = {
            str(self.motorista.pk): OrdemServico.FUNCAO_CONDUCAO,
            str(self.tecnico.pk): OrdemServico.FUNCAO_TECNICO,
            str(self.montagem.pk): OrdemServico.FUNCAO_APOIO,
            str(self.escolta.pk): OrdemServico.FUNCAO_APOIO,
        }
        ordem.save(update_fields=["funcoes_servidores"])

        ctx = build_os_docxtpl_context(ordem)

        self.assertEqual(ctx["referencia"], "Deslocamento - Caminhão de apoio")
        self.assertEqual(len(ctx["competencias_equipe"]), 3)
        self.assertIn("Motorista Teste – conduzir a Unidade Móvel (caminhão)", ctx["competencias_equipe"][0])
        self.assertIn("Tecnico Teste – prestar apoio técnico", ctx["competencias_equipe"][1])
        self.assertIn("Apoio Montagem e Apoio Escolta: realizar a escolta", ctx["competencias_equipe"][2])
        self.assertNotIn("Apoio Extra", " ".join(ctx["competencias_equipe"]))
        self.assertIn("dois dias de antecedência", " ".join(ctx["justificativas"]))
        self.assertIn("dois dias posteriores", " ".join(ctx["justificativas"]))

    def test_caminhao_sem_funcao_gera_texto_padrao(self):
        ctx = build_os_docxtpl_context(self._ordem(OrdemServico.TIPO_CAMINHAO))

        self.assertEqual(ctx["referencia"], "Diligências")
        self.assertEqual(ctx["competencias_equipe"], [])
        self.assertEqual(ctx["justificativas"], [])

    def test_caminhao_tecnico_e_opcional(self):
        ordem = self._ordem(OrdemServico.TIPO_CAMINHAO)
        ordem.funcoes_servidores = {
            str(self.motorista.pk): OrdemServico.FUNCAO_CONDUCAO,
            str(self.montagem.pk): OrdemServico.FUNCAO_APOIO,
            str(self.escolta.pk): OrdemServico.FUNCAO_APOIO,
        }
        ordem.save(update_fields=["funcoes_servidores"])

        ctx = build_os_docxtpl_context(ordem)

        self.assertEqual(len(ctx["competencias_equipe"]), 2)
        self.assertNotIn("prestar apoio técnico", " ".join(ctx["competencias_equipe"]))

    def test_microonibus_nao_aplica_regra_de_dois_dias(self):
        ctx = build_os_docxtpl_context(self._ordem(OrdemServico.TIPO_MICROONIBUS))

        self.assertEqual(ctx["referencia"], "Deslocamento - Micro-ônibus")
        self.assertEqual(len(ctx["competencias_equipe"]), 4)
        self.assertIn("sem necessidade de deslocamento com dois dias de antecedência", " ".join(ctx["justificativas"]))

    def test_microonibus_descreve_competencias_por_funcao(self):
        ordem = self._ordem(OrdemServico.TIPO_MICROONIBUS)
        ordem.funcoes_servidores = {
            str(self.motorista.pk): OrdemServico.FUNCAO_CONDUCAO,
            str(self.tecnico.pk): OrdemServico.FUNCAO_TECNICO,
            str(self.montagem.pk): OrdemServico.FUNCAO_APOIO,
        }
        ordem.save(update_fields=["funcoes_servidores"])

        ctx = build_os_docxtpl_context(ordem)

        self.assertEqual(len(ctx["competencias_equipe"]), 3)
        self.assertIn("conduzir o micro-ônibus oficial", ctx["competencias_equipe"][0])
        self.assertIn("prestar suporte técnico", ctx["competencias_equipe"][1])
        self.assertIn("prestar apoio operacional", ctx["competencias_equipe"][2])

    def test_cerimonial_descreve_ida_antecipada_e_competencias(self):
        ctx = build_os_docxtpl_context(self._ordem(OrdemServico.TIPO_CERIMONIAL_ANTECIPADO))

        self.assertEqual(ctx["referencia"], "Deslocamento - Equipe de Cerimonial")
        self.assertEqual(len(ctx["competencias_equipe"]), 3)
        self.assertIn("Coordenador Cerimonial", ctx["competencias_equipe"][0])
        self.assertEqual(
            ctx["justificativas"],
            [
                "O deslocamento da equipe com dois dias de antecedência faz-se necessário, sendo o primeiro destinado ao deslocamento até o município do evento e o segundo à organização dos trabalhos, em razão da inexistência de visita técnica prévia.",
                "A permanência da equipe permitirá verificar a estrutura do local, sistema de sonorização, disposição do palco, púlpito, bandeiras, autoridades e convidados, decoração, acessos e demais aspectos logísticos, possibilitando os ajustes necessários para assegurar a adequada realização da solenidade.",
            ],
        )
        self.assertEqual(
            ctx["finalidade"],
            "A presente Ordem de Serviço tem por finalidade garantir o planejamento, a organização e a execução das atividades de Cerimonial, assegurando o cumprimento das normas de protocolo e a realização do evento institucional com eficiência e observância aos padrões da Polícia Civil do Paraná.",
        )

    def test_cerimonial_descreve_competencias_por_funcao(self):
        ordem = self._ordem(OrdemServico.TIPO_CERIMONIAL_ANTECIPADO)
        ordem.funcoes_servidores = {
            str(self.coordenador.pk): OrdemServico.FUNCAO_COORDENACAO,
            str(self.apoio.pk): OrdemServico.FUNCAO_APOIO,
            str(self.preparacao.pk): OrdemServico.FUNCAO_PREPARACAO,
        }
        ordem.servidores.set([self.coordenador, self.apoio, self.preparacao])
        ordem.save(update_fields=["funcoes_servidores"])

        ctx = build_os_docxtpl_context(ordem)

        self.assertEqual(len(ctx["competencias_equipe"]), 3)
        self.assertIn("coordenar as atividades de Cerimonial", ctx["competencias_equipe"][0])
        self.assertIn("prestar apoio às atividades de Cerimonial", ctx["competencias_equipe"][1])
        self.assertIn("auxiliar na preparação da solenidade", ctx["competencias_equipe"][2])

    def test_operacao_policial_justifica_apenas_um_dia_posterior(self):
        ctx = build_os_docxtpl_context(self._ordem(OrdemServico.TIPO_OPERACAO_RETORNO_POSTERIOR))

        self.assertEqual(ctx["referencia"], "Deslocamento - Operação policial com um dia posterior")
        self.assertEqual(len(ctx["justificativas"]), 1)
        justificativa = ctx["justificativas"][0]
        self.assertIn("A concessão de um dia posterior justifica-se", justificativa)
        self.assertIn("produção de material jornalístico durante o briefing", justificativa)
        self.assertIn("assessoria de imprensa pós-operação", justificativa)
        self.assertIn("permanência da equipe policial", justificativa)
        self.assertNotIn("ida antecipada", justificativa.lower())

    def test_form_salva_funcoes_dinamicas_dos_servidores(self):
        form = OrdemServicoForm(
            data={
                "data_evento_inicio": "2026-08-10",
                "data_evento_fim": "2026-08-12",
                "destino_estado": str(self.estado.pk),
                "destino_cidade": str(self.cidade.pk),
                "servidores": [str(self.motorista.pk), str(self.montagem.pk), str(self.escolta.pk)],
                "tipo_necessidade": OrdemServico.TIPO_CAMINHAO,
                "funcao_servidor_%s" % self.motorista.pk: OrdemServico.FUNCAO_CONDUCAO,
                "funcao_servidor_%s" % self.montagem.pk: OrdemServico.FUNCAO_APOIO,
                "funcao_servidor_%s" % self.escolta.pk: OrdemServico.FUNCAO_APOIO,
                "motivo": "evento institucional",
            }
        )

        self.assertTrue(form.is_valid(), form.errors.as_data())
        ordem = form.save()

        self.assertEqual(
            ordem.funcoes_servidores,
            {
                str(self.motorista.pk): OrdemServico.FUNCAO_CONDUCAO,
                str(self.montagem.pk): OrdemServico.FUNCAO_APOIO,
                str(self.escolta.pk): OrdemServico.FUNCAO_APOIO,
            },
        )

    def test_form_salva_funcoes_dinamicas_do_microonibus(self):
        form = OrdemServicoForm(
            data={
                "data_evento_inicio": "2026-08-10",
                "data_evento_fim": "2026-08-12",
                "destino_estado": str(self.estado.pk),
                "destino_cidade": str(self.cidade.pk),
                "servidores": [str(self.motorista.pk), str(self.tecnico.pk)],
                "tipo_necessidade": OrdemServico.TIPO_MICROONIBUS,
                "funcao_servidor_%s" % self.motorista.pk: OrdemServico.FUNCAO_CONDUCAO,
                "funcao_servidor_%s" % self.tecnico.pk: OrdemServico.FUNCAO_TECNICO,
                "motivo": "evento institucional",
            }
        )

        self.assertTrue(form.is_valid(), form.errors.as_data())
        ordem = form.save()

        self.assertEqual(
            ordem.funcoes_servidores,
            {
                str(self.motorista.pk): OrdemServico.FUNCAO_CONDUCAO,
                str(self.tecnico.pk): OrdemServico.FUNCAO_TECNICO,
            },
        )

    def test_form_salva_funcoes_dinamicas_do_cerimonial(self):
        form = OrdemServicoForm(
            data={
                "data_evento_inicio": "2026-08-10",
                "data_evento_fim": "2026-08-12",
                "destino_estado": str(self.estado.pk),
                "destino_cidade": str(self.cidade.pk),
                "servidores": [str(self.coordenador.pk), str(self.apoio.pk), str(self.preparacao.pk)],
                "tipo_necessidade": OrdemServico.TIPO_CERIMONIAL_ANTECIPADO,
                "funcao_servidor_%s" % self.coordenador.pk: OrdemServico.FUNCAO_COORDENACAO,
                "funcao_servidor_%s" % self.apoio.pk: OrdemServico.FUNCAO_APOIO,
                "funcao_servidor_%s" % self.preparacao.pk: OrdemServico.FUNCAO_PREPARACAO,
                "motivo": "evento institucional",
            }
        )

        self.assertTrue(form.is_valid(), form.errors.as_data())
        ordem = form.save()

        self.assertEqual(
            ordem.funcoes_servidores,
            {
                str(self.coordenador.pk): OrdemServico.FUNCAO_COORDENACAO,
                str(self.apoio.pk): OrdemServico.FUNCAO_APOIO,
                str(self.preparacao.pk): OrdemServico.FUNCAO_PREPARACAO,
            },
        )
