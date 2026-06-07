# Entidades para NFS-e Padrão Nacional v1.01
# Baseado no Manual de Integração NotaControl/ISS.net (17/03/2026)
# DPS substitui o RPS como documento fiscal de origem da NFS-e

from decimal import Decimal
from .base import Entidade


class PrestadorDPS(Entidade):
    """Identificação do prestador de serviços (prest)."""
    cnpj = str()
    cpf = str()
    inscricao_municipal = str()           # IM - obrigatório
    # Regime de tributação (regTrib)
    opcao_simples_nacional = 1            # 1=Não optante, 2=MEI, 3=ME/EPP
    regime_apuracao_simples = None        # só para opSimpNac=3
    regime_especial_tributacao = 0        # 0=Nenhum ... 6=Sociedade de Prof.
    # Dados opcionais (novos na v1.01)
    nome = str()
    telefone = str()
    email = str()

    def __str__(self):
        return self.cnpj or self.cpf


class TomadorDPS(Entidade):
    """Identificação do tomador de serviços (toma) — opcional."""
    cnpj = str()
    cpf = str()
    nif = str()
    cod_nao_nif = None                    # 1=Dispensado, 2=Não exigência
    inscricao_municipal = str()
    razao_social = str()
    # Endereço (opcional)
    cod_municipio = str()                 # IBGE
    cep = str()
    logradouro = str()
    numero = str()
    complemento = str()
    bairro = str()
    telefone = str()
    email = str()

    def __str__(self):
        return self.razao_social or self.cnpj or self.cpf


class ServicoLocalPrestacao(Entidade):
    """Local da prestação do serviço (locPrest)."""
    cod_municipio = str()                 # cLocPrestacao (IBGE)
    cod_pais = str()                      # cPaisPrestacao (ISO) – exterior


class ServicoCodigo(Entidade):
    """Código do serviço prestado (cServ)."""
    cod_tributacao_nacional = str()       # cTribNac – 6 dígitos
    cod_tributacao_municipal = str()      # cTribMun – 3 dígitos (TCCodTribMun)
    descricao_servico = str()             # xDescServ – até 2000 chars
    cod_nbs = str()                       # cNBS – 9 dígitos (opcional)
    cod_interno_contribuinte = str()      # cIntContrib – opcional


class ServicoDPS(Entidade):
    """Informações do serviço prestado (serv)."""
    local_prestacao = None                # ServicoLocalPrestacao
    codigo = None                         # ServicoCodigo
    # Campos opcionais (comércio exterior, obra, evento, etc.)
    info_complementar = str()             # xInfComp
    documento_referenciado = str()        # docRef (obrigatório para tomador/intermediário)
    pedido = str()                        # xPed


class TribMunicipal(Entidade):
    """Tributos municipais – ISSQN (tribMun)."""
    tributacao_issqn = 1                  # 1=Trib., 2=Imunidade, 3=Export., 4=Não Incid.
    tipo_retencao_issqn = 1               # 1=Não Ret., 2=Ret. Tomador, 3=Ret. Interm.
    aliquota = None                       # pAliq – informar apenas nos casos do manual
    # Exigibilidade suspensa (opcional)
    tipo_suspensao = None                 # 1=Decisão Judicial, 2=Proc. Administrativo
    numero_processo = str()
    # Benefício municipal (opcional)
    numero_beneficio_municipal = str()    # nBM – 14 dígitos
    valor_reducao_bc_bm = None            # vRedBCBM
    percentual_reducao_bc_bm = None       # pRedBCBM


class TribFederal(Entidade):
    """Tributos federais – PIS/COFINS/IRRF/CP/CSLL (tribFed) — opcional."""
    valor_ret_cp = None                   # vRetCP
    valor_ret_irrf = None                 # vRetIRRF
    valor_ret_csll = None                 # vRetCSLL
    # PIS/COFINS
    cst_pis_cofins = "00"                 # 00=Nenhum
    valor_bc_pis_cofins = None
    aliquota_pis = None
    aliquota_cofins = None
    valor_pis = None
    valor_cofins = None
    tipo_retencao_pis_cofins = None


