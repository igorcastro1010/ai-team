"""Registro opt-in de GitHub App privada pelo fluxo oficial de manifesto."""

import hmac
import html
import json
import re
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import keyring

SERVICE = "AI TEAM / GitHub App"
OWNER = "igorcastro1010"
PROJECT_URL = f"https://github.com/{OWNER}/ai-team"


class AppVault:
    def __init__(self, backend=None):
        self.backend = backend or keyring.get_keyring()
        if backend is None and not type(self.backend).__module__.startswith(
            (
                "keyring.backends.Windows",
                "keyring.backends.SecretService",
                "keyring.backends.kwallet",
            )
        ):
            raise RuntimeError("Cofre seguro do sistema indisponível; fallback em arquivo proibido")

    def preflight(self):
        marker = f"preflight-{secrets.token_hex(8)}"
        self.backend.set_password(SERVICE, marker, marker)
        try:
            if self.backend.get_password(SERVICE, marker) != marker:
                raise RuntimeError("Cofre indisponível")
        finally:
            self.backend.delete_password(SERVICE, marker)
        if self.load() is not None:
            raise RuntimeError("GitHub App já configurado; não será sobrescrito")

    def load(self):
        metadata = self.backend.get_password(SERVICE, "current")
        if metadata is None:
            return None
        index = json.loads(metadata)
        if not re.fullmatch(r"[a-f0-9]{32}", index["ref"]) or not 1 <= index["count"] <= 32:
            raise RuntimeError("Metadados do cofre inválidos")
        parts = [
            self.backend.get_password(SERVICE, f"{index['ref']}-{i}") for i in range(index["count"])
        ]
        if any(part is None for part in parts):
            raise RuntimeError("Credencial incompleta no cofre")
        return json.loads("".join(parts))

    def save(self, response):
        if self.backend.get_password(SERVICE, "current") is not None:
            raise RuntimeError("GitHub App já configurado; não será sobrescrito")
        # Keep only fields used for App JWT authentication. Discard OAuth/webhook secrets.
        payload = json.dumps({key: response[key] for key in ["id", "slug", "pem"]})
        if len(payload) > 32000:
            raise ValueError("Chave privada excede o limite do cofre")
        ref = secrets.token_hex(16)
        parts = [payload[i : i + 1000] for i in range(0, len(payload), 1000)]
        written = []
        try:
            for i, part in enumerate(parts):
                account = f"{ref}-{i}"
                self.backend.set_password(SERVICE, account, part)
                written.append(account)
            self.backend.set_password(
                SERVICE, "current", json.dumps({"ref": ref, "count": len(parts)})
            )
        except Exception:
            for account in written:
                try:
                    self.backend.delete_password(SERVICE, account)
                except Exception:
                    pass
            raise RuntimeError("Não foi possível salvar a credencial no cofre") from None


def app_manifest(redirect_url):
    return {
        "name": "AI TEAM - igorcastro1010",
        "url": PROJECT_URL,
        "description": "Agentes supervisionados. Validação inicial somente no repositório ai-team.",
        "public": False,
        "redirect_url": redirect_url,
        "hook_attributes": {"url": PROJECT_URL, "active": False},
        "default_events": [],
        "default_permissions": {
            "contents": "write",
            "issues": "write",
            "pull_requests": "write",
            "metadata": "read",
        },
        "request_oauth_on_install": False,
    }


def registration_form(redirect_url, state):
    """Serialize the validated manifest into a POST form, never a GitHub GET link."""
    manifest = app_manifest(redirect_url)
    callback = urlsplit(redirect_url)
    if (
        manifest.get("url") != PROJECT_URL
        or manifest.get("hook_attributes") != {"url": PROJECT_URL, "active": False}
        or manifest.get("redirect_url") != redirect_url
        or callback.scheme != "http"
        or callback.hostname != "127.0.0.1"
        or not callback.port
        or callback.username is not None
        or callback.password is not None
        or callback.path != "/callback"
        or callback.query
        or callback.fragment
    ):
        raise ValueError("Configuração do manifesto inválida; registro não será enviado")
    encoded = html.escape(json.dumps(manifest, ensure_ascii=False, allow_nan=False), quote=True)
    action = html.escape(
        "https://github.com/settings/apps/new?" + urlencode({"state": state}), quote=True
    )
    return (
        f'<form method="post" action="{action}" '
        'enctype="application/x-www-form-urlencoded" accept-charset="UTF-8">'
        f'<input type="hidden" name="manifest" value="{encoded}">'
        '<button>Criar GitHub App privada</button></form>'
    )


def existing_app_page(app):
    slug = app["slug"]
    if not re.fullmatch(r"[a-z0-9-]{1,100}", slug):
        raise ValueError("Identificação da App inválida no cofre")
    return (
        "<p>AI TEAM / INTEGRAÇÃO PRÓPRIA</p><h1>App já registrada.</h1>"
        f"<p>A configuração de <strong>{slug}</strong> está no cofre do executor. "
        "O cadastro existente será preservado.</p>"
        f'<p><a href="https://github.com/apps/{slug}/installations/new">'
        "Revisar instalação no GitHub</a></p>"
        "<p>Escolha <strong>Only select repositories → ai-team</strong>. "
        "Se já estiver instalada, revise a seleção existente.</p>"
        "<p>Instalação e operações da API ainda precisam ser homologadas.</p>"
    )


