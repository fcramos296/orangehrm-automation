"""Geração de arquivos de currículo sintéticos para os cenários de upload.

Os arquivos são criados em tempo de execução (``tmp_path``), assim o repositório
não carrega binários e os limites ficam exatos (ex.: 1 byte acima do máximo).
"""

from __future__ import annotations

from pathlib import Path

# Limite exibido na tela ("up to 1MB") e aplicado no cliente: file.size <= 1048576.
MAX_RESUME_BYTES = 1_048_576

ALLOWED_EXTENSIONS = (".docx", ".doc", ".odt", ".pdf", ".rtf", ".txt")

_MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)
_PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def text_resume(directory: Path, name: str = "curriculo.txt") -> Path:
    path = directory / name
    path.write_text("Curriculo sintetico para testes automatizados.\n", encoding="utf-8")
    return path


def pdf_resume(directory: Path, name: str = "curriculo.pdf", size: int | None = None) -> Path:
    """PDF mínimo; com ``size`` é preenchido até o tamanho exato em bytes."""
    content = _MINIMAL_PDF
    if size is not None:
        if size < len(content):
            raise ValueError(f"size deve ser >= {len(content)} bytes")
        content = content + b"%" * (size - len(content))
    path = directory / name
    path.write_bytes(content)
    return path


def image_file(directory: Path, name: str = "foto.png") -> Path:
    path = directory / name
    path.write_bytes(_PNG_HEADER + b"\x00" * 64)
    return path


def empty_file(directory: Path, name: str = "vazio.txt") -> Path:
    path = directory / name
    path.write_bytes(b"")
    return path
