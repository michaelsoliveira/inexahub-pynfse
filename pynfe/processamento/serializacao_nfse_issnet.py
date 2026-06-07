"""Serialização XML ABRASF v2.01 / v2.04 para ISSNet (RPS)."""
from lxml import etree

from pynfe.utils.nfse.issnet import (
    VERSAO_ABRASF,
    VERSAO_ABRASF204,
    NAMESPACE_ABRASF,
    ISS_RETIDO_SIM,
    ISS_RETIDO_NAO,
    TIPO_RPS_NORMAL,
    STATUS_RPS_NORMAL,
    NATUREZA_MUNICIPIO,
    SIMPLES_NAO,
    INCENTIVADOR_NAO,
    EXIG_EXIGIVEL,
    CODIGO_PAIS_BRASIL,
)

NS = NAMESPACE_ABRASF
DSIG_NS = "http://www.w3.org/2000/09/xmldsig#"


def _sub(parent: etree._Element, tag: str, text: str = None) -> etree._Element:
    el = etree.SubElement(parent, "{%s}%s" % (NS, tag))
    if text is not None:
        el.text = str(text)
    return el


def _cpf_cnpj_element(parent: etree._Element, doc: str) -> None:
    cpf_cnpj = _sub(parent, "CpfCnpj")
    doc_digits = "".join(c for c in (doc or "") if c.isdigit())
    if len(doc_digits) == 11:
        _sub(cpf_cnpj, "Cpf", doc_digits)
    else:
        _sub(cpf_cnpj, "Cnpj", doc_digits.zfill(14))


def _is_abrasf204(versao_abrasf: str) -> bool:
    return (versao_abrasf or "").strip() == VERSAO_ABRASF204


def empacotar_rps_assinado(inf_ou_rps: etree._Element) -> etree._Element:
    """
    ABRASF tcDeclaracaoPrestacaoServico: Signature é irmã de InfDeclaracaoPrestacaoServico.

    signxml enveloped deixa Signature dentro de Inf*; ISSNet/Nota Control rejeita (HTTP 500).
    """
    if etree.QName(inf_ou_rps.tag).localname == "Rps":
        return inf_ou_rps

    sig = None
    for child in list(inf_ou_rps):
        if etree.QName(child.tag).localname == "Signature":
            sig = child
            inf_ou_rps.remove(child)
            break

    wrapper = etree.Element("{%s}Rps" % NS)
    wrapper.append(inf_ou_rps)
    if sig is not None:
        wrapper.append(sig)
    return wrapper


def empacotar_lote_assinado(envio_xml: etree._Element) -> etree._Element:
    """
    ABRASF 2.04: assinatura do lote é irmã de LoteRps em EnviarLoteRps*Envio.

    signxml enveloped deixa Signature dentro de LoteRps; o schema ISSNet espera
    Signature como filho direto de EnviarLoteRpsSincronoEnvio.
    """
    lote = envio_xml.find(".//{%s}LoteRps" % NS)
    if lote is None:
        return envio_xml

    sig = None
    for child in list(lote):
        if etree.QName(child.tag).localname == "Signature":
            sig = child
            lote.remove(child)
            break

    if sig is not None:
        envio_xml.append(sig)
    return envio_xml


def serializar_rps(rps: dict, versao_abrasf: str = VERSAO_ABRASF) -> etree._Element:
    if _is_abrasf204(versao_abrasf):
        return _serializar_rps_v204(rps, versao_abrasf)
    return _serializar_rps_v201(rps, versao_abrasf)


def _serializar_rps_v201(rps: dict, versao_abrasf: str) -> etree._Element:
    numero = str(rps.get("numero", "1"))
    inf = etree.Element(
        "{%s}InfDeclaracaoPrestacaoServico" % NS,
        Id="InfPS%s" % numero,
        versao=versao_abrasf,
        nsmap={None: NS},
    )
    rps_el = _sub(inf, "Rps")
    id_rps = _sub(rps_el, "IdentificacaoRps")
    _sub(id_rps, "Numero", numero)
    _sub(id_rps, "Serie", rps.get("serie", "A"))
    _sub(id_rps, "Tipo", rps.get("tipo", TIPO_RPS_NORMAL))
    _sub(rps_el, "DataEmissao", rps.get("data_emissao"))
    _sub(rps_el, "NaturezaOperacao", rps.get("natureza_operacao", NATUREZA_MUNICIPIO))
    regime = rps.get("regime_especial", 0)
    if regime and int(regime) > 0:
        _sub(rps_el, "RegimeEspecialTributacao", regime)
    _sub(rps_el, "OptanteSimplesNacional", rps.get("simples", SIMPLES_NAO))
    _sub(rps_el, "IncentivadorCultural", rps.get("incentivo", INCENTIVADOR_NAO))
    _sub(rps_el, "Status", STATUS_RPS_NORMAL)
    _sub(inf, "Competencia", rps.get("competencia"))
    _append_servico(inf, rps, abrasf204=False)
    _append_prestador(inf, rps)
    _append_tomador(inf, rps, "Tomador", True, True)
    return inf


