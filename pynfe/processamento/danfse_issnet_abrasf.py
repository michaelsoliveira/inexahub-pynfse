# Geração do DANFSE para NFS-e ISSNet ABRASF v2.01
#
# Extrai os dados do XML CompNfse (namespace http://www.abrasf.org.br/nfse.xsd)
# e gera um PDF funcional usando fpdf2.
#
# Estratégia:
#   1. Se o XML contém <LinkNfse>, redireciona para a URL oficial do município.
#   2. Caso contrário, gera DANFSE básico localmente com fpdf2.
#
# Uso:
#   from pynfe.processamento.danfse_issnet_abrasf import gerar_danfse_pdf_abrasf, extrair_link_nfse

from __future__ import annotations

from lxml import etree

NS = "http://www.abrasf.org.br/nfse.xsd"
_NS = "{%s}" % NS


def extrair_link_nfse(xml_str: str | bytes) -> str | None:
    """Retorna o LinkNfse da CompNfse se presente, senão None."""
    try:
        root = etree.fromstring(
            xml_str.encode() if isinstance(xml_str, str) else xml_str
        )
        el = root.find(f".//{_NS}LinkNfse")
        if el is not None and (el.text or "").strip():
            return el.text.strip()
    except Exception:
        pass
    return None


def gerar_danfse_pdf_abrasf(xml_str: str | bytes) -> bytes:
    """
    Gera PDF do DANFSE a partir do XML CompNfse ABRASF v2.01 (ISSNet).

    Parâmetro:
        xml_str - XML da NFS-e retornado pelo webservice ISSNet

    Retorna bytes do PDF.
    """
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise ImportError("fpdf2 é necessário: pip install fpdf2") from exc

    if isinstance(xml_str, bytes):
        xml_str = xml_str.decode("utf-8")

    data = _extrair_dados(xml_str)
    return _gerar_pdf(data)


# ─── Extração de dados do XML ABRASF ─────────────────────────────────────────

def _txt(el, path: str, default: str = "") -> str:
    if el is None:
        return default
    found = el.find(path)
    return (found.text or "").strip() if found is not None and found.text else default


def _extrair_dados(xml_str: str) -> dict:
    try:
        root = etree.fromstring(xml_str.encode("utf-8"))
    except Exception as exc:
        raise ValueError(f"XML ABRASF inválido: {exc}") from exc

    n = _NS  # prefixo de namespace

    # Nfse/InfNfse
    inf = root.find(f".//{n}InfNfse")
    numero = _txt(inf, f"{n}Numero")
    data_emissao = _txt(inf, f"{n}DataEmissao")[:10] if inf is not None else ""
    cod_verificacao = _txt(inf, f"{n}CodigoVerificacao")
    link_nfse = _txt(inf, f"{n}LinkNfse")
    competencia = ""

    # DPS dentro do InfNfse (ABRASF v2.01 estrutura interna)
    dps = root.find(f".//{n}InfDeclaracaoPrestacaoServico")
    if dps is None:
        dps = root.find(f".//{n}Rps")

    competencia = _txt(dps, f"{n}Competencia") if dps is not None else ""

    # Servico
    serv = root.find(f".//{n}Servico")
    discriminacao = _txt(serv, f"{n}Discriminacao")
    item_lista = _txt(serv, f"{n}ItemListaServico")
    valor_servicos = _txt(serv, f".//{n}ValorServicos")
    aliquota = _txt(serv, f".//{n}Aliquota")
    valor_iss = _txt(serv, f".//{n}ValorIss")
    iss_retido_val = _txt(serv, f"{n}IssRetido")
    iss_retido = "Sim" if iss_retido_val == "1" else "Não"

    # Prestador
    prest = root.find(f".//{n}Prestador")
    prest_cnpj = (_cpf_cnpj(prest) if prest is not None else "")
    prest_im = _txt(prest, f".//{n}InscricaoMunicipal") if prest is not None else ""
    prest_nome = _txt(prest, f"{n}RazaoSocial") if prest is not None else ""

    # Tomador
    toma = root.find(f".//{n}Tomador")
    toma_cnpj = (_cpf_cnpj(toma) if toma is not None else "")
    toma_nome = _txt(toma, f"{n}RazaoSocial") if toma is not None else ""
    toma_end = _endereco(toma) if toma is not None else ""

    # Emitente (InfNfse pode ter Prestador com nome)
    if not prest_nome and inf is not None:
        p2 = inf.find(f"{n}PrestadorServico")
        if p2 is not None:
            prest_nome = _txt(p2, f"{n}RazaoSocial")
            prest_im = prest_im or _txt(p2, f".//{n}InscricaoMunicipal")

    return {
        "numero": numero,
        "data_emissao": data_emissao,
        "competencia": competencia or data_emissao[:7],
        "cod_verificacao": cod_verificacao,
        "link_nfse": link_nfse,
        "discriminacao": discriminacao,
        "item_lista": item_lista,
        "valor_servicos": valor_servicos,
        "aliquota": aliquota,
        "valor_iss": valor_iss,
        "iss_retido": iss_retido,
        "prest_cnpj": prest_cnpj,
        "prest_im": prest_im,
        "prest_nome": prest_nome,
        "toma_cnpj": toma_cnpj,
        "toma_nome": toma_nome,
        "toma_end": toma_end,
    }


