"""GitHub REST oficial com credencial própria e allowlist de um repositório."""

import time
from urllib.parse import quote

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
        self.mutation_attempted = False
        self.tick = lambda: None

    def close(self):
        self._client.close()

    def _jwt(self):
        now = int(time.time())
        try:
            self.tick()
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
            self.tick()
            if method != "GET" and not path.endswith("/access_tokens"):
                self.mutation_attempted = True
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
            self.tick()
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

    def _token(self, verification, permissions):
        response = self._request(
            "POST",
            f"/app/installations/{verification['installation_id']}/access_tokens",
            self._jwt(),
            body={
                "repository_ids": [verification["repository_id"]],
                "permissions": {"metadata": "read", **permissions},
            },
            expected=201,
        )
        token = response.get("token")
        if not isinstance(token, str) or not token:
            raise GitHubError("Token restrito ao repositório indisponível")
        return token

    def head(self, verification):
        token = self._token(verification, {"contents": "read"})
        ref = self._request(
            "GET",
            f"/repos/{REPOSITORY}/git/ref/heads/" + quote(verification["default_branch"], safe=""),
            token,
        )
        return ref["object"]["sha"]

    def execute(self, payload):
        from .github_actions import Proposal

        data = Proposal.model_validate(payload)
        # Recheck installation scope immediately before every approved external operation.
        verified = self.verify()
        if verified["default_branch"] != "main":
            raise GitHubError("A branch padrão mudou; revise a política antes de executar")
        permission = {
            "branch": "contents",
            "commit": "contents",
            "issue": "issues",
            "pull_request": "pull_requests",
        }[data.operation]
        permissions = {permission: "write"}
        if data.operation == "pull_request":
            # Private head refs require contents:read; without it GitHub reports HTTP 422.
            permissions["contents"] = "read"
        token = self._token(verified, permissions)
        root = f"/repos/{REPOSITORY}"
        if data.operation == "branch":
            current = self._request("GET", root + "/git/ref/heads/main", token)
            if current["object"]["sha"] != data.expected_sha:
                raise GitHubError("A base mudou desde a revisão. Crie outra proposta")
            self._request(
                "POST",
                root + "/git/refs",
                token,
                expected=201,
                body={"ref": "refs/heads/" + data.branch, "sha": data.expected_sha},
            )
            return {
                "sha": data.expected_sha,
                "url": f"https://github.com/{REPOSITORY}/tree/{data.branch}",
            }
        if data.operation == "commit":
            current = self._request("GET", root + "/git/ref/heads/" + data.branch, token)
            if current["object"]["sha"] != data.expected_sha:
                raise GitHubError("Branch alterada desde a revisão. Crie outra proposta")
            parent = self._request("GET", root + "/git/commits/" + data.expected_sha, token)
            blob = self._request(
                "POST",
                root + "/git/blobs",
                token,
                expected=201,
                body={"content": data.content, "encoding": "utf-8"},
            )
            tree = self._request(
                "POST",
                root + "/git/trees",
                token,
                expected=201,
                body={
                    "base_tree": parent["tree"]["sha"],
                    "tree": [
                        {"path": data.path, "mode": "100644", "type": "blob", "sha": blob["sha"]}
                    ],
                },
            )
            commit = self._request(
                "POST",
                root + "/git/commits",
                token,
                expected=201,
                body={"message": data.title, "tree": tree["sha"], "parents": [data.expected_sha]},
            )
            # A concurrent commit is not an ancestor: force=false rejects losing their work.
            self._request(
                "PATCH",
                root + "/git/refs/heads/" + data.branch,
                token,
                body={"sha": commit["sha"], "force": False},
            )
            return {
                "sha": commit["sha"],
                "url": f"https://github.com/{REPOSITORY}/commit/{commit['sha']}",
            }
        body = {"title": data.title, "body": data.body}
        endpoint = "/issues"
        if data.operation == "pull_request":
            current = self._request("GET", root + "/git/ref/heads/" + data.branch, token)
            if current["object"]["sha"] != data.expected_sha:
                raise GitHubError("Branch do PR alterada desde a revisão. Crie outra proposta")
            endpoint = "/pulls"
            body.update({"head": data.branch, "base": "main", "draft": data.draft})
        created = self._request("POST", root + endpoint, token, expected=201, body=body)
        number = created.get("number")
        if type(number) is not int or number <= 0:
            raise GitHubError("Resposta de criação inesperada; confira no GitHub")
        kind = "pull" if data.operation == "pull_request" else "issues"
        result = {"number": number, "url": f"https://github.com/{REPOSITORY}/{kind}/{number}"}
        if data.operation == "pull_request":
            result["requires_review"] = created.get("head", {}).get("sha") != data.expected_sha
        return result


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