def _serializar_rps_v204(rps: dict, versao_abrasf: str) -> etree._Element:
    numero = str(rps.get("numero", "1"))
    inf = etree.Element(
        "{%s}InfDeclaracaoPrestacaoServico" % NS,
        Id="InfPS%s" % numero,
        versao=versao_abrasf,
        nsmap={None: NS},
    )
    rps_el = _sub(inf, "Rps")
    id_rps = _sub(rps_el, "IdentificacaoRps")
    _sub(id_rps, "Numero", numero)
    _sub(id_rps, "Serie", rps.get("serie", "A"))
    _sub(id_rps, "Tipo", rps.get("tipo", TIPO_RPS_NORMAL))
    _sub(rps_el, "DataEmissao", rps.get("data_emissao"))
    _sub(rps_el, "Status", STATUS_RPS_NORMAL)
    _sub(inf, "Competencia", rps.get("competencia"))
    _append_servico(inf, rps, abrasf204=True)
    _append_prestador(inf, rps)
    _append_tomador(inf, rps, "TomadorServico", True, False)
    regime = rps.get("regime_especial", 0)
    if regime and int(regime) > 0:
        _sub(inf, "RegimeEspecialTributacao", regime)
    _sub(inf, "OptanteSimplesNacional", rps.get("simples", SIMPLES_NAO))
    _sub(inf, "IncentivoFiscal", rps.get("incentivo", INCENTIVADOR_NAO))
    return inf


def _append_servico(parent: etree._Element, rps: dict, abrasf204: bool) -> None:
    serv_el = _sub(parent, "Servico")
    valores_el = _sub(serv_el, "Valores")
    valor_servico = _fmt_valor(rps.get("valor_servico", "0"))
    _sub(valores_el, "ValorServicos", valor_servico)
    _opt_valor(valores_el, "ValorDeducoes", rps.get("valor_deducoes"))
    aliq = rps.get("aliquota")
    if aliq is not None:
        aliq_str = _fmt_aliquota(aliq, abrasf204=abrasf204)
        if abrasf204:
            try:
                aliq_num = float(str(aliq))
                frac = aliq_num / 100.0 if aliq_num > 1 else aliq_num
                _sub(valores_el, "ValorIss", _fmt_valor(float(valor_servico) * frac))
            except (ValueError, TypeError):
                pass
        _sub(valores_el, "Aliquota", aliq_str)
    iss_retido = rps.get("iss_retido", ISS_RETIDO_NAO)
    _sub(serv_el, "IssRetido", iss_retido)
    if abrasf204 and int(iss_retido) == ISS_RETIDO_SIM:
        _sub(serv_el, "ResponsavelRetencao", 1)
    _sub(serv_el, "ItemListaServico", rps.get("item_lista_servico", ""))
    if rps.get("cod_cnae"):
        _sub(serv_el, "CodigoCnae", rps["cod_cnae"])
    if rps.get("cod_tributacao_mun"):
        _sub(serv_el, "CodigoTributacaoMunicipio", rps["cod_tributacao_mun"])
    _sub(serv_el, "Discriminacao", rps.get("discriminacao", ""))
    _sub(serv_el, "CodigoMunicipio", rps.get("cod_municipio", ""))
    if not abrasf204:
        _sub(serv_el, "CodigoPais", rps.get("cod_pais", CODIGO_PAIS_BRASIL))
    _sub(serv_el, "ExigibilidadeISS", rps.get("exigibilidade_iss", EXIG_EXIGIVEL))
    _sub(serv_el, "MunicipioIncidencia", rps.get("municipio_incidencia") or rps.get("cod_municipio", ""))


def _append_prestador(parent: etree._Element, rps: dict) -> None:
    prest_el = _sub(parent, "Prestador")
    _cpf_cnpj_element(prest_el, rps.get("prest_cnpj_cpf", ""))
    if rps.get("prest_im"):
        _sub(prest_el, "InscricaoMunicipal", rps["prest_im"])


