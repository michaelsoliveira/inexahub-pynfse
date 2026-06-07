# Serialização XML para NFS-e Padrão Nacional v1.01
# Manual NotaControl/ISS.net — usa lxml diretamente (sem PyXB)

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from lxml import etree

from pynfe.entidades.dps import DPS, LoteDPS
from pynfe.utils.nfse.nacional import (
    ISSNET_HOMOLOGACAO_CLOC_EMI,
    NAMESPACE_NFSE_NACIONAL,
    VERSAO_NFSE_NACIONAL,
)
from pynfe.utils.nfse.nacional.id_dps import (
    format_n_dps_id_nacional,
    format_n_dps_portal,
    format_serie_elemento_portal,
    format_serie_portal,
    gerar_id_dps,
    tp_inscr_from_prestador,
)

NS = NAMESPACE_NFSE_NACIONAL

# NBS padrão por serviço de saúde (lista 04.01)
_NBS_POR_TRIB_NAC = {
    "040101": "123012200",
    "040201": "123012200",
    "040301": "123012200",
}


def _tag(pai: etree._Element, local: str, texto=None) -> etree._Element:
    el = etree.SubElement(pai, "{%s}%s" % (NS, local))
    if texto is not None:
        el.text = str(texto)
    return el


def _formatar_decimal(valor) -> Optional[str]:
    if valor is None:
        return None
    return "{:.2f}".format(valor)


def _c_trib_mun_from_nacional(cod_nacional: str) -> Optional[str]:
    """
    Deriva cTribMun (3 díg.) a partir de cTribNac (6 díg.).
    Ex.: 040101 → item 04, subitem 01 → serviço 4.01 → 401.
    """
    nac = "".join(c for c in str(cod_nacional or "") if c.isdigit())
    if len(nac) < 4:
        return None
    item = int(nac[0:2])
    subitem = nac[2:4]
    derived = f"{item}{subitem}"
    if len(derived) <= 3:
        return derived.zfill(3)
    return derived[-3:]


def _normalizar_cod_trib_municipal(cod_nacional: str, cod_municipal: str = None) -> Optional[str]:
    """TCCodTribMun — exatamente 3 dígitos numéricos."""
    digits = "".join(c for c in str(cod_municipal or "") if c.isdigit())
    if len(digits) == 3:
        return digits
    if len(digits) == 6:
        return _c_trib_mun_from_nacional(digits)
    if len(digits) > 3:
        return digits[-3:]
    return _c_trib_mun_from_nacional(cod_nacional)


def _format_c_trib_mun(cod_nacional: str, cod_municipal: str = None) -> str:
    """cTribMun layout ISS.net validado: 6 dígitos (mesmo formato de cTribNac)."""
    mun_digits = "".join(c for c in str(cod_municipal or "") if c.isdigit())
    if len(mun_digits) == 6:
        return mun_digits.zfill(6)[-6:]
    nac = "".join(c for c in str(cod_nacional or "") if c.isdigit()).zfill(6)[-6:]
    return nac


def _format_c_trib_mun_issnet(cod_nacional: str, cod_municipal: str, cod_ibge: str) -> str:
    """Layout legado ISSNet: IBGE(7) + código municipal (3)."""
    ibge = "".join(c for c in str(cod_ibge or "") if c.isdigit()).zfill(7)[:7]
    mun = _normalizar_cod_trib_municipal(cod_nacional, cod_municipal) or "401"
    return f"{ibge}{mun}"


def _resolver_cod_nbs(cod_trib_nac: str, cod_nbs: str = None) -> str:
    if cod_nbs:
        return "".join(c for c in str(cod_nbs) if c.isdigit())[:9]
    nac = "".join(c for c in str(cod_trib_nac or "") if c.isdigit()).zfill(6)[-6:]
    return _NBS_POR_TRIB_NAC.get(nac, "123012200")


def _format_n_dps(numero) -> str:
    return format_n_dps_id_nacional(numero)


def _format_n_dps_elemento(numero) -> str:
    return format_n_dps_portal(numero)


def _format_serie_id(serie) -> str:
    return format_serie_portal(serie)


def _format_serie_elemento(serie) -> str:
    return format_serie_elemento_portal(serie)