class SetupFlow:
    def __init__(self, vault, client=None):
        self.vault = vault
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
        self.state = secrets.token_urlsafe(32)
        self.used = False
        self.expires_at = time.monotonic() + 900

    def complete(self, state, code):
        if (
            self.used
            or time.monotonic() > self.expires_at
            or not hmac.compare_digest(state, self.state)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", code)
        ):
            raise ValueError("Callback inválido, vencido ou já utilizado")
        self.used = True
        response = self.client.post(
            f"https://api.github.com/app-manifests/{code}/conversions",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "AI-TEAM-setup",
            },
        )
        if response.status_code != 201:
            raise ValueError("GitHub não concluiu o registro; nenhum segredo foi exibido")
        data = response.json()
        if (
            data.get("owner", {}).get("login", "").lower() != OWNER
            or not isinstance(data.get("id"), int)
            or data["id"] <= 0
            or not re.fullmatch(r"[a-z0-9-]{1,100}", data.get("slug", ""))
            or "PRIVATE KEY" not in data.get("pem", "")
        ):
            raise ValueError("Resposta inesperada ou App registrado em outra conta")
        self.vault.save(data)
        return f"https://github.com/apps/{data['slug']}/installations/new"


PAGE_STYLE = """<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font:16px/1.65 system-ui;background:#13190f;color:#edf5e4;max-width:680px;
padding:38px 24px;margin:5vh auto}h1{font-size:35px;font-weight:500}a{color:#c4ef82}
button{background:#c4ef82;color:#18230f;padding:15px 23px;border:0;border-radius:8px;
font:600 16px system-ui;cursor:pointer}small{color:#b5c4a7}li{margin:12px 0}</style>"""


def main():
    vault = AppVault()
    existing = vault.load()
    if existing is None:
        vault.preflight()
    flow = SetupFlow(vault)
    completed = False

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass  # Callback includes one-time code: never log request URLs.

        def send_page(self, status, content):
            body = (
                f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
                f"<title>AI TEAM · GitHub App</title>{PAGE_STYLE}</head>"
                f"<body>{content}</body></html>"
            ).encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; "
                "form-action https://github.com; base-uri 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            nonlocal completed
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send_page(403, "<h1>Host não autorizado.</h1>")
                return
            parsed = urlsplit(self.path)
            if parsed.path == f"/start/{flow.state}" and not flow.used:
                if existing is not None:
                    self.send_page(200, existing_app_page(existing))
                    return
                form = registration_form(
                    f"http://127.0.0.1:{self.server.server_port}/callback", flow.state
                )
                self.send_page(
                    200,
                    f"""<p>AI TEAM / INTEGRAÇÃO PRÓPRIA</p>
<h1>Uma App privada, sob seu controle.</h1>
<p>O registro será feito na conta <strong>{OWNER}</strong>.
A chave privada será recebida diretamente no cofre do sistema;
não aparecerá na página, no chat ou em arquivos do projeto.</p>
<ul><li>Permissões: conteúdo, issues e pull requests com escrita; metadados com leitura.</li>
<li>Sem administração, pagamentos, exclusão de repositórios ou workflows.</li>
<li>App privada, sem webhooks e sem acesso público.</li>
<li>Na instalação, escolha <strong>Only select repositories → ai-team</strong>.</li></ul>
<p>Primeiro, <a href="https://github.com/login" target="_blank" rel="noopener noreferrer">entre
no GitHub</a> com a conta <strong>{OWNER}</strong>. Depois volte a esta página e clique abaixo.</p>
{form}
<p><small>O botão envia o manifesto por POST. Abrir ou recarregar o endereço
<code>github.com/settings/apps/new</code> diretamente não envia a configuração.
Se aparecer “url wasn't supplied”, volte a esta página e use o botão novamente.</small></p>
<p><small>Este serviço temporário escuta somente em 127.0.0.1 e expira em 15 minutos.
O registro não faz commit, pull request ou deploy.</small></p>""",
                )
            elif parsed.path == "/callback":
                if existing is not None:
                    self.send_page(409, "<h1>App já configurada. Cadastro preservado.</h1>")
                    return
                query = parse_qs(parsed.query)
                try:
                    url = flow.complete(query.get("state", [""])[0], query.get("code", [""])[0])
                except Exception:
                    self.send_page(
                        400,
                        "<h1>Registro não concluído.</h1><p>Confira a conta, o prazo e o cofre. "
                        "Nenhum segredo foi exibido. Se uma App foi criada, preserve seu acesso "
                        "nas configurações do GitHub antes de tentar novamente.</p>",
                    )
                    return
                completed = True
                self.send_page(
                    200,
                    "<h1>App registrada com segurança.</h1><p>Agora instale somente no "
                    "<strong>ai-team</strong>.</p><p>"
                    f'<a href="{html.escape(url, quote=True)}">Instalar no GitHub</a></p>'
                    "<p>Integração ainda não homologada: a instalação e as chamadas da API "
                    "serão verificadas na próxima etapa.</p>",
                )
                print(f"App registrada no cofre. Instale somente em ai-team: {url}", flush=True)
            else:
                self.send_page(404, "<h1>Página não encontrada.</h1>")

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        server.timeout = 1
        print(
            f"Abra para revisar o registro: http://127.0.0.1:{server.server_port}/start/{flow.state}",
            flush=True,
        )
        while not completed and time.monotonic() < flow.expires_at:
            server.handle_request()
    flow.client.close()


if __name__ == "__main__":
    main()
