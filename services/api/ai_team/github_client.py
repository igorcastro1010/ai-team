"""GitHub REST oficial com credencial própria e allowlist de um repositório."""

import time

import httpx
import jwt

from .github_setup import OWNER, AppVault

REPOSITORY = f"{OWNER}/ai-team"
PERMISSIONS = {"contents": "write", "issues": "write", "pull_requests": "write", "metadata": "read"}


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, credentials=None, *, client=None):
        self._credentials = credentials if credentials is not None else AppVault().load()
        if not self._credentials:
            raise GitHubError("GitHub App não configurada no cofre do executor")
        self._client = client or httpx.Client(timeout=20, follow_redirects=False, trust_env=False)

    def close(self):
        self._client.close()

    def _jwt(self):
        now = int(time.time())
        try:
            return jwt.encode(
                {"iat": now - 60, "exp": now + 540, "iss": str(self._credentials["id"])},
                self._credentials["pem"],
                algorithm="RS256",
            )
        except Exception:
            raise GitHubError("Não foi possível autenticar a App com a chave do cofre") from None

    def _request(self, method, path, token, *, body=None, expected=200):
        # Only internal, fixed paths reach this method. No host or redirect comes from a model.
        if not path.startswith("/") or path.startswith("//"):
            raise GitHubError("Caminho da API não autorizado")
        try:
            response = self._client.request(
                method,
                "https://api.github.com" + path,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": "Bearer " + token,
                    "X-GitHub-Api-Version": "2026-03-10",
                    "User-Agent": "AI-TEAM",
                },
                json=body,
                follow_redirects=False,
            )
            if response.status_code != expected:
                raise GitHubError(
                    f"GitHub respondeu HTTP {response.status_code}; chamada não repetida"
                )
            result = response.json()
            if not isinstance(result, dict):
                raise GitHubError("Resposta inesperada do GitHub")
            return result
        except GitHubError:
            raise
        except Exception:
            raise GitHubError("Falha de comunicação com o GitHub; chamada não repetida") from None

    def verify(self):
        app_jwt = self._jwt()
        app = self._request("GET", "/app", app_jwt)
        if (
            app.get("id") != self._credentials["id"]
            or app.get("slug") != self._credentials["slug"]
            or app.get("owner", {}).get("login", "").lower() != OWNER
        ):
            raise GitHubError("Identidade da GitHub App diferente da configuração autorizada")
        installation = self._request("GET", f"/repos/{REPOSITORY}/installation", app_jwt)
        installation_id = installation.get("id")
        if (
            type(installation_id) is not int
            or installation_id <= 0
            or installation.get("app_id") != self._credentials["id"]
            or installation.get("account", {}).get("login", "").lower() != OWNER
            or installation.get("repository_selection") != "selected"
            or installation.get("suspended_at") is not None
            or installation.get("permissions") != PERMISSIONS
        ):
            raise GitHubError(
                "Instalação deve ser seletiva, ativa e ter apenas as permissões previstas"
            )
        # An unscoped metadata-only token reveals the real installation scope, not a filtered list.
        response = self._request(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            app_jwt,
            body={"permissions": {"metadata": "read"}},
            expected=201,
        )
        token = response.get("token")
        if not isinstance(token, str) or not token:
            raise GitHubError("GitHub não emitiu token de instalação")
        accessible = self._request("GET", "/installation/repositories?per_page=100", token)
        repositories = accessible.get("repositories", [])
        if (
            accessible.get("total_count") != 1
            or len(repositories) != 1
            or repositories[0].get("full_name", "").lower() != REPOSITORY
        ):
            raise GitHubError("Instalação deve permitir exclusivamente igorcastro1010/ai-team")
        repository = self._request("GET", f"/repos/{REPOSITORY}", token)
        if (
            repository.get("id") != repositories[0].get("id")
            or repository.get("full_name", "").lower() != REPOSITORY
            or repository.get("private") is not True
            or repository.get("archived") is not False
            or not repository.get("default_branch")
        ):
            raise GitHubError("Repositório privado autorizado indisponível para desenvolvimento")
        return {
            "repository": REPOSITORY,
            "repository_id": repository["id"],
            "installation_id": installation_id,
            "app_slug": app["slug"],
            "default_branch": repository["default_branch"],
            "verified_at": int(time.time()),
        }


def main():
    import json

    client = None
    try:
        client = GitHubClient()
        print(json.dumps(client.verify(), ensure_ascii=False))
    except GitHubError as error:
        print(str(error))
        raise SystemExit(1) from None
    except Exception:
        print("Não foi possível verificar a GitHub App; nenhum segredo foi exibido")
        raise SystemExit(1) from None
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