def _format_numero_lote(numero: str) -> str:
    digits = "".join(c for c in str(numero) if c.isdigit())
    n = int(digits) if digits else 1
    return str(n).zfill(15)


def _id_lote(numero: str) -> str:
    digits = "".join(c for c in str(numero) if c.isdigit())
    n = int(digits) if digits else 1
    return f"Lote{n}"


def resolve_cod_municipio_emissao(cod_ibge: str, homologacao: bool, portal: bool = False) -> str:
    """
    Código IBGE do município emissor (cLocEmi / Id da DPS).

    portal=True (Macapá/ISSNet): produção usa IBGE real; homolog usa Campo Grande.
    portal=False: homolog usa Campo Grande; produção usa IBGE informado.
    """
    cod = "".join(c for c in str(cod_ibge or "") if c.isdigit()).zfill(7)[:7]
    if homologacao:
        if portal:
            return "5002704"
        return ISSNET_HOMOLOGACAO_CLOC_EMI
    return cod or ISSNET_HOMOLOGACAO_CLOC_EMI


def _doc_prestador(prest) -> tuple[str, str]:
    if getattr(prest, "cnpj", None):
        return "2", "".join(c for c in prest.cnpj if c.isdigit()).zfill(14)[-14:]
    cpf = "".join(c for c in (prest.cpf or "") if c.isdigit()).zfill(11)[-11:]
    return "1", cpf


def _dh_emi_str(dps: DPS) -> str:
    dh = dps.data_hora_emissao or datetime.datetime.now()
    if hasattr(dh, "strftime"):
        if dh.tzinfo is None:
            return dh.strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"
        return dh.isoformat(timespec="seconds")
    return str(dh)


def _data_competencia_str(dps: DPS) -> str:
    dc = dps.data_competencia
    if hasattr(dc, "strftime"):
        return dc.strftime("%Y-%m-%d")
    return str(dc)


def _serializar_prestador(pai, prest) -> None:
    prest_el = _tag(pai, "prest")
    if prest.cnpj:
        _tag(prest_el, "CNPJ", "".join(c for c in prest.cnpj if c.isdigit()).zfill(14)[-14:])
    elif prest.cpf:
        _tag(prest_el, "CPF", "".join(c for c in prest.cpf if c.isdigit()).zfill(11)[-11:])
    if prest.inscricao_municipal:
        _tag(prest_el, "IM", prest.inscricao_municipal)
    reg = _tag(prest_el, "regTrib")
    _tag(reg, "opSimpNac", prest.opcao_simples_nacional or 1)
    if prest.regime_apuracao_simples is not None and int(prest.opcao_simples_nacional or 1) == 3:
        _tag(reg, "regApTribSN", prest.regime_apuracao_simples)
    _tag(reg, "regEspTrib", prest.regime_especial_tributacao or 0)


def _serializar_tomador(pai, toma) -> None:
    toma_el = _tag(pai, "toma")
    if toma.cnpj:
        _tag(toma_el, "CNPJ", "".join(c for c in toma.cnpj if c.isdigit()).zfill(14)[-14:])
    elif toma.cpf:
        _tag(toma_el, "CPF", "".join(c for c in toma.cpf if c.isdigit()).zfill(11)[-11:])
    if toma.razao_social:
        _tag(toma_el, "xNome", toma.razao_social[:150])
    if toma.cod_municipio or toma.cep or toma.logradouro:
        end_el = _tag(toma_el, "end")
        if toma.cod_municipio or toma.cep:
            end_nac = _tag(end_el, "endNac")
            if toma.cod_municipio:
                _tag(end_nac, "cMun", "".join(c for c in toma.cod_municipio if c.isdigit()).zfill(7)[:7])
            if toma.cep:
                _tag(end_nac, "CEP", "".join(c for c in toma.cep if c.isdigit())[:8])
        if toma.logradouro:
            _tag(end_el, "xLgr", toma.logradouro[:255])
        if toma.numero:
            _tag(end_el, "nro", toma.numero[:60])
        if toma.complemento:
            _tag(end_el, "xCpl", toma.complemento[:156])
        if toma.bairro:
            _tag(end_el, "xBairro", toma.bairro[:60])
    if toma.telefone:
        _tag(toma_el, "fone", toma.telefone[:15])
    if toma.email:
        _tag(toma_el, "email", toma.email[:80])


