# Construtores de entidades DPS a partir de dicionários neutros.
#
# Objetivo: isolar o conhecimento de entidades pynfse (DPS, TomadorDPS, PrestadorDPS…)
# dentro da biblioteca, de forma que consumidores externos (inexahub, outros módulos)
# possam construir uma DPS completa apenas passando dicts de configuração e payload
# sem precisar importar nenhuma entidade pynfse diretamente.
#
# Contratos dos dicionários:
#
#   config  → dados técnicos da integração (vêm de NfseConfiguracaoClinica):
#     ibge                      str 7 dígitos (código IBGE do município)
#     tipo_certificado_nfse     "e_cnpj" | "e_cpf"
#     cnpj                      str 14 dígitos (modo e-CNPJ)
#     cpf                       str 11 dígitos (modo e-CPF)
#     inscricao_municipal       str (IM do prestador)
#     opcao_simples_nacional    int 1|2|3  (1=não optante, 2=MEI, 3=ME/EPP)
#     regime_especial           int 0–6
#     regime_apuracao_simples   int 1|2|3  (opcional — só para opSimpNac=3)
#     nome_prestador            str
#     cod_tributacao_nacional   str 6 dígitos
#     cod_tributacao_municipal  str até 3 dígitos (opcional)
#     descricao_servico         str
#     iss_retido                bool
#     aliquota_iss_percentual   Decimal (ex: 5.00 para 5%) — opcional
#     trib_issqn                int 1–4 (1=tributável, 2=imunidade…)
#     ambiente                  int 1=produção 2=homologação
#     versao_aplicativo         str
#     serie                     str numérica ≤5 dígitos
#     numero_dps                str ≤15 dígitos
#     data_competencia          date
#     cod_municipio_emissao     str 7 dígitos (pode diferir do ibge em homologação)
#
#   tomador → dados do tomador (vêm de load_tomador_from_paciente ou similar):
#     tomador_nome              str
#     tomador_doc               str 11 (CPF) ou 14 (CNPJ) dígitos
#     tomador_cod_municipio     str 7 dígitos (opcional)
#     tomador_cep               str 8 dígitos (opcional)
#     tomador_logradouro        str (opcional)
#     tomador_numero            str (opcional)
#     tomador_complemento       str (opcional)
#     tomador_bairro            str (opcional)
#     tomador_telefone          str dígitos (opcional)
#     tomador_email             str (opcional)

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from pynfe.utils.nfse.nacional.validacao import validar_cpf


def criar_tomador(tomador: Dict[str, Any]):
    """
    Constrói um TomadorDPS a partir de um dict neutro (sem lógica de domínio de saúde).

    Parâmetro:
        tomador  – dict com chaves tomador_* (ver contratos no cabeçalho deste módulo)

    Retorna:
        TomadorDPS ou None se não houver dados suficientes.
    """
    from pynfe.entidades.dps import TomadorDPS

    doc = "".join(c for c in (tomador.get("tomador_doc") or "") if c.isdigit())
    nome = (tomador.get("tomador_nome") or "").strip()

    if not nome and not doc:
        return None

    toma = TomadorDPS()
    toma.razao_social = nome or "Não identificado"

    if len(doc) == 14:
        toma.cnpj = doc
    elif len(doc) == 11:
        if not validar_cpf(doc):
            raise ValueError(
                f"CPF do tomador inválido (dígito verificador): {doc}. "
                "Corrija o CPF no cadastro do paciente."
            )
        toma.cpf = doc

    cod_mun = (tomador.get("tomador_cod_municipio") or "")
    if cod_mun:
        toma.cod_municipio = "".join(c for c in str(cod_mun) if c.isdigit()).zfill(7)[:7]

    cep = "".join(c for c in (tomador.get("tomador_cep") or "") if c.isdigit())[:8]
    if cep:
        toma.cep = cep

    if tomador.get("tomador_logradouro"):
        toma.logradouro = str(tomador["tomador_logradouro"])[:255]
    if tomador.get("tomador_numero"):
        toma.numero = str(tomador["tomador_numero"])[:60]
    if tomador.get("tomador_complemento"):
        toma.complemento = str(tomador["tomador_complemento"])[:156]
    if tomador.get("tomador_bairro"):
        toma.bairro = str(tomador["tomador_bairro"])[:60]
    if tomador.get("tomador_telefone"):
        toma.telefone = "".join(c for c in str(tomador["tomador_telefone"]) if c.isdigit())[:15]
    if tomador.get("tomador_email"):
        toma.email = str(tomador["tomador_email"])[:80]

    return toma


