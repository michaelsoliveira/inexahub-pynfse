def get_version():
    return "0.6.0"


__version__ = get_version()
__author__ = "Marinho Brandao, Junior Tada, Leonardo Tada"
__license__ = "GNU Lesser General Public License (LGPL)"
__url__ = "https://github.com/TadaSoftware/PyNFe"

# NFS-e Padrão Nacional v1.01 — exports de conveniência
from pynfe.entidades.dps import (  # noqa: E402
    DPS,
    LoteDPS,
    PrestadorDPS,
    TomadorDPS,
    ServicoDPS,
    ServicoLocalPrestacao,
    ServicoCodigo,
    ValoresDPS,
    InfoTributacao,
    TribMunicipal,
    TribFederal,
)
from pynfe.processamento.comunicacao_nfse_nacional import ComunicacaoNFSeNacional  # noqa: E402
from pynfe.processamento.assinatura_nfse_nacional import AssinaturaNFSeNacional  # noqa: E402
from pynfe.processamento.serializacao_nfse_nacional import serializar_dps  # noqa: E402