def _serializar_servico(pai, serv, dps: DPS) -> None:
    serv_el = _tag(pai, "serv")
    if serv.local_prestacao and serv.local_prestacao.cod_municipio:
        loc = _tag(serv_el, "locPrest")
        _tag(loc, "cLocPrestacao", serv.local_prestacao.cod_municipio)
    cod = serv.codigo
    if cod:
        c_serv = _tag(serv_el, "cServ")
        trib_nac = "".join(c for c in (cod.cod_tributacao_nacional or "") if c.isdigit()).zfill(6)[-6:]
        _tag(c_serv, "cTribNac", trib_nac)
        trib_mun = _normalizar_cod_trib_municipal(trib_nac, cod.cod_tributacao_municipal)
        if trib_mun:
            _tag(c_serv, "cTribMun", trib_mun)
        if cod.descricao_servico:
            _tag(c_serv, "xDescServ", cod.descricao_servico[:2000])
        nbs = _resolver_cod_nbs(trib_nac, cod.cod_nbs)
        _tag(c_serv, "cNBS", nbs)


def _serializar_tributacao(val_el, tributacao) -> None:
    trib_el = _tag(val_el, "trib")
    trib_mun = tributacao.trib_municipal
    if trib_mun:
        tm = _tag(trib_el, "tribMun")
        _tag(tm, "tribISSQN", trib_mun.tributacao_issqn or 1)
        _tag(tm, "tpRetISSQN", trib_mun.tipo_retencao_issqn or 1)
        if trib_mun.aliquota is not None:
            _tag(tm, "pAliq", _formatar_decimal(trib_mun.aliquota))
    tot = _tag(trib_el, "totTrib")
    if tributacao.p_tot_trib_sn is not None:
        _tag(tot, "pTotTribSN", _formatar_decimal(tributacao.p_tot_trib_sn))
    elif tributacao.ind_tot_trib is not None:
        _tag(tot, "indTotTrib", tributacao.ind_tot_trib)
    else:
        _tag(tot, "indTotTrib", 0)


def _serializar_valores(pai, valores) -> etree._Element:
    val_el = _tag(pai, "valores")
    vsp = _tag(val_el, "vServPrest")
    _tag(vsp, "vServ", _formatar_decimal(valores.valor_servico))
    if valores.tributacao:
        _serializar_tributacao(val_el, valores.tributacao)
    return val_el


def _serializar_ibscbs(pai, dps: DPS) -> None:
    """Grupo IBSCBS — obrigatório no schema ISS.net v1.01."""
    ibscbs_el = _tag(pai, "IBSCBS")
    _tag(ibscbs_el, "finNFSe", 0)
    _tag(ibscbs_el, "indFinal", 1)
    _tag(ibscbs_el, "cIndOp", getattr(dps, "ibscbs_c_ind_op", None) or "010101")
    _tag(ibscbs_el, "indDest", 0)

    toma = dps.tomador
    modo = getattr(dps, "ibscbs_modo", "minimo") or "minimo"
    if dps.incluir_ibscbs and modo == "completo" and toma and int(dps.ambiente or 2) == 1:
        dest_el = _tag(ibscbs_el, "dest")
        if toma.cnpj:
            _tag(dest_el, "CNPJ", "".join(c for c in toma.cnpj if c.isdigit()).zfill(14)[-14:])
        elif toma.cpf:
            _tag(dest_el, "CPF", "".join(c for c in toma.cpf if c.isdigit()).zfill(11)[-11:])
        if toma.razao_social:
            _tag(dest_el, "xNome", toma.razao_social[:150])

    valores_el = _tag(ibscbs_el, "valores")
    trib_el = _tag(valores_el, "trib")
    gib = _tag(trib_el, "gIBSCBS")
    _tag(gib, "CST", "000")
    _tag(gib, "cClassTrib", "000001")


def resolver_id_dps(dps: DPS) -> str:
    """Retorna o atributo Id (TSIdDPS, 45 chars) para uma entidade DPS."""
    prest = dps.prestador
    tp_inscr, inscr = _doc_prestador(prest)
    id_modo = getattr(dps, "id_dps_modo", "issnet_portal") or "issnet_portal"
    return gerar_id_dps(
        dps.cod_municipio_emissao,
        tp_inscr,
        inscr,
        dps.serie,
        dps.numero_dps,
        modo=id_modo,
    )