def criar_prestador(config: Dict[str, Any]):
    """
    Constrói um PrestadorDPS a partir do dict de configuração.

    Suporta e-CNPJ (empresa) e e-CPF (autônomo/MEI) via config["tipo_certificado_nfse"].
    """
    from pynfe.entidades.dps import PrestadorDPS

    tipo = (config.get("tipo_certificado_nfse") or "e_cnpj").lower()
    im = (config.get("inscricao_municipal") or "").strip()
    prest = PrestadorDPS()
    prest.inscricao_municipal = im

    from pynfe.processamento.serializacao_nfse_nacional import resolve_cod_municipio_emissao

    homolog = bool(config.get("homologacao"))
    id_dps_modo = str(config.get("id_dps_modo") or "issnet_portal")
    portal = id_dps_modo == "issnet_portal"
    ibge_clinica = str(config.get("ibge") or "")[:7]
    cod_emissao = resolve_cod_municipio_emissao(
        ibge_clinica or str(config.get("cod_municipio_emissao") or "")[:7],
        homolog,
        portal=portal,
    )
    cross_municipio = bool(ibge_clinica and cod_emissao and ibge_clinica != cod_emissao)

    if tipo == "e_cpf":
        prest.cpf = (config.get("cpf") or "").strip()
        op_sn = int(config.get("opcao_simples_nacional") or 1)
        # E0176: cLocEmi≠incidência → regEspTrib 0 ou 5 (autônomo)
        if config.get("regime_especial") is not None:
            prest.regime_especial_tributacao = int(config.get("regime_especial"))
        elif cross_municipio:
            prest.regime_especial_tributacao = 5
        else:
            prest.regime_especial_tributacao = 0
        # E0162: regApTribSN só opSimpNac=3 (ME/EPP com CNPJ)
        prest.regime_apuracao_simples = None
        if op_sn == 3:
            try:
                prest.regime_apuracao_simples = int(config.get("regime_apuracao_simples") or 1)
            except (TypeError, ValueError):
                prest.regime_apuracao_simples = 1
    else:
        prest.cnpj = (config.get("cnpj") or "").strip()
        op_sn = int(config.get("opcao_simples_nacional") or 1)
        prest.regime_especial_tributacao = int(
            config.get("regime_especial") if config.get("regime_especial") is not None else 0
        )
        if op_sn == 3:
            try:
                prest.regime_apuracao_simples = int(config.get("regime_apuracao_simples") or 1)
            except (TypeError, ValueError):
                prest.regime_apuracao_simples = 1
        else:
            prest.regime_apuracao_simples = None

    prest.opcao_simples_nacional = op_sn
    prest.nome = (config.get("nome_prestador") or "").strip()

    return prest


