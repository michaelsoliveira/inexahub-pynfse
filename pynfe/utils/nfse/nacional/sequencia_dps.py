"""
Sincronização de série/nDPS com o cadastro ISS.net municipal.

A sequência DPS é controlada pelo município — não pelo contador RPS interno.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from lxml import etree

from pynfe.utils.nfse.nacional import NAMESPACE_NFSE_NACIONAL

logger = logging.getLogger(__name__)
NS = NAMESPACE_NFSE_NACIONAL


def extrair_sequencia_dps_resposta(xml_text: str) -> Dict[str, Any]:
    """
    Extrai série e nDPS de respostas ConsultarDpsDisponivel / cadastro.

    Retorna dict com chaves opcionais: serie, numero_dps, proximo_numero_dps.
    """
    result: Dict[str, Any] = {}
    if not xml_text:
        return result
    try:
        root = etree.fromstring(
            xml_text.encode() if isinstance(xml_text, str) else xml_text
        )
    except etree.XMLSyntaxError:
        return result

    ns = {"n": NS}

    def _first_text(*paths):
        for path in paths:
            el = root.find(path, ns) if path.startswith(".//") else root.find(f".//n:{path}", ns)
            if el is not None and (el.text or "").strip():
                return "".join(c for c in el.text if c.isdigit() or c.isalnum())
        return None

    serie = _first_text("SerieDPS", "serie", "Serie")
    numero = _first_text("NumDPS", "nDPS", "NumeroDPS")

    for el in root.iter(f"{{{NS}}}IdentificacaoDps"):
        if serie is None:
            s = el.find(f"{{{NS}}}SerieDPS")
            if s is not None and s.text:
                serie = "".join(c for c in s.text if c.isdigit())
        if numero is None:
            n = el.find(f"{{{NS}}}NumDPS")
            if n is not None and n.text:
                numero = "".join(c for c in n.text if c.isdigit())

    if serie:
        result["serie"] = serie
    if numero:
        result["numero_dps"] = str(int(numero))
        try:
            result["proximo_numero_dps"] = str(int(numero) + 1)
        except ValueError:
            pass

    return result


def resolver_sequencia_emissao(
    config: Dict[str, Any],
    sync: Optional[Dict[str, Any]] = None,
) -> tuple[str, str]:
    """
    Resolve (serie, numero_dps) para emissão.

    Prioridade: sync API → config serie_rps / proximo_numero_rps.
    """
    serie = ""
    numero = "1"

    if sync:
        serie = (sync.get("serie") or "").strip()
        if sync.get("proximo_numero_dps"):
            numero = str(sync.get("proximo_numero_dps")).strip()
        elif sync.get("numero_dps"):
            try:
                numero = str(int(sync.get("numero_dps")) + 1)
            except (TypeError, ValueError):
                numero = str(sync.get("numero_dps")).strip()

    if not serie:
        serie = "".join(
            c for c in str(config.get("serie") or config.get("serie_rps") or "") if c.isdigit()
        )
    if not numero or numero == "0":
        numero = str(config.get("numero_dps") or config.get("proximo_numero_rps") or "1")

    if not serie:
        raise ValueError(
            "Série DPS ISSNet não configurada. "
            "Informe serie_rps na config NFS-e (ex.: 70002) ou sincronize com o portal municipal."
        )

    return serie, str(int("".join(c for c in numero if c.isdigit()) or "1"))
