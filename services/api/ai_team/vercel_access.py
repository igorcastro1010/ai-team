"""Credencial Vercel própria no cofre; somente consultas, sem comandos de publicação."""

import argparse
import getpass
import json
import re
import secrets
import sys
import time

import httpx
import keyring

SERVICE = "AI TEAM / Vercel"


class VercelVault:
    def __init__(self, backend=None):
        self.backend = backend or keyring.get_keyring()
        if backend is None and not type(self.backend).__module__.startswith(
            (
                "keyring.backends.Windows",
                "keyring.backends.SecretService",
                "keyring.backends.kwallet",
            )
        ):
            raise RuntimeError("Cofre nativo indisponível; arquivo de credenciais proibido")

    def load(self):
        stored = self.backend.get_password(SERVICE, "credentials")
        return json.loads(stored) if stored is not None else None

    def preflight(self):
        marker = "preflight-" + secrets.token_hex(8)
        self.backend.set_password(SERVICE, marker, marker)
        try:
            if self.backend.get_password(SERVICE, marker) != marker:
                raise RuntimeError("Cofre indisponível")
        finally:
            self.backend.delete_password(SERVICE, marker)
        if self.load() is not None:
            raise RuntimeError("Credencial existente será preservada; substituição não autorizada")

    def save(self, token, team_id):
        if self.load() is not None:
            raise RuntimeError("Credencial existente será preservada; substituição não autorizada")
        payload = json.dumps({"token": token, "team_id": team_id})
        if len(payload.encode("utf-16-le")) > 2400:
            raise RuntimeError("Credencial excede limite do cofre")
        try:
            self.backend.set_password(SERVICE, "credentials", payload)
        except Exception:
            raise RuntimeError(
                "Não foi possível salvar no cofre; nenhum segredo foi exibido"
            ) from None

    def bind_team(self, team_id, project_id, *, client=None):
        existing = self.load()
        if not existing:
            raise RuntimeError("Configure a credencial no cofre antes de vincular a equipe")
        reader = VercelClient(existing["token"], team_id, client=client, project_id=project_id)
        try:
            details = reader.probe()
            if details["project"] is None:
                raise RuntimeError("Projeto autorizado não encontrado nessa equipe")
            payload = json.dumps({**existing, "team_id": team_id, "project_id": project_id})
            try:
                self.backend.set_password(SERVICE, "credentials", payload)
            except Exception:
                raise RuntimeError("Não foi possível vincular a equipe no cofre") from None
            return details
        finally:
            reader.close()


