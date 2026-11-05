RESEARCHER = {
    "id": "PESQUISADOR",
    "name": "PESQUISADOR",
    "role": "Pesquisa de código e documentação",
    "description": "Analisa evidências no snapshot autorizado e orienta os especialistas.",
    "tools": ["ler snapshot autorizado", "relatar fontes locais"],
    "status": "available",
    "limit": "Sem navegação externa, shell ou acesso a credenciais",
}

AGENTS = [
    {
        "id": "CEO",
        "name": "CEO",
        "role": "Estratégia e coordenação",
        "description": (
            "Transforma solicitações em planos, distribui trabalho e consolida resultados."
        ),
        "tools": ["planejar", "delegar", "relatar"],
        "status": "available",
        "limit": "Sem shell; publicação depende de autorização específica no executor",
    },
    {
        "id": "DEV",
        "name": "DEV",
        "role": "Engenharia e integrações",
        "description": "Prepara alterações de código em ambientes isolados e revisáveis.",
        "tools": ["gerar arquivos do perfil", "especificar integrações"],
        "status": "available",
        "limit": "Somente arquivos autorizados do perfil; sem shell ou credenciais",
    },
    {
        "id": "DESIGNER",
        "name": "DESIGNER",
        "role": "Produto e experiência",
        "description": "Define interfaces, linguagem visual e critérios de acessibilidade.",
        "tools": ["especificar UI", "revisar experiência"],
        "status": "available",
        "limit": "CSS ou documentação conforme o perfil; sem publicação autônoma",
    },
    {
        "id": "QA",
        "name": "QA",
        "role": "Qualidade e revisão",
        "description": "Verifica evidências, critérios de aceite e riscos antes da entrega.",
        "tools": ["gerar testes", "revisar resultados", "relatar riscos"],
        "status": "available",
        "limit": "Comando fixo executado pelo worker no sandbox; sem shell de agente",
    },
]
