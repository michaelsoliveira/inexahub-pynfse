# NFS-e Padrão Nacional v1.01 - NotaControl / ISS.net
# Manual de Integração Webservice v1.01 (17/03/2026)
# Documento base: DPS (Declaração de Prestação de Serviços)

NAMESPACE_NFSE_NACIONAL = "http://www.sped.fazenda.gov.br/nfse"
VERSAO_NFSE_NACIONAL = "1.01"

# Ambiente: 1=Produção, 2=Homologação
AMBIENTE_PRODUCAO = 1
AMBIENTE_HOMOLOGACAO = 2

# ISS.net homologação: usar Campo Grande-MS em cLocEmi e no Id da DPS (ACBr/NotaControl).
ISSNET_HOMOLOGACAO_CLOC_EMI = "5002704"

# Emitente da DPS: 1=Prestador, 2=Tomador, 3=Intermediário
EMITENTE_PRESTADOR = 1
EMITENTE_TOMADOR = 2
EMITENTE_INTERMEDIARIO = 3

# Tributação ISSQN
TRIB_ISSQN_OPERACAO_TRIBUTAVEL = 1
TRIB_ISSQN_IMUNIDADE = 2
TRIB_ISSQN_EXPORTACAO = 3
TRIB_ISSQN_NAO_INCIDENCIA = 4

# Tipo de retenção ISSQN
RET_ISSQN_NAO_RETIDO = 1
RET_ISSQN_RETIDO_TOMADOR = 2
RET_ISSQN_RETIDO_INTERMEDIARIO = 3

# Simples Nacional
SN_NAO_OPTANTE = 1
SN_MEI = 2
SN_ME_EPP = 3

# Regime especial de tributação
REG_ESP_NENHUM = 0
REG_ESP_COOPERATIVA = 1
REG_ESP_ESTIMATIVA = 2
REG_ESP_MICROEMPRESA_MUNICIPAL = 3
REG_ESP_NOTARIO = 4
REG_ESP_PROFISSIONAL_AUTONOMO = 5
REG_ESP_SOCIEDADE_PROFISSIONAIS = 6

# Código de cancelamento
COD_CANC_ERRO_EMISSAO = 1
COD_CANC_SERVICO_NAO_PRESTADO = 2
COD_CANC_OUTROS = 9

# URLs ISS.net / NotaControl
NFSE_NACIONAL_URLS = {
    "ISSNET": {
        "PRODUCAO": "https://nfse.issnetonline.com.br/wsnfsenacional/nfse.asmx?WSDL",
        "HOMOLOGACAO": "https://nfse.issnetonline.com.br/wsnfsenacional/homologacao/nfse.asmx?WSDL",
    }
}

# Métodos SOAP disponíveis (conforme seção 9.2 do manual)
METODO_RECEPCIONAR_LOTE_DPS = "RecepcionarLoteDps"
METODO_ENVIAR_LOTE_DPS_SINCRONO = "RecepcionarLoteDpsSincrono"
METODO_GERAR_NFSE = "GerarNfse"
METODO_CANCELAR_NFSE = "CancelarNfse"
METODO_CONSULTAR_LOTE_DPS = "ConsultarLoteDps"
METODO_CONSULTAR_NFSE_DPS = "ConsultarNfsePorDps"
METODO_CONSULTAR_NFSE_PRESTADO = "ConsultarNfseServicoPrestado"
METODO_CONSULTAR_NFSE_TOMADO = "ConsultarNfseServicoTomado"
METODO_CONSULTAR_NFSE_FAIXA = "ConsultarNfseFaixa"
METODO_CONSULTAR_DADOS_CADASTRAIS = "ConsultarDadosCadastrais"
METODO_CONSULTAR_DPS_DISPONIVEL = "ConsultarDpsDisponivel"
METODO_CONSULTAR_URL_NFSE = "ConsultarUrlNfse"

# Construtores de entidades — importação conveniente para consumidores externos
from pynfe.utils.nfse.nacional.construtor import (  # noqa: E402
    criar_tomador,
    criar_prestador,
    construir_dps,
    construir_lote,
)
