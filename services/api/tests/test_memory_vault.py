from pathlib import Path

import pytest


def test_markdown_roundtrip_and_conflict(tmp_path):
    from ai_team.memory_vault import Vault, VaultError

    vault = Vault(tmp_path)
    vault.write("alpha", "decisao.md", "# Decisão\nUsar [[Python]].")
    assert "[[Python]]" in vault.read("alpha", "decisao.md")
    with pytest.raises(VaultError):
        vault.write("alpha", "decisao.md", "Alteração", expected_digest="0" * 64)


@pytest.mark.parametrize(
    "path",
    [
        "../secret.md",
        "C:/secret.md",
        "\\\\server\\share.md",
        "a/../../secret.md",
        ".obsidian/config.md",
        "NUL.md",
        "foo.md:stream",
        "test.py",
        "a\\b.md",
    ],
)
def test_vault_denies_unsafe_paths(tmp_path, path):
    from ai_team.memory_vault import Vault, VaultError

    with pytest.raises(VaultError):
        Vault(tmp_path).write("alpha", path, "texto")
    assert list(tmp_path.glob("*.md")) == []


def test_vault_never_follows_symlinks(tmp_path):
    from ai_team.memory_vault import Vault, VaultError

    outside = tmp_path / "outside"
    outside.mkdir()
    target = tmp_path / "vault"
    target.mkdir()
    try:
        (target / "alpha").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS cannot create symlinks without privilege")
    with pytest.raises(VaultError):
        Vault(target).write("alpha", "escape.md", "never")
    assert not (outside / "escape.md").exists()


def test_vault_rejects_secrets_and_large_files(tmp_path):
    from ai_team.memory_vault import Vault, VaultError

    vault = Vault(tmp_path)
    with pytest.raises(VaultError):
        vault.write("alpha", "secret.md", "Bearer " + "a" * 60)
    with pytest.raises(VaultError):
        vault.write("alpha", "big.md", "x" * 65537)
    assert not list(Path(tmp_path).rglob("*.md"))