def serializar_dps(dps: DPS) -> etree._Element:
    """Serializa uma DPS (sem assinatura) para NFS-e Nacional v1.01."""
    raiz = etree.Element(
        "{%s}DPS" % NS,
        nsmap={None: NS},
        versao=VERSAO_NFSE_NACIONAL,
    )
    prest = dps.prestador
    id_dps = resolver_id_dps(dps)
    inf = etree.SubElement(raiz, "{%s}infDPS" % NS, Id=id_dps)
    _tag(inf, "tpAmb", dps.ambiente or 2)
    _tag(inf, "dhEmi", _dh_emi_str(dps))
    if dps.versao_aplicativo:
        _tag(inf, "verAplic", dps.versao_aplicativo[:20])
    _tag(inf, "serie", _format_serie_elemento(dps.serie))
    _tag(inf, "nDPS", _format_n_dps_elemento(dps.numero_dps))
    _tag(inf, "dCompet", _data_competencia_str(dps))
    _tag(inf, "tpEmit", dps.tipo_emitente or 1)
    _tag(inf, "cLocEmi", dps.cod_municipio_emissao)

    if prest:
        _serializar_prestador(inf, prest)
    if dps.tomador:
        _serializar_tomador(inf, dps.tomador)
    if dps.servico:
        _serializar_servico(inf, dps.servico, dps)
    if dps.valores:
        _serializar_valores(inf, dps.valores)
    _serializar_ibscbs(inf, dps)
    return raiz


def _prestador_lote_element(lote: LoteDPS) -> etree._Element:
    prest = etree.Element("{%s}Prestador" % NS)
    if lote.prestador_cpf:
        _tag(prest, "CPF", "".join(c for c in lote.prestador_cpf if c.isdigit()).zfill(11)[-11:])
    else:
        _tag(prest, "CNPJ", "".join(c for c in lote.prestador_cnpj if c.isdigit()).zfill(14)[-14:])
    if lote.prestador_inscricao_municipal:
        _tag(prest, "IM", lote.prestador_inscricao_municipal)
    return prest


def _montar_lote_xml(lote: LoteDPS, dps_assinadas: list, tag_raiz: str) -> etree._Element:
    raiz = etree.Element("{%s}%s" % (NS, tag_raiz), nsmap={None: NS})
    num_fmt = _format_numero_lote(lote.numero_lote)
    lote_el = etree.SubElement(
        raiz,
        "{%s}LoteDps" % NS,
        Id=_id_lote(lote.numero_lote),
        versao=VERSAO_NFSE_NACIONAL,
    )
    _tag(lote_el, "NumeroLote", num_fmt)
    lote_el.append(_prestador_lote_element(lote))
    _tag(lote_el, "QuantidadeDps", len(dps_assinadas))
    if dps_assinadas:
        lista = _tag(lote_el, "ListaDps")
        for dps_xml in dps_assinadas:
            lista.append(dps_xml)
    return raiz


def serializar_lote_sincrono(lote: LoteDPS, dps_assinadas: list) -> etree._Element:
    return _montar_lote_xml(lote, dps_assinadas, "EnviarLoteDpsSincronoEnvio")


def serializar_lote_assincrono(lote: LoteDPS, dps_assinadas: list) -> etree._Element:
    return _montar_lote_xml(lote, dps_assinadas, "RecepcionarLoteDpsEnvio")


def _prestador_consulta(pai, doc: str, im: str, usar_cpf: bool = False) -> None:
    prest = _tag(pai, "Prestador")
    digits = "".join(c for c in doc if c.isdigit())
    if usar_cpf or len(digits) == 11:
        _tag(prest, "CPF", digits.zfill(11)[-11:])
    else:
        _tag(prest, "CNPJ", digits.zfill(14)[-14:])
    if im:
        _tag(prest, "IM", im)


