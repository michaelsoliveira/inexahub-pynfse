"""
ISSNet / Nota Control — ABRASF 2.04 (RPS, não DPS Nacional).

Cada contribuinte (clínica/autônomo) possui cadastro municipal próprio:
certificado A1, IM, série RPS autorizada pela prefeitura e sequência individual.

Webservice Macapá (produção):
  https://nfse.issnetonline.com.br/abrasf204/macapa/nfse.asmx

Homologação ISSNet (ABRASF 2.04 genérico):
  https://www.issnetonline.com.br/homologaabrasf/webservicenfse204/nfse.asmx
"""
from __future__ import annotations

from dataclasses import dataclass

from pynfe.utils.nfse.issnet import (
    ISSNET_URL_PADRAO,
    ISSNET_CIDADES,
    VERSAO_ABRASF204,
)

# Municípios com webservice oficial ABRASF 2.04 (Nota Control)
ISSNET_ABRASF204: dict[str, dict[str, str]] = {
    "1600303": {
        "ws_producao": "https://nfse.issnetonline.com.br/abrasf204/macapa/nfse.asmx",
        # Nota Control/ISSNet ABRASF 2.04 não possui endpoint de homologação público.
        # O teste deve ser feito no endpoint de produção com IM autorizada pela prefeitura.
        # Use issnet_ws_url na config da clínica para apontar a um ambiente de testes
        # caso a Nota Control disponibilize um no futuro.
        "ws_homologacao": "https://nfse.issnetonline.com.br/abrasf204/macapa/nfse.asmx",
        "ibge_homologacao": "1600303",
        "serie_producao": "3",
        "serie_homologacao": "8",
    },
}


def normalizar_ibge(ibge: str) -> str:
    return "".join(c for c in str(ibge or "") if c.isdigit()).zfill(7)[:7]


def params_municipio(ibge: str) -> dict[str, str] | None:
    return ISSNET_ABRASF204.get(normalizar_ibge(ibge))


def suporta_abrasf204(ibge: str) -> bool:
    return params_municipio(ibge) is not None


def url_webservice(ibge: str, homologacao: bool = False, ws_url: str | None = None) -> str:
    """URL do webservice ABRASF 2.04 por IBGE ou override explícito."""
    if (ws_url or "").strip():
        return ws_url.strip().rstrip("?WSDL").rstrip("?wsdl")
    cfg = params_municipio(ibge)
    if cfg:
        return cfg["ws_homologacao"] if homologacao else cfg["ws_producao"]
    ibge7 = normalizar_ibge(ibge)
    cidade = ISSNET_CIDADES.get(ibge7)
    if cidade:
        return ISSNET_URL_PADRAO.format(cidade=cidade)
    raise ValueError(
        f"Município IBGE {ibge7!r} não cadastrado para ISSNet ABRASF. "
        "Informe issnet_ws_url na config NFS-e."
    )


def serie_rps_emissao(
    ibge: str,
    homologacao: bool,
    serie_config: str | None = None,
    serie_payload: str | None = None,
) -> str:
    """
    Resolve série RPS do contribuinte.

    Macapá: série 3 (produção) ou 8 (homologação), liberada pela prefeitura.
    Ignora séries do portal DPS Nacional (700xx).
    """
    if serie_payload:
        return str(serie_payload).strip()

    cfg = params_municipio(ibge)
    if not cfg:
        return (serie_config or "A").strip() or "A"

    padrao = cfg["serie_homologacao"] if homologacao else cfg["serie_producao"]
    serie = (serie_config or "").strip()
    if serie and not serie.startswith("700"):
        return serie
    return padrao


def ibge_prestacao_servico(ibge_prestador: str, homologacao: bool) -> str:
    """IBGE do município de prestação (homolog ISSNet usa Campo Grande 5002704)."""
    cfg = params_municipio(ibge_prestador)
    if cfg and homologacao:
        return cfg.get("ibge_homologacao") or normalizar_ibge(ibge_prestador)
    return normalizar_ibge(ibge_prestador)