def construir_dps(config: Dict[str, Any], tomador: Optional[Dict[str, Any]] = None):
    """
    Fábrica principal: constrói uma DPS completa a partir de dicts neutros.

    Parâmetros:
        config   – configuração técnica + dados da emissão (ver cabeçalho)
        tomador  – dados do tomador (dict neutro, ex: saída de load_tomador_from_paciente)

    Retorna:
        DPS (entidade pynfse, pronta para assinar e enviar)
    """
    from pynfe.entidades.dps import (
        DPS,
        LoteDPS,
        ServicoDPS,
        ServicoLocalPrestacao,
        ServicoCodigo,
        ValoresDPS,
        InfoTributacao,
        TribMunicipal,
    )

    dps = DPS()
    dps.ambiente = int(config.get("ambiente") or 2)

    # Data/hora com fuso de Brasília quando disponível
    try:
        from zoneinfo import ZoneInfo
        dps.data_hora_emissao = datetime.datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        dps.data_hora_emissao = datetime.datetime.utcnow()

    dps.versao_aplicativo = (config.get("versao_aplicativo") or "pynfse-1.0.0")[:20]
    dps.serie = (config.get("serie") or "1")
    dps.numero_dps = str(config.get("numero_dps") or "1")

    dc = config.get("data_competencia")
    dps.data_competencia = dc if isinstance(dc, datetime.date) else datetime.date.today()

    dps.tipo_emitente = 1  # Prestador
    id_dps_modo = str(config.get("id_dps_modo") or "issnet_portal")
    ibge_clinica = (config.get("ibge") or config.get("cod_municipio_emissao") or "")
    homolog = bool(config.get("homologacao"))
    portal = id_dps_modo == "issnet_portal"
    from pynfe.processamento.serializacao_nfse_nacional import resolve_cod_municipio_emissao

    dps.cod_municipio_emissao = resolve_cod_municipio_emissao(
        ibge_clinica, homolog, portal=portal
    )

    dps.id_dps_modo = id_dps_modo
    dps.prestador = criar_prestador(config)

    # Tomador
    if tomador:
        dps.tomador = criar_tomador(tomador)

    # Serviço
    ibge = (config.get("ibge") or config.get("cod_municipio_emissao") or "")
    serv = ServicoDPS()
    serv.local_prestacao = ServicoLocalPrestacao()
    # Local da prestação = município de incidência (clínica), não cLocEmi homologação
    serv.local_prestacao.cod_municipio = ibge

    cod_trib_nac = (config.get("cod_tributacao_nacional") or "").replace(".", "")
    cod_trib_nac = "".join(c for c in cod_trib_nac if c.isdigit()).zfill(6)[-6:]

    serv.codigo = ServicoCodigo()
    serv.codigo.cod_tributacao_nacional = cod_trib_nac
    cod_trib_mun = config.get("cod_tributacao_municipal")
    if cod_trib_mun:
        from pynfe.processamento.serializacao_nfse_nacional import (
            _normalizar_cod_trib_municipal,
        )

        serv.codigo.cod_tributacao_municipal = _normalizar_cod_trib_municipal(
            cod_trib_nac, cod_trib_mun
        )
    else:
        from pynfe.processamento.serializacao_nfse_nacional import (
            _c_trib_mun_from_nacional,
        )

        serv.codigo.cod_tributacao_municipal = _c_trib_mun_from_nacional(cod_trib_nac) or "401"
    cod_nbs = config.get("cod_nbs")
    if cod_nbs:
        serv.codigo.cod_nbs = "".join(c for c in str(cod_nbs) if c.isdigit())[:9]
    serv.codigo.descricao_servico = (config.get("descricao_servico") or "")[:2000]
    dps.servico = serv

    # Tributação
    trib_mun = TribMunicipal()
    trib_mun.tributacao_issqn = int(config.get("trib_issqn") or 1)
    homolog = bool(config.get("homologacao"))
    reg_esp = int(getattr(dps.prestador, "regime_especial_tributacao", 0) or 0)
    portal = (getattr(dps, "id_dps_modo", None) or "issnet_portal") == "issnet_portal"
    ibge_inc = str(ibge)[:7]
    c_loc_emi = str(dps.cod_municipio_emissao)[:7]
    if portal:
        cross_municipio = ibge_inc and c_loc_emi and ibge_inc != c_loc_emi
    else:
        cross_municipio = homolog or (c_loc_emi != ibge_inc)
    # E0588: regEspTrib≠0 → tpRetISSQN=1
    # L056/E241: tomador CPF → ISS não retido (tpRetISSQN=1)
    tomador_doc = ""
    if tomador:
        tomador_doc = "".join(
            c for c in str(tomador.get("tomador_doc") or "") if c.isdigit()
        )
    iss_retido = bool(config.get("iss_retido")) and not homolog
    if iss_retido and len(tomador_doc) == 11:
        iss_retido = False

    if reg_esp != 0:
        trib_mun.tipo_retencao_issqn = 1
    elif iss_retido:
        trib_mun.tipo_retencao_issqn = 2
    else:
        trib_mun.tipo_retencao_issqn = 1

    aliq = config.get("aliquota_iss_percentual")
    # E0604: regEspTrib≠0 → omitir pAliq
    # E341: ISS devido a outro município → informar alíquota (somente regEspTrib=0)
    if reg_esp == 0 and (aliq is not None or cross_municipio):
        try:
            trib_mun.aliquota = Decimal(str(aliq or "5.00"))
        except Exception:
            trib_mun.aliquota = Decimal("5.00")

    inf_trib = InfoTributacao()
    inf_trib.trib_municipal = trib_mun

    aliq_sn = config.get("p_tot_trib_sn")
    if aliq_sn is None:
        aliq_sn = config.get("aliquota_iss_percentual")
    op_sn = int(getattr(dps.prestador, "opcao_simples_nacional", 1) or 1)
    if aliq_sn is not None and op_sn in (2, 3):
        try:
            inf_trib.p_tot_trib_sn = Decimal(str(aliq_sn))
        except Exception:
            inf_trib.p_tot_trib_sn = Decimal("0")
    else:
        inf_trib.ind_tot_trib = 0

    # Valores
    vals = ValoresDPS()
    try:
        vals.valor_servico = Decimal(str(config.get("valor_servicos") or "0"))
    except Exception:
        vals.valor_servico = Decimal("0")
    vals.tributacao = inf_trib
    dps.valores = vals

    dps.incluir_ibscbs = bool(config.get("incluir_ibscbs", True))
    dps.ibscbs_modo = str(config.get("ibscbs_modo") or "minimo")
    dps.ibscbs_c_ind_op = str(config.get("c_ind_op") or "010101")

    return dps


def construir_lote(config: Dict[str, Any], dps_list) -> "LoteDPS":
    """Constrói um LoteDPS a partir do config e lista de DPS já criadas."""
    from pynfe.entidades.dps import LoteDPS

    lote = LoteDPS()
    lote.numero_lote = str(config.get("numero_lote") or "1")
    cnpj = (config.get("cnpj") or "").strip()
    cpf = (config.get("cpf") or "").strip()
    tipo = (config.get("tipo_certificado_nfse") or "e_cnpj").lower()
    if tipo == "e_cpf" and cpf:
        lote.prestador_cpf = cpf
    else:
        lote.prestador_cnpj = cnpj
    lote.prestador_inscricao_municipal = (config.get("inscricao_municipal") or "").strip()
    for dps in dps_list:
        lote.adicionar_dps(dps)
    return lote
