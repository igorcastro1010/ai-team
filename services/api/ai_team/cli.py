import argparse
import getpass

from .auth import create_owner
from .config import Settings
from .db import Database


def main():
    parser = argparse.ArgumentParser(description="Administração local do AI TEAM")
    parser.add_argument("command", choices=["init-db", "create-owner"])
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()
    database = Database(Settings())
    database.initialize()
    if args.command == "create-owner":
        password = getpass.getpass("Senha (mínimo 12 caracteres): ")
        confirmation = getpass.getpass("Confirme a senha: ")
        if password != confirmation:
            parser.exit(1, "Senhas diferentes. Nenhum usuário criado.\n")
        try:
            with database.session() as db:
                create_owner(db, args.username, password)
        except ValueError as error:
            parser.exit(1, f"{error}\n")
        print("Proprietário criado. Acesse http://localhost:3000")
    else:
        print("Banco inicializado. Nenhum segredo foi exibido.")


if __name__ == "__main__":
    main()