def item_lista_lc116(codigo: str) -> str:
    """Converte código nacional 6 dígitos (040101) → LC 116 ABRASF (04.01)."""
    raw = (codigo or "").strip()
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 6:
        return "%s.%s" % (digits[:2], digits[2:4])
    return raw


def aliquota_xml_valor(aliquota_frac: float, abrasf204: bool = True) -> float | None:
    """ABRASF 2.04: fração decimal (0.05 = 5%); legado 2.01: percentual (5.00)."""
    if aliquota_frac <= 0:
        return None
    if abrasf204:
        return aliquota_frac / 100.0 if aliquota_frac > 1 else float(aliquota_frac)
    return float(aliquota_frac) * 100.0 if aliquota_frac <= 1 else float(aliquota_frac)


def iss_retido_para_tomador(
    tomador_doc: str,
    iss_retido_config: bool,
    homologacao: bool,
) -> int:
    """PF (CPF) não retém ISS; retenção só para CNPJ tomador em produção."""
    from pynfe.utils.nfse.issnet import ISS_RETIDO_NAO, ISS_RETIDO_SIM

    doc = "".join(c for c in str(tomador_doc or "") if c.isdigit())
    if iss_retido_config and not homologacao and len(doc) == 14:
        return ISS_RETIDO_SIM
    return ISS_RETIDO_NAO


def codigo_tributacao_municipio(
    item_lista: str,
    cnae: str = "",
    config_val: str | None = None,
) -> str | None:
    """
    Resolve CodigoTributacaoMunicipio para ABRASF 2.04.

    Preferência: config explícita → item LC116 (ex.: 04.01 → 0401) → CNAE.
    CNAE (8630501) não deve ser usado como código municipal quando há item LC116.
    """
    if config_val:
        digits = "".join(c for c in str(config_val) if c.isdigit())
        return digits[:20] if digits else None
    raw = (item_lista or "").replace(".", "").replace(" ", "")
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) >= 4:
        return digits[:4]
    if digits:
        return digits.zfill(4)
    cnae_digits = "".join(c for c in str(cnae or "") if c.isdigit())[:7]
    return cnae_digits or None


@dataclass(frozen=True)
class ContextoRpsContribuinte:
    """
    Contexto de emissão por contribuinte (multi-tenant SaaS).

    Cada clínica/profissional mantém sua própria faixa de RPS autorizada
    pela prefeitura (serie_rps + proximo_numero_rps na config da clínica).
    """

    ibge_prestador: str
    ibge_prestacao: str
    serie_rps: str
    numero_rps: str
    homologacao: bool
    ws_url: str
    versao_abrasf: str = VERSAO_ABRASF204
    abrasf204: bool = True

    @classmethod
    def resolver(
        cls,
        ibge: str,
        *,
        homologacao: bool,
        serie_rps: str | None = None,
        proximo_numero_rps: str | None = None,
        rps_serie_payload: str | None = None,
        rps_numero_payload: str | None = None,
        ws_url: str | None = None,
    ) -> ContextoRpsContribuinte:
        ibge7 = normalizar_ibge(ibge)
        cfg = params_municipio(ibge7)
        abrasf204 = cfg is not None
        serie = serie_rps_emissao(
            ibge7,
            homologacao,
            serie_config=serie_rps,
            serie_payload=rps_serie_payload,
        )
        numero = str(rps_numero_payload or proximo_numero_rps or "1").strip()
        return cls(
            ibge_prestador=ibge7,
            ibge_prestacao=ibge_prestacao_servico(ibge7, homologacao),
            serie_rps=serie,
            numero_rps=numero,
            homologacao=homologacao,
            ws_url=url_webservice(ibge7, homologacao, ws_url),
            versao_abrasf=VERSAO_ABRASF204 if abrasf204 else "2.01",
            abrasf204=abrasf204,
        )
