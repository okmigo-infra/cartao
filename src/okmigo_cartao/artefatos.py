"""Materialização estável de manifestos compilados pelo SDK."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def manifesto_confere(destino: str | Path, manifesto: Mapping[str, Any]) -> bool:
    """Compara o conteúdo JSON sem transformar ordem de chaves em mudança."""
    caminho = Path(destino)
    try:
        atual = json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return atual == manifesto


def materializar_manifesto(
    destino: str | Path,
    manifesto: Mapping[str, Any],
    *,
    indentacao: int = 2,
) -> bool:
    """Escreve somente quando o contrato mudou; devolve se houve escrita."""
    caminho = Path(destino)
    if manifesto_confere(caminho, manifesto):
        return False
    caminho.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=indentacao) + "\n",
        encoding="utf-8",
    )
    return True
