def integration_statuses():
    return [
        {
            "id": "github",
            "name": "GitHub",
            "status": "planned",
            "verified_at": None,
            "description": "V0.3 · Repositórios permitidos, branches e pull requests com revisão.",
        },
        {
            "id": "codex",
            "name": "Codex",
            "status": "planned",
            "verified_at": None,
            "description": (
                "V0.4 · SDK/CLI oficial em executor próprio. Sem acesso à sessão do Desktop."
            ),
        },
        {
            "id": "vercel",
            "name": "Vercel",
            "status": "planned",
            "verified_at": None,
            "description": "V0.4 · Consulta de deploys; produção exige autorização específica.",
        },
        {
            "id": "supabase",
            "name": "Supabase",
            "status": "not_configured",
            "verified_at": None,
            "description": (
                "PostgreSQL privado via DATABASE_URL no servidor; sem chaves no navegador."
            ),
        },
        {
            "id": "skills",
            "name": "Find Skills",
            "status": "planned",
            "verified_at": None,
            "description": "Skills de desenvolvimento revisadas. Instalação em runtime desativada.",
        },
    ]