def serializar_cancelar_nfse(chave_nfse: str, codigo_motivo: int, motivo: str) -> etree._Element:
    ped = etree.Element("{%s}pedRegEvento" % NS, nsmap={None: NS}, versao=VERSAO_NFSE_NACIONAL)
    inf = etree.SubElement(ped, "{%s}infPedReg" % NS, Id=f"PRE{chave_nfse}"[:45])
    _tag(inf, "tpAmb", 2)
    _tag(inf, "dhEvento", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + "-03:00")
    _tag(inf, "chNFSe", chave_nfse)
    _tag(inf, "nPedRegEvento", 1)
    det = _tag(inf, "e101101")
    _tag(det, "xDesc", "Cancelamento de NFS-e")
    _tag(det, "cMotivo", codigo_motivo)
    _tag(det, "xMotivo", (motivo or "")[:255])
    return ped


def serializar_consultar_lote(
    prestador_doc: str,
    prestador_im: str,
    protocolo: str,
    usar_cpf: bool = False,
) -> etree._Element:
    raiz = etree.Element("{%s}ConsultarLoteDpsEnvio" % NS, nsmap={None: NS})
    _prestador_consulta(raiz, prestador_doc, prestador_im, usar_cpf=usar_cpf)
    _tag(raiz, "Protocolo", protocolo)
    return raiz


def serializar_consultar_nfse_por_dps(
    prestador_doc: str,
    prestador_im: str,
    serie: str,
    numero_dps: str,
    usar_cpf: bool = False,
) -> etree._Element:
    raiz = etree.Element("{%s}ConsultarNfseDpsEnvio" % NS, nsmap={None: NS})
    _prestador_consulta(raiz, prestador_doc, prestador_im, usar_cpf=usar_cpf)
    _tag(raiz, "Serie", _format_serie_elemento(serie))
    _tag(raiz, "NumeroDps", _format_n_dps_elemento(numero_dps))
    return raiz


def serializar_consultar_nfse_servico_prestado(
    prestador_doc: str,
    prestador_im: str,
    numero_nfse: str = None,
    data_inicial: str = None,
    data_final: str = None,
    pagina: int = 1,
    usar_cpf: bool = False,
) -> etree._Element:
    raiz = etree.Element("{%s}ConsultarNfseServicoPrestadoEnvio" % NS, nsmap={None: NS})
    _prestador_consulta(raiz, prestador_doc, prestador_im, usar_cpf=usar_cpf)
    if numero_nfse:
        _tag(raiz, "NumeroNfse", numero_nfse)
    if data_inicial:
        _tag(raiz, "DataInicial", data_inicial)
    if data_final:
        _tag(raiz, "DataFinal", data_final)
    _tag(raiz, "Pagina", pagina)
    return raiz


def serializar_consultar_dados_cadastrais(prestador_cnpj: str, prestador_im: str) -> etree._Element:
    raiz = etree.Element("{%s}ConsultarDadosCadastraisEnvio" % NS, nsmap={None: NS})
    _prestador_consulta(raiz, prestador_cnpj, prestador_im, usar_cpf=False)
    return raiz


def serializar_consultar_dps_disponivel(
    prestador_doc: str,
    prestador_im: str,
    pagina: int = 1,
    usar_cpf: bool = False,
) -> etree._Element:
    raiz = etree.Element("{%s}ConsultarDpsDisponivelEnvio" % NS, nsmap={None: NS})
    _prestador_consulta(raiz, prestador_doc, prestador_im, usar_cpf=usar_cpf)
    _tag(raiz, "Pagina", pagina)
    return raiz


def serializar_consultar_url_nfse(
    prestador_doc: str,
    prestador_im: str,
    numero_nfse: str = None,
    data_inicial: str = None,
    data_final: str = None,
    pagina: int = 1,
    usar_cpf: bool = False,
) -> etree._Element:
    raiz = etree.Element("{%s}ConsultarUrlNfseEnvio" % NS, nsmap={None: NS})
    _prestador_consulta(raiz, prestador_doc, prestador_im, usar_cpf=usar_cpf)
    if numero_nfse:
        _tag(raiz, "NumeroNfse", numero_nfse)
    if data_inicial:
        _tag(raiz, "DataInicial", data_inicial)
    if data_final:
        _tag(raiz, "DataFinal", data_final)
    _tag(raiz, "Pagina", pagina)
    return raiz
