"""Reject credentials before persistence; retrieved text never grants authority."""

import re

SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\b(?:gh[pousr]_|github_pat_|sk-|vcp_)[A-Za-z0-9_-]{16,}|"
    r"\b(?i:Bearer)\s+[A-Za-z0-9._~-]{16,}|"
    r"(?i:postgres(?:ql)?(?:\+psycopg)?://)[^\s]+|"
    r"(?i:(?:password|passwd|senha|api[_-]?key|access[_-]?token|client[_-]?secret)"
    r"\s*[\"']?\s*[:=]\s*[\"']?[^\s\"']{8,})"
)
INJECTION = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions|"
    r"ignore\s+(?:as\s+)?instruções|reveal\s+(?:secrets|credentials)|"
    r"<\|(?:system|im_start)\|>|\[INST\]|<script|javascript:",
    re.I,
)


def validate_text(text: str, *, maximum: int = 64000):
    if not isinstance(text, str) or len(text.encode("utf-8")) > maximum or "\x00" in text:
        raise ValueError("Texto inválido ou maior que o limite permitido")
    if SECRET.search(text):
        raise ValueError("Credencial detectada; conteúdo não foi armazenado")
    return text