class InfoTributacao(Entidade):
    """Grupo de tributos (Trib)."""
    trib_municipal = None                 # TribMunicipal — obrigatório
    trib_federal = None                   # TribFederal — opcional
    # Total de tributos (totTrib) - obrigatório mas pode ser indicador
    ind_tot_trib = 0                      # 0=Não (não informar estimativa)
    p_tot_trib_fed = None                 # percentual fed. (opcional)
    p_tot_trib_est = None                 # percentual est. (opcional)
    p_tot_trib_mun = None                 # percentual mun. (opcional)
    p_tot_trib_sn = None                  # percentual SN (opcional)


class ValoresDPS(Entidade):
    """Informações de valores do serviço (valores)."""
    valor_servico = Decimal("0.00")       # vServ — obrigatório
    valor_recebido = None                 # vReceb — só para intermediário
    # Descontos (vDescCondIncond) — opcionais
    desconto_incondicionado = None        # vDescIncond
    desconto_condicionado = None          # vDescCond
    # Deduções/reduções (vDedRed) — opcionais
    percentual_deducao = None             # pDR
    valor_deducao = None                  # vDR
    # Tributação
    tributacao = None                     # InfoTributacao — obrigatório


class DPS(Entidade):
    """
    Declaração de Prestação de Serviços — documento fiscal de origem da NFS-e.
    Substitui o RPS no padrão NFS-e Nacional v1.01.

    O Id é formado por:
      "DPS" + cMun(7) + tpInscFed(1) + inscFed(14) + serie(5) + nDPS(15)
    """
    # Cabeçalho (infDPS)
    ambiente = 2                          # 1=Produção, 2=Homologação
    data_hora_emissao = None              # dhEmi – datetime UTC
    versao_aplicativo = str()             # verAplic – até 20 chars
    serie = str()                         # serie – até 5 dígitos
    numero_dps = str()                    # nDPS – até 15 dígitos
    data_competencia = None               # dCompet – date
    tipo_emitente = 1                     # 1=Prestador, 2=Tomador, 3=Intermediário
    motivo_emissao_ti = None              # cMotivoEmisTI – só para tomador/interm.
    cod_municipio_emissao = str()         # cLocEmi – código IBGE

    # Substituição (opcional)
    chave_nfse_substituida = str()        # chSubstda
    codigo_motivo_substituicao = None     # cMotivo
    motivo_substituicao = str()           # xMotivo

    # Participantes
    prestador = None                      # PrestadorDPS — obrigatório
    tomador = None                        # TomadorDPS — opcional
    intermediario = None                  # TomadorDPS (reutiliza) — opcional

    # Serviço
    servico = None                        # ServicoDPS — obrigatório

    # Valores
    valores = None                        # ValoresDPS — obrigatório

    # IBSCBS — obrigatório no schema ISS.net v1.01 (E160 se omitido)
    incluir_ibscbs = True

    # Id DPS: issnet_portal (Macapá/série municipal) ou nacional_padrao (homolog padded)
    id_dps_modo = "issnet_portal"
    ibscbs_c_ind_op = "010101"
    ibscbs_modo = "minimo"

    def __str__(self):
        return f"DPS/{self.serie}/{self.numero_dps}"


class LoteDPS(Entidade):
    """
    Lote de DPS para envio ao município.
    Suporta envio síncrono (EnviarLoteDpsSincrono) e assíncrono (RecepcionarLoteDps).
    """
    numero_lote = str()                   # NumeroLote – até 15 dígitos
    # Prestador do lote (Prestador - tcIdentificacaoPessoaEmpresaComIM)
    prestador_cnpj = str()
    prestador_cpf = str()
    prestador_inscricao_municipal = str()

    lista_dps = None                      # lista de DPS assinadas

    def __init__(self, *args, **kwargs):
        self.lista_dps = []
        super().__init__(*args, **kwargs)

    def adicionar_dps(self, dps: DPS):
        self.lista_dps.append(dps)

    @property
    def quantidade_dps(self):
        return len(self.lista_dps)

    def __str__(self):
        return f"Lote/{self.numero_lote} ({self.quantidade_dps} DPS)"
