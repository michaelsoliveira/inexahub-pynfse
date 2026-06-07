# Geração do DANFSE (Documento Auxiliar da NFS-e Nacional)
# via BrazilFiscalReport — padrão nacional v1.01
#
# Instale o extra:
#   pip install "inexahub-pynfse[nfse_nacional]"
# Ou manualmente:
#   pip install brazilfiscalreport qrcode[pil]
#
# Uso:
#   from pynfe.processamento.danfse_nfse_nacional import gerar_danfse_pdf
#   pdf_bytes = gerar_danfse_pdf(nfse_xml_str)


def gerar_danfse_pdf(nfse_xml: str | bytes) -> bytes:
    """
    Gera o PDF do DANFSE a partir do XML completo da NFS-e autorizada.

    Parâmetro:
        nfse_xml — string ou bytes do XML da NFS-e retornado pelo município
                   (elemento CompNfse ou NFSe com namespace sped.fazenda.gov.br/nfse).

    Retorna bytes do PDF pronto para download ou armazenamento.

    Requer: brazilfiscalreport + qrcode[pil]
      pip install "inexahub-pynfse[nfse_nacional]"
    """
    _validar_dependencias()

    from brazilfiscalreport.danfse import Danfse
    from brazilfiscalreport.danfse.config import DanfseConfig

    if isinstance(nfse_xml, bytes):
        nfse_xml = nfse_xml.decode("utf-8")

    if not nfse_xml or not nfse_xml.strip():
        raise ValueError("XML da NFS-e está vazio — impossível gerar o DANFSE.")

    try:
        danfse = Danfse(xml=nfse_xml, config=DanfseConfig())
    except Exception as e:
        raise RuntimeError(
            f"Erro ao montar DANFSE: {e}. "
            "Verifique se o XML retornado pelo município é um NFSe válido."
        ) from e

    pdf = danfse.output()
    if isinstance(pdf, str):
        pdf = pdf.encode("latin-1")
    return pdf


def _validar_dependencias() -> None:
    missing = []
    try:
        import brazilfiscalreport  # noqa: F401
    except ImportError:
        missing.append("brazilfiscalreport")
    try:
        import qrcode  # noqa: F401
    except ImportError:
        missing.append("qrcode[pil]")

    if missing:
        pacotes = " ".join(missing)
        raise ImportError(
            f"Dependências ausentes para gerar DANFSE: {pacotes}. "
            'Instale com: pip install "inexahub-pynfse[nfse_nacional]"'
        )
