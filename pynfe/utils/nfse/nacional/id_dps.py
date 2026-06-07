"""
Geração do Id da DPS — NFS-e Nacional v1.01 (TSIdDPS).

Schema (tiposSimples_v1.01.xsd):
  Id = DPS + cMunEmi(7) + tpInscr(1) + inscrFederal(14) + serie(5) + nDPS(15)
  Pattern: DPS[0-9]{42} — exatamente 45 caracteres.

Elementos XML (<serie>, <nDPS>) podem ser menores (ex.: serie=70002, nDPS=2).
O portal ISSNet Macapá exibe Id encurtado na UI; o webservice exige o Id padded.
"""
from __future__ import annotations

from typing import Literal

IdDpsModo = Literal["issnet_portal", "nacional_padrao"]


def format_inscricao_federal_id(tp_inscr: str, doc: str) -> str:
    """CPF/CNPJ com 14 dígitos para composição do Id."""
    digits = "".join(c for c in str(doc or "") if c.isdigit())
    if tp_inscr == "1":
        return digits.zfill(11).zfill(14)[-14:]
    return digits.zfill(14)[-14:]


def format_serie_portal(serie) -> str:
    """Série municipal — 5 dígitos no Id (ex.: 70002)."""
    digits = "".join(c for c in str(serie) if c.isdigit())
    if not digits:
        return "00001"
    n = int(digits)
    if n > 99999:
        n = int(str(n)[-5:])
    return str(n).zfill(5)


def format_serie_elemento_portal(serie) -> str:
    """Valor do elemento <serie> — como retornado pelo portal (ex.: 70002)."""
    digits = "".join(c for c in str(serie) if c.isdigit())
    return digits if digits else "1"


def format_n_dps_portal(numero) -> str:
    """Valor do elemento <nDPS> e sufixo do Id — sequência municipal sem padding."""
    digits = "".join(c for c in str(numero) if c.isdigit())
    if not digits:
        return "1"
    if len(digits) == 15 and digits[0] == "1":
        resto = digits[1:].lstrip("0")
        return resto if resto else "1"
    return str(int(digits))


def format_n_dps_id_nacional(numero) -> str:
    """Sufixo 15 dígitos — layout nacional genérico (homologação NotaControl)."""
    digits = "".join(c for c in str(numero) if c.isdigit())
    n = int(digits) if digits else 1
    s = str(n)
    if len(s) > 15:
        s = s[-15:]
    if s[0] == "0" or len(s) < 15:
        s = ("1" + s.zfill(14))[-15:]
    return s


def gerar_id_dps(
    c_mun: str,
    tp_inscr: str,
    inscricao: str,
    serie,
    numero_dps,
    modo: IdDpsModo = "issnet_portal",
) -> str:
    """
    Gera o atributo Id da infDPS (TSIdDPS — sempre 45 caracteres).

    O parâmetro ``modo`` não altera o Id; só documenta a origem da série/nDPS.
    Elementos <serie>/<nDPS> usam formatação portal em serializacao_nfse_nacional.
    """
    del modo  # Id segue sempre o XSD nacional
    c_mun7 = "".join(c for c in str(c_mun or "") if c.isdigit()).zfill(7)[:7]
    inscr = format_inscricao_federal_id(tp_inscr, inscricao)
    serie5 = format_serie_portal(serie)
    n_dps15 = format_n_dps_id_nacional(numero_dps)
    return f"DPS{c_mun7}{tp_inscr}{inscr}{serie5}{n_dps15}"


def tp_inscr_from_prestador(cnpj: str = "", cpf: str = "") -> str:
    if cnpj:
        return "2"
    return "1"