class VercelClient:
    def __init__(self, token, team_id=None, *, client=None, project_id=None):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{20,512}", token):
            raise RuntimeError("Formato de token inválido; nenhum segredo foi exibido")
        if team_id and not re.fullmatch(r"team_[A-Za-z0-9]{1,100}", team_id):
            raise RuntimeError("Informe o Team ID, não a URL nem o nome da equipe")
        self._token, self._team_id = token, team_id
        self._project_id = project_id
        self._client = client or httpx.Client(timeout=20, follow_redirects=False, trust_env=False)

    def close(self):
        self._client.close()

    def _get(self, path, params):
        if path not in {"/v10/projects", "/v7/deployments"}:
            raise RuntimeError("Consulta Vercel não autorizada")
        query = dict(params)
        if self._team_id:
            query["teamId"] = self._team_id
        try:
            response = self._client.get(
                "https://api.vercel.com" + path,
                params=query,
                headers={"Authorization": "Bearer " + self._token, "User-Agent": "AI-TEAM"},
                follow_redirects=False,
            )
            if response.status_code != 200:
                raise RuntimeError(f"Consulta Vercel retornou HTTP {response.status_code}")
            return response.json()
        except RuntimeError:
            raise
        except Exception:
            raise RuntimeError(
                "Não foi possível consultar a Vercel; nenhum segredo foi exibido"
            ) from None

    def probe(self):
        result = self._get("/v10/projects", {"search": "ai-team", "limit": "100"})
        rows = result.get("projects") if isinstance(result, dict) else result
        if not isinstance(rows, list):
            raise RuntimeError("Resposta de projetos Vercel inesperada")
        matches = [row for row in rows if row.get("name") == "ai-team"]
        if len(matches) > 1:
            raise RuntimeError("Mais de um projeto ai-team; configure o escopo da equipe")
        details = {"verified_at": int(time.time()), "project": None, "deployments": []}
        if not matches:
            return details
        project = matches[0]
        if self._project_id and project.get("id") != self._project_id:
            raise RuntimeError("O projeto ai-team mudou de ID; revise o vínculo autorizado")
        if not isinstance(project.get("id"), str) or not re.fullmatch(
            r"[A-Za-z0-9_]{1,100}", project["id"]
        ):
            raise RuntimeError("Identificação do projeto Vercel inesperada")
        details["project"] = {"id": project["id"], "name": "ai-team"}
        result = self._get("/v7/deployments", {"projectId": project["id"], "limit": "10"})
        rows = result.get("deployments") if isinstance(result, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError("Resposta de deploys Vercel inesperada")
        for row in rows:
            if row.get("projectId") and row["projectId"] != project["id"]:
                raise RuntimeError("Deploy fora do projeto autorizado")
            details["deployments"].append(
                {
                    "id": row.get("uid") or row.get("id"),
                    "state": row.get("state"),
                    "created_at": row.get("createdAt"),
                }
            )
        return details


def configure(token, team_id, vault, *, client=None):
    vault.preflight()
    reader = VercelClient(token, team_id, client=client)
    try:
        details = reader.probe()
        vault.save(token, team_id)
        return details
    finally:
        reader.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["configure", "status", "bind-team"])
    parser.add_argument("--team-id", default=None, help="Equipe para token sem escopo inferido")
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()
    try:
        vault = VercelVault()
        existing = vault.load()
        if args.command == "bind-team":
            if not args.team_id or not args.project_id:
                raise RuntimeError("Informe Team ID e Project ID autorizados")
            details = vault.bind_team(args.team_id, args.project_id)
            print("Consulta vinculada à equipe e projeto autorizados; token preservado.")
        elif args.command == "configure" and existing is None:
            if not sys.stdin.isatty():
                raise RuntimeError(
                    "Abra um terminal interativo para informar o token com entrada oculta"
                )
            vault.preflight()
            print("Vercel / AI TEAM - somente consultas. Nenhum projeto ou deploy será criado.")
            print(
                "Crie um token em https://vercel.com/account/settings/tokens "
                "com escopo mínimo e prazo curto."
            )
            print("Prefira escopo do projeto ai-team. Evite Full Account.")
            print("O token pode permitir escrita na Vercel; este executor só implementa GET.")
            team_id = args.team_id
            token = getpass.getpass("Token Vercel (oculto, nunca enviado ao chat): ").strip()
            details = configure(token, team_id, vault)
            print("Credencial validada e armazenada no cofre do sistema.")
        elif existing:
            reader = VercelClient(
                existing["token"], existing.get("team_id"), project_id=existing.get("project_id")
            )
            try:
                details = reader.probe()
            finally:
                reader.close()
            print("Credencial existente preservada.")
        else:
            print("Credencial Vercel não configurada.")
            return
        print(json.dumps(details, ensure_ascii=False))
        if details["project"] is None:
            print("Nenhum projeto ai-team encontrado nesse escopo. Nada foi criado ou publicado.")
    except (RuntimeError, EOFError, KeyboardInterrupt) as error:
        print(str(error) if isinstance(error, RuntimeError) else "Configuração interrompida.")
        raise SystemExit(1) from None
    except Exception:
        print("Não foi possível configurar a Vercel; nenhum segredo foi exibido.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
