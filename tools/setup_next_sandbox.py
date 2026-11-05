"""Prepare only the reviewed Next.js image; never loads credentials or project files."""

import io
import json
import re
import subprocess
import tarfile

from ai_team.next_artifacts import runtime_fingerprint, runtime_sources
from ai_team.next_sandbox import MANIFEST


def main():
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    iid = MANIFEST.parent / "image.id"
    # Freeze exactly the public reviewed inputs; edits during build cannot label
    # an old image with the fingerprint of newer files or add private context.
    files = runtime_sources()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for path, content in sorted(files.items()):
            data = content.encode("utf-8")
            entry = tarfile.TarInfo(path)
            entry.size = len(data)
            entry.mode = 0o644
            archive.addfile(entry, io.BytesIO(data))
    subprocess.run(
        [
            "docker",
            "build",
            "--pull=false",
            "--iidfile",
            str(iid),
            "-t",
            "ai-team-next-sandbox:16.4.3",
            "-",
        ],
        input=buffer.getvalue(),
        check=True,
        timeout=600,
    )
    image = iid.read_text().strip()
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise RuntimeError("Docker não confirmou ID imutável")
    MANIFEST.write_text(
        json.dumps(
            {
                "image_id": image,
                "runtime_hash": runtime_fingerprint(files),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Imagem Next.js própria preparada e vinculada ao runtime revisado.")


if __name__ == "__main__":
    main()