def _append_tomador(
    parent: etree._Element,
    rps: dict,
    tag_tomador: str,
    incluir_contato: bool,
    incluir_cod_pais_endereco: bool,
) -> None:
    toma_doc = rps.get("toma_cnpj_cpf", "")
    toma_nome = rps.get("toma_razao_social", "")
    if not toma_doc and not toma_nome:
        return
    toma_el = _sub(parent, tag_tomador)
    id_toma = _sub(toma_el, "IdentificacaoTomador")
    _cpf_cnpj_element(id_toma, toma_doc)
    if toma_nome:
        _sub(toma_el, "RazaoSocial", toma_nome)
    # ABRASF tcDadosTomador: Endereco é Choice 1-1 (obrigatório quando TomadorServico presente).
    # Emite bloco sempre, usando "NAO INFORMADO" como placeholder para campos sem dado.
    end_el = _sub(toma_el, "Endereco")
    _sub(end_el, "Endereco", rps.get("toma_endereco") or "NAO INFORMADO")
    _sub(end_el, "Numero", rps.get("toma_numero") or "S/N")
    if rps.get("toma_complemento"):
        _sub(end_el, "Complemento", rps["toma_complemento"])
    _sub(end_el, "Bairro", rps.get("toma_bairro") or "NAO INFORMADO")
    _sub(end_el, "CodigoMunicipio", rps.get("toma_cod_municipio") or "")
    toma_uf = (rps.get("toma_uf") or "").strip().upper()[:2]
    if toma_uf:
        _sub(end_el, "Uf", toma_uf)
    if incluir_cod_pais_endereco:
        _sub(end_el, "CodigoPais", rps.get("toma_cod_pais", CODIGO_PAIS_BRASIL))
    cep_digits = "".join(c for c in rps.get("toma_cep", "") if c.isdigit())
    _sub(end_el, "Cep", cep_digits or "00000000")
    if incluir_contato:
        tel = rps.get("toma_telefone", "")
        email = rps.get("toma_email", "")
        if tel or email:
            contato = _sub(toma_el, "Contato")
            if tel:
                _sub(contato, "Telefone", "".join(c for c in tel if c.isdigit()))
            if email:
                _sub(contato, "Email", email)


def _fmt_valor(v) -> str:
    try:
        return "{:.2f}".format(float(str(v)))
    except (ValueError, TypeError):
        return "0.00"


def _fmt_aliquota(v, abrasf204: bool = False) -> str:
    try:
        val = float(str(v))
    except (ValueError, TypeError):
        return "0.0000" if abrasf204 else "0.00"
    if abrasf204:
        if val > 1:
            val = val / 100.0
        return "{:.4f}".format(val)
    if val <= 1:
        val *= 100.0
    return "{:.2f}".format(val)


def _opt_valor(parent: etree._Element, tag: str, v) -> None:
    if v is None:
        return
    try:
        if float(str(v)) != 0:
            _sub(parent, tag, _fmt_valor(v))
    except (ValueError, TypeError):
        pass


def serializar_lote(
    rps_assinados: list,
    numero_lote: str,
    emitente_cnpj_cpf: str,
    emitente_im: str,
    sincrono: bool = True,
    versao_abrasf: str = VERSAO_ABRASF,
) -> etree._Element:
    tag_raiz = "EnviarLoteRpsSincronoEnvio" if sincrono else "EnviarLoteRpsEnvio"
    raiz = etree.Element("{%s}%s" % (NS, tag_raiz), nsmap={None: NS})
    lote = etree.SubElement(raiz, "{%s}LoteRps" % NS, Id="lote-%s" % numero_lote, versao=versao_abrasf)
    _sub(lote, "NumeroLote", numero_lote)
    # ABRASF tcLoteRps: CpfCnpj/InscricaoMunicipal ficam dentro de <Prestador> (1-1)
    prestador_lote = _sub(lote, "Prestador")
    _cpf_cnpj_element(prestador_lote, emitente_cnpj_cpf)
    if emitente_im:
        _sub(prestador_lote, "InscricaoMunicipal", emitente_im)
    _sub(lote, "QuantidadeRps", len(rps_assinados))
    lista = _sub(lote, "ListaRps")
    for rps_xml in rps_assinados:
        if etree.QName(rps_xml.tag).localname == "Rps":
            lista.append(rps_xml)
        else:
            wrapper = _sub(lista, "Rps")
            wrapper.append(rps_xml)
    return raiz
