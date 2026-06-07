# NFS-e Municipal via ISSNet Online — ABRASF 2.04 (RPS) e legado 2.01
#
# Macapá/AP: webservice oficial ABRASF 2.04 (Nota Control), não DPS Nacional.
# Portal web pode gerar DPS; integração SOAP para terceiros usa RPS + faixa autorizada.

VERSAO_ABRASF = "2.01"

# Namespace dos elementos de dados (schema ABRASF)
NAMESPACE_ABRASF = "http://www.abrasf.org.br/nfse.xsd"

# Namespace do wrapper de serviço no envelope SOAP (específico ISSNet legado v2.01)
NAMESPACE_SERVICO_ISSNET = "http://www.issnetonline.com.br/webservices/nfse"

# ABRASF 2.04 (Nota Control / ISSNet abrasf204) — namespace padrão do WSDL
NAMESPACE_SERVICO_ABRASF204 = "http://nfse.abrasf.org.br"
VERSAO_ABRASF204 = "2.04"
# Atributo versao do elemento <cabecalho> em endpoints Nota Control 2.04
VERSAO_CABECALHO_ABRASF204 = "2.04"

# URL padrão do webservice ISSNet por cidade
# Padrão: https://www.issnetonline.com.br/{cidade}/Servicos/ServicoNFSe.asmx
ISSNET_URL_PADRAO = "https://www.issnetonline.com.br/{cidade}/Servicos/ServicoNFSe.asmx"

# URL do portal online (para consulta manual)
ISSNET_PORTAL_PADRAO = "https://www.issnetonline.com.br/{cidade}/online/Default/Master.aspx"

# Métodos SOAP disponíveis
METODO_RECEPCIONAR_LOTE_SINCRONO = "RecepcionarLoteRpsSincrono"
METODO_RECEPCIONAR_LOTE = "RecepcionarLoteRps"
METODO_GERAR_NFSE = "GerarNfse"
METODO_CANCELAR_NFSE = "CancelarNfse"
METODO_CONSULTAR_NFSE = "ConsultarNfse"
METODO_CONSULTAR_NFSE_POR_RPS = "ConsultarNfsePorRps"
METODO_CONSULTAR_LOTE_RPS = "ConsultarLoteRps"
METODO_CONSULTAR_SITUACAO_LOTE = "ConsultarSituacaoLoteRps"

# Tipo de RPS
TIPO_RPS_NORMAL = 1
TIPO_RPS_MISTO = 2
TIPO_RPS_CUPOM = 3

# Status do RPS: 1=Normal
STATUS_RPS_NORMAL = 1

# Natureza da Operação ISSQN
NATUREZA_MUNICIPIO = 1
NATUREZA_FORA_MUNICIPIO = 2
NATUREZA_ISENCAO = 3
NATUREZA_IMUNE = 4
NATUREZA_SUSPENSA_JUDICIAL = 5
NATUREZA_SUSPENSA_ADMIN = 6

# ISS Retido: 1=Sim, 2=Não
ISS_RETIDO_SIM = 1
ISS_RETIDO_NAO = 2

# Simples Nacional: 1=Sim, 2=Não
SIMPLES_SIM = 1
SIMPLES_NAO = 2

# Incentivador Cultural: 1=Sim, 2=Não
INCENTIVADOR_SIM = 1
INCENTIVADOR_NAO = 2

# Regime Especial de Tributação
REG_ESP_MICROEMPRESA_MUNICIPAL = 1
REG_ESP_ESTIMATIVA = 2
REG_ESP_SOCIEDADE_PROFISSIONAIS = 3
REG_ESP_COOPERATIVA = 4
REG_ESP_MEI = 5
REG_ESP_ME_EPP = 6

# Exigibilidade ISS
EXIG_EXIGIVEL = 1
EXIG_NAO_INCIDENCIA = 2
EXIG_ISENCAO = 3
EXIG_EXPORTACAO = 4
EXIG_IMUNIDADE = 5
EXIG_SUSPENSA_JUDICIAL = 6
EXIG_SUSPENSA_ADMIN = 7

# País Brasil
CODIGO_PAIS_BRASIL = "1058"

# Cidades conhecidas no ISSNet Online (slug na URL legado v2.01)
ISSNET_CIDADES = {
    "1600303": "macapa",   # Macapá/AP — ver abrasf204.ISSNET_ABRASF204 para URL oficial 2.04
}


def detectar_layout_issnet(url: str) -> str:
    """
    Detecta layout SOAP ISSNet a partir da URL do webservice.

    Retorna ``abrasf204`` (Nota Control) ou ``issnet201`` (legado v2.01).
    """
    u = (url or "").lower()
    if any(
        token in u
        for token in ("abrasf204", "homologaabrasf", "webservicenfse204")
    ):
        return "abrasf204"
    return "issnet201"


def namespace_servico_por_url(url: str) -> str:
    """Namespace SOAP do wrapper conforme URL do webservice."""
    if detectar_layout_issnet(url) == "abrasf204":
        return NAMESPACE_SERVICO_ABRASF204
    return NAMESPACE_SERVICO_ISSNET


def versao_abrasf_por_url(url: str) -> str:
    """Versão ABRASF dos dados (cabecalho/lote/RPS) conforme URL."""
    if detectar_layout_issnet(url) == "abrasf204":
        return VERSAO_ABRASF204
    return VERSAO_ABRASF


def issnet_abrasf204_params(ibge: str) -> dict[str, str] | None:
    """Parâmetros oficiais ISSNet ABRASF 2.04 por IBGE, ou None."""
    from pynfe.utils.nfse.issnet.abrasf204 import params_municipio

    return params_municipio(ibge)


def url_por_municipio(ibge: str, homologacao: bool = False) -> str:
    """URL do webservice ISSNet por IBGE (ABRASF 2.04 prioritário)."""
    from pynfe.utils.nfse.issnet.abrasf204 import url_webservice

    return url_webservice(ibge, homologacao)


def format_provider_reference_id(serie: str, numero: str) -> str:
    """
    Referência interna para consulta por RPS.

    Formato: ``{serie}:{numero}`` (sem prefixo ``RPS`` — evita ``RPSRPS...`` quando
    a série configurada já é ``RPS``).
    """
    serie_norm = (serie or "A").strip()
    digits = "".join(c for c in str(numero) if c.isdigit()) or "1"
    return "%s:%s" % (serie_norm, digits.zfill(15))


def parse_provider_reference_id(ref: str) -> tuple[str, str]:
    """
    Decodifica ``format_provider_reference_id`` e o formato legado ``RPS{serie}{num15}``.
    """
    ref = (ref or "").strip()
    if not ref:
        return "A", "1"

    if ":" in ref:
        serie, numero = ref.split(":", 1)
        return serie.strip() or "A", numero.lstrip("0") or "1"

    if ref.startswith("RPS") and len(ref) > 3:
        resto = ref[3:]
        if len(resto) > 15:
            return resto[:-15] or "A", resto[-15:].lstrip("0") or "1"
        return "A", resto.lstrip("0") or "1"

    return "A", ref.lstrip("0") or "1"


from pynfe.utils.nfse.issnet.abrasf204 import (  # noqa: E402
    ISSNET_ABRASF204,
    ContextoRpsContribuinte,
    normalizar_ibge,
    params_municipio,
    serie_rps_emissao,
    ibge_prestacao_servico,
    item_lista_lc116,
    aliquota_xml_valor,
    iss_retido_para_tomador,
    suporta_abrasf204,
    url_webservice,
)
