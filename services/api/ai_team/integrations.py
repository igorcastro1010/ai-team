def integration_statuses():
    return [
        {
            "id": "github",
            "name": "GitHub",
            "status": "available",
            "verified_at": None,
            "description": (
                "App própria para ai-team. Verifique a instalação e revise as propostas."
            ),
        },
        {
            "id": "codex",
            "name": "Codex",
            "status": "available",
            "verified_at": None,
            "description": (
                "CLI oficial para planos e pareceres. Login próprio e worker necessários."
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