def _cpf_cnpj(el) -> str:
    if el is None:
        return ""
    n = _NS
    cnpj = el.find(f".//{n}Cnpj")
    if cnpj is not None and cnpj.text:
        v = cnpj.text.strip()
        return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}" if len(v) == 14 else v
    cpf = el.find(f".//{n}Cpf")
    if cpf is not None and cpf.text:
        v = cpf.text.strip()
        return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}" if len(v) == 11 else v
    return ""


def _endereco(el) -> str:
    if el is None:
        return ""
    n = _NS
    end = el.find(f"{n}Endereco")
    if end is None:
        return ""
    partes = []
    for tag in (f"{n}Endereco", f"{n}Numero", f"{n}Bairro", f"{n}Uf"):
        v = end.find(tag)
        if v is not None and v.text:
            partes.append(v.text.strip())
    cep = end.find(f"{n}Cep")
    if cep is not None and cep.text:
        v = cep.text.strip()
        partes.append(f"CEP {v[:5]}-{v[5:]}" if len(v) == 8 else v)
    return ", ".join(partes)


# ─── Geração do PDF ──────────────────────────────────────────────────────────

def _gerar_pdf(d: dict) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_doc_option("core_fonts_encoding", "windows-1252")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    # Cabeçalho
    pdf.set_fill_color(30, 90, 150)
    pdf.rect(15, 15, 180, 10, "F")
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(15, 16)
    pdf.cell(180, 8, "NOTA FISCAL DE SERVICOS ELETRONICOS - NFS-e", align="C")

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(15, 26)
    pdf.cell(180, 5, "Documento Auxiliar da NFS-e (DANFSE) - ISSNet Online", align="C")
    pdf.ln(3)

    # Número e data
    y = pdf.get_y()
    pdf.set_fill_color(240, 240, 240)
    pdf.rect(15, y, 180, 14, "F")
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(15, y + 1)
    pdf.cell(90, 6, f"NFS-e N.° {d['numero']}", align="C")
    pdf.set_xy(105, y + 1)
    pdf.cell(90, 6, f"Data de Emissão: {_fmt_data(d['data_emissao'])}", align="C")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(15, y + 8)
    pdf.cell(90, 5, f"Competência: {d['competencia']}", align="C")
    if d["cod_verificacao"]:
        pdf.set_xy(105, y + 8)
        pdf.cell(90, 5, f"Cód. Verificação: {d['cod_verificacao']}", align="C")
    pdf.ln(16)

    # Prestador
    _secao(pdf, "PRESTADOR DE SERVIÇOS")
    _linha(pdf, "Nome/Razão Social:", d["prest_nome"])
    _linha_dupla(pdf, "CPF/CNPJ:", d["prest_cnpj"], "Insc. Municipal:", d["prest_im"])

    # Tomador
    pdf.ln(2)
    _secao(pdf, "TOMADOR DE SERVIÇOS")
    _linha(pdf, "Nome/Razão Social:", d["toma_nome"])
    _linha(pdf, "CPF/CNPJ:", d["toma_cnpj"])
    if d["toma_end"]:
        _linha(pdf, "Endereço:", d["toma_end"])

    # Serviço
    pdf.ln(2)
    _secao(pdf, "DISCRIMINAÇÃO DO SERVIÇO")
    _linha(pdf, "Item Lista Serviço:", d["item_lista"])
    _bloco_texto(pdf, d["discriminacao"])

    # Valores
    pdf.ln(2)
    _secao(pdf, "VALORES")
    _linha_dupla(pdf, "Valor dos Serviços:", _fmt_valor(d["valor_servicos"]),
                 "ISS Retido:", d["iss_retido"])
    _linha_dupla(pdf, "Alíquota ISS:", f"{d['aliquota']}%" if d["aliquota"] else "-",
                 "Valor ISS:", _fmt_valor(d["valor_iss"]))

    # Link para verificação
    if d["link_nfse"]:
        pdf.ln(3)
        _secao(pdf, "VERIFICAÇÃO DE AUTENTICIDADE")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_x(15)
        pdf.multi_cell(180, 4, f"Acesse: {d['link_nfse']}", align="L")

    # Rodapé
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(180, 5, "Este documento é auxiliar à NFS-e. A nota fiscal eletrônica é o documento oficial.", align="C")

    return bytes(pdf.output())


def _secao(pdf, titulo: str) -> None:
    from fpdf import FPDF
    pdf.set_fill_color(220, 230, 245)
    y = pdf.get_y()
    pdf.rect(15, y, 180, 6, "F")
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(30, 60, 120)
    pdf.set_xy(15, y + 0.5)
    pdf.cell(180, 5, titulo)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(7)


def _linha(pdf, label: str, value: str) -> None:
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_x(15)
    pdf.cell(40, 5, label)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(140, 5, value or "-", new_x="LMARGIN")


def _linha_dupla(pdf, l1: str, v1: str, l2: str, v2: str) -> None:
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_x(15)
    pdf.cell(35, 5, l1)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(55, 5, v1 or "-")
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(35, 5, l2)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(55, 5, v2 or "-")
    pdf.ln(6)


def _bloco_texto(pdf, texto: str) -> None:
    pdf.set_font("Helvetica", "", 8)
    pdf.set_x(15)
    pdf.multi_cell(180, 4, texto or "-", align="L", new_x="LMARGIN")
    pdf.ln(1)


def _fmt_data(d: str) -> str:
    if len(d) >= 10:
        return f"{d[8:10]}/{d[5:7]}/{d[:4]}"
    return d


def _fmt_valor(v: str) -> str:
    if not v:
        return "R$ 0,00"
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        return v
