from django.db import migrations

# Catálogo oficial portado do legado (eventos/services/plano_trabalho_domain.py).
# Cada atividade carrega a meta exibida no documento e o recurso necessário associado.
ATIVIDADES = [
    {
        "codigo": "CIN",
        "nome": "Confecção da Carteira de Identidade Nacional (CIN)",
        "meta": (
            "Ampliar o acesso ao documento oficial de identificação civil, garantindo "
            "cidadania e inclusão social à população atendida."
        ),
        "recurso_necessario": (
            "Kit de captura biométrica, estação de atendimento, conectividade e equipe "
            "técnica para triagem e emissão."
        ),
        "ordem": 10,
    },
    {
        "codigo": "BO",
        "nome": "Registro de Boletins de Ocorrência",
        "meta": (
            "Possibilitar o atendimento imediato de demandas policiais, promovendo "
            "orientação e formalização de ocorrências no próprio evento."
        ),
        "recurso_necessario": (
            "Posto de atendimento com sistema de registro, insumos administrativos e "
            "equipe para orientação ao cidadão."
        ),
        "ordem": 20,
    },
    {
        "codigo": "AAC",
        "nome": "Emissão de Atestado de Antecedentes Criminais",
        "meta": (
            "Facilitar a obtenção do documento, contribuindo para fins trabalhistas e "
            "demais necessidades legais dos cidadãos."
        ),
        "recurso_necessario": (
            "Terminal com acesso aos sistemas institucionais, impressão e equipe de "
            "apoio para validação de dados."
        ),
        "ordem": 30,
    },
    {
        "codigo": "PALESTRAS",
        "nome": "Palestras e orientações preventivas",
        "meta": (
            "Desenvolver ações educativas voltadas à prevenção de crimes, conscientização "
            "sobre segurança pública e fortalecimento do vínculo comunitário."
        ),
        "recurso_necessario": (
            "Espaço para apresentação, sistema de áudio, material didático e equipe de "
            "facilitação."
        ),
        "ordem": 40,
    },
    {
        "codigo": "LUDICO",
        "nome": "Atividades lúdicas e educativas para crianças",
        "meta": (
            "Promover aproximação institucional de forma didática, incentivando a cultura "
            "de respeito às leis e à cidadania desde a infância."
        ),
        "recurso_necessario": (
            "Materiais lúdicos, apoio pedagógico e área segura para dinâmicas com crianças."
        ),
        "ordem": 50,
    },
    {
        "codigo": "NOC",
        "nome": "Apresentação do trabalho do Núcleo de Operações com Cães (NOC)",
        "meta": (
            "Demonstrar as atividades operacionais desenvolvidas pela unidade especializada "
            "da Polícia Civil do Paraná, evidenciando técnicas e capacidades institucionais."
        ),
        "recurso_necessario": (
            "Área controlada para exibição operacional, equipe especializada, equipamentos "
            "de segurança e suporte logístico."
        ),
        "ordem": 60,
    },
    {
        "codigo": "TATICO",
        "nome": "Exposição de material tático",
        "meta": (
            "Apresentar equipamentos utilizados nas atividades policiais, proporcionando "
            "transparência e conhecimento sobre os recursos empregados pela instituição."
        ),
        "recurso_necessario": (
            "Bancadas de exposição, controle de acesso, equipe de apresentação e "
            "sinalização informativa."
        ),
        "ordem": 70,
    },
    {
        "codigo": "PAPILOSCOPIA",
        "nome": "Exposição da atividade de perícia papiloscópica",
        "meta": (
            "Demonstrar os procedimentos técnicos de identificação humana, ressaltando a "
            "importância da papiloscopia na investigação criminal e na identificação civil."
        ),
        "recurso_necessario": (
            "Estação demonstrativa, kits de coleta, materiais visuais e equipe técnica "
            "especializada."
        ),
        "ordem": 80,
    },
    {
        "codigo": "VIATURAS",
        "nome": "Exposição de viaturas antigas e modernas",
        "meta": (
            "Apresentar a evolução histórica e tecnológica dos veículos operacionais da instituição."
        ),
        "recurso_necessario": (
            "Área de exposição, apoio de segurança patrimonial e equipe para conduzir "
            "apresentações ao público."
        ),
        "ordem": 90,
    },
    {
        "codigo": "BANDA",
        "nome": "Apresentação da banda institucional",
        "meta": (
            "Fortalecer a integração com a comunidade por meio de atividade cultural "
            "representativa da instituição."
        ),
        "recurso_necessario": (
            "Estrutura de palco, sonorização, logística de montagem e suporte técnico "
            "para apresentação musical."
        ),
        "ordem": 100,
    },
    {
        "codigo": "UNIDADE_MOVEL",
        "nome": "Unidade móvel (ônibus ou caminhão)",
        "meta": (
            "Viabilizar a prestação descentralizada dos serviços acima descritos, assegurando "
            "estrutura adequada para atendimento ao público."
        ),
        "recurso_necessario": (
            "Unidade móvel institucional, equipe de operação, energia, conectividade e "
            "manutenção de suporte."
        ),
        "ordem": 110,
    },
]


def seed_atividades(apps, schema_editor):
    Atividade = apps.get_model("planos_trabalho", "AtividadePlanoTrabalho")
    for item in ATIVIDADES:
        Atividade.objects.update_or_create(
            codigo=item["codigo"],
            defaults={
                "nome": item["nome"],
                "meta": item["meta"],
                "recurso_necessario": item["recurso_necessario"],
                "ordem": item["ordem"],
                "ativo": True,
            },
        )


def remover_atividades(apps, schema_editor):
    Atividade = apps.get_model("planos_trabalho", "AtividadePlanoTrabalho")
    Atividade.objects.filter(codigo__in=[item["codigo"] for item in ATIVIDADES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("planos_trabalho", "0007_atividadeplanotrabalho_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_atividades, remover_atividades),
    ]
