"""O comando que leva os registros antigos para a caixa que a máscara exige.

A máscara do `NOVO-53` vale do próximo salvamento em diante. Tudo que já estava
gravado continua na caixa em que foi digitado, e o sistema passa a ter duas
populações no mesmo campo. `normalizar_maiusculas` fecha essa diferença.

O que estes testes protegem, em ordem de gravidade:

  1. **`username` fora da lista.** Maiusculizar o campo de login trocaria a
     chave que o Django compara byte a byte, e ninguém mais entraria no
     sistema. Foi o comando que descobriu que dois formulários mascaravam
     `username` (`NOVO-56`); o teste existe para que ele nunca migre o campo
     mesmo que a máscara volte por outro caminho.
  2. **Simulação não grava.** É o modo padrão, e ele escreve no banco de
     verdade antes de desfazer — se o `rollback` falhar, uma execução de
     leitura teria alterado a base.
  3. **Colisão de unicidade não passa.** "Reunião" e "REUNIÃO" convivem hoje;
     em maiúscula viram a mesma chave. O campo inteiro fica de fora.
"""

from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from eventos.models import TipoEvento
from usuarios.models import AreaTrabalho


def rodar(*args) -> str:
    saida = StringIO()
    call_command("normalizar_maiusculas", *args, stdout=saida, stderr=saida)
    return saida.getvalue()


class NormalizarMaiusculasTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área de Teste", sigla="AT")

    # ----------------------------------------------------------- descoberta
    def test_username_nao_esta_entre_os_campos_a_migrar(self):
        """A trava que existe para o sistema continuar autenticando."""
        saida = rodar()

        self.assertNotIn("auth.User.username", saida)

    def test_campo_reservado_mascarado_e_recusado_e_denunciado(self):
        """Vale mesmo com o formulário errado — que é o estado de onde viemos.

        O teste acima passa porque os formulários foram corrigidos no
        `NOVO-56`. Este simula a volta do defeito: põe a máscara em `username`
        e exige que o comando (a) não migre o campo e (b) diga em voz alta que
        o formulário está errado, em vez de pular em silêncio.
        """
        from usuarios.forms import UsuarioEditForm

        original = UsuarioEditForm.__init__

        def com_defeito(self, *args, **kwargs):
            original(self, *args, **kwargs)
            self.fields["username"].widget.attrs["data-mask"] = "upper"

        usuario = get_user_model().objects.create_user(
            username="adm.tsantos",
            password="x",
        )
        UsuarioEditForm.__init__ = com_defeito
        try:
            saida = rodar("--commit")
        finally:
            UsuarioEditForm.__init__ = original

        self.assertIn("campos reservados mascarados por engano", saida)
        self.assertIn("UsuarioEditForm.username", saida)
        usuario.refresh_from_db()
        self.assertEqual(usuario.username, "adm.tsantos")

    def test_descobre_campo_de_modelo_com_mascara(self):
        saida = rodar()

        self.assertIn("eventos.TipoEvento.nome", saida)

    def test_campo_inexistente_e_avisado_e_nao_silenciado(self):
        saida = rodar("--campo", "eventos.TipoEvento.inexistente")

        self.assertIn("não é campo de modelo com máscara", saida)

    # -------------------------------------------------------------- escrita
    def test_simulacao_nao_grava(self):
        tipo = TipoEvento.objects.create(area=self.area, nome="Reunião Técnica")

        saida = rodar()

        self.assertIn("Simulação", saida)
        tipo.refresh_from_db()
        self.assertEqual(tipo.nome, "Reunião Técnica")

    def test_commit_maiusculiza(self):
        tipo = TipoEvento.objects.create(area=self.area, nome="Reunião Técnica")

        rodar("--commit")

        tipo.refresh_from_db()
        self.assertEqual(tipo.nome, "REUNIÃO TÉCNICA")

    def test_commit_nao_toca_no_que_ja_esta_em_maiuscula(self):
        tipo = TipoEvento.objects.create(area=self.area, nome="JÁ ESTÁ ASSIM")
        antes = tipo.atualizado_em if hasattr(tipo, "atualizado_em") else None

        rodar("--commit")

        tipo.refresh_from_db()
        self.assertEqual(tipo.nome, "JÁ ESTÁ ASSIM")
        if antes is not None:
            # `update` em vez de `save()`: a data de atualização é do usuário,
            # não da migração.
            self.assertEqual(tipo.atualizado_em, antes)

    def test_filtro_por_campo_restringe_a_escrita(self):
        tipo = TipoEvento.objects.create(area=self.area, nome="Reunião")
        area = AreaTrabalho.objects.create(nome="Outra Área", sigla="OA")

        rodar("--campo", "eventos.TipoEvento.nome", "--commit")

        tipo.refresh_from_db()
        area.refresh_from_db()
        self.assertEqual(tipo.nome, "REUNIÃO")
        self.assertEqual(area.nome, "Outra Área")

    # ------------------------------------------------------------- colisão
    def test_colisao_de_unicidade_bloqueia_o_campo_inteiro(self):
        """Duas linhas que viram a mesma chave param a migração do campo.

        O bloqueio é por campo, não por linha: migrar as outras e deixar o par
        para trás daria um campo meio migrado, que é o pior dos dois estados.
        """
        antigo = TipoEvento.objects.create(area=self.area, nome="Reunião")
        novo = TipoEvento.objects.create(area=self.area, nome="REUNIÃO")

        saida = rodar("--campo", "eventos.TipoEvento.nome", "--commit")

        self.assertIn("BLOQUEADO", saida)
        self.assertIn("bloqueados por unicidade", saida)
        antigo.refresh_from_db()
        novo.refresh_from_db()
        self.assertEqual(antigo.nome, "Reunião")
        self.assertEqual(novo.nome, "REUNIÃO")

    def test_colisao_num_campo_nao_impede_os_outros(self):
        """Um campo bloqueado não pode arrastar a transação inteira.

        Sem o savepoint por campo, o `IntegrityError` de `TipoEvento` desfaria
        também o que já tinha sido migrado em `AreaTrabalho`.
        """
        TipoEvento.objects.create(area=self.area, nome="Reunião")
        TipoEvento.objects.create(area=self.area, nome="REUNIÃO")

        rodar("--commit")

        self.area.refresh_from_db()
        self.assertEqual(self.area.nome, "ÁREA DE TESTE")
        self.assertEqual(
            set(
                TipoEvento.all_objects.filter(area=self.area).values_list(
                    "nome",
                    flat=True,
                ),
            ),
            {"Reunião", "REUNIÃO"},
        )
