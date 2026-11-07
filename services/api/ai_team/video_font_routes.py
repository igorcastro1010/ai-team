"""Authenticated local fonts: preview and renderer share the same files."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from .auth import require_owner
from .video_render import font_path

router = APIRouter(prefix="/video-studio/fonts")


@router.get("/{family}")
def font(family: Literal["sans", "serif", "mono"], owner: Annotated[str, Depends(require_owner)]):
    path = font_path(family)
    if path is None or path.is_symlink():
        raise HTTPException(404, "Fonte local indisponível")
    return FileResponse(path, media_type="font/ttf", headers={"Cache-Control": "private, no-store"})
