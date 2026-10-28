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
        "limit": "Sem execução de ferramentas externas nesta versão",
    },
    {
        "id": "DEV",
        "name": "DEV",
        "role": "Engenharia e integrações",
        "description": "Prepara alterações de código em ambientes isolados e revisáveis.",
        "tools": ["propor código", "especificar integrações"],
        "status": "available",
        "limit": "Sem acesso a checkouts ou shell nesta versão",
    },
    {
        "id": "DESIGNER",
        "name": "DESIGNER",
        "role": "Produto e experiência",
        "description": "Define interfaces, linguagem visual e critérios de acessibilidade.",
        "tools": ["especificar UI", "revisar experiência"],
        "status": "available",
        "limit": "Sem publicação de arquivos nesta versão",
    },
    {
        "id": "QA",
        "name": "QA",
        "role": "Qualidade e revisão",
        "description": "Verifica evidências, critérios de aceite e riscos antes da entrega.",
        "tools": ["revisar resultados", "relatar riscos"],
        "status": "available",
        "limit": "Sem execução de testes de projetos externos nesta versão",
    },
]
