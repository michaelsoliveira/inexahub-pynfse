# Comunicação SOAP para NFS-e Padrão Nacional v1.01
# Manual NotaControl/ISS.net – seção 7.2 e 9.2
#
# Protocolo: HTTPS + mTLS (certificado A1)
# Padrão SOAP: Document/Literal Wrapped (WS-I Basic Profile)
# Namespace: http://www.sped.fazenda.gov.br/nfse
#
# Todos os serviços usam o mesmo endpoint WSDL.
# O método SOAP é determinado pela tag raiz do XML enviado.

from __future__ import annotations

import datetime
import logging
import re
import requests
import lxml.etree as etree

from pynfe.entidades.certificado import CertificadoA1
from pynfe.utils.nfse.nacional import (
    NAMESPACE_NFSE_NACIONAL,
    NFSE_NACIONAL_URLS,
    VERSAO_NFSE_NACIONAL,
    AMBIENTE_HOMOLOGACAO,
    METODO_RECEPCIONAR_LOTE_DPS,
    METODO_ENVIAR_LOTE_DPS_SINCRONO,
    METODO_GERAR_NFSE,
    METODO_CANCELAR_NFSE,
    METODO_CONSULTAR_LOTE_DPS,
    METODO_CONSULTAR_NFSE_DPS,
    METODO_CONSULTAR_NFSE_PRESTADO,
    METODO_CONSULTAR_NFSE_TOMADO,
    METODO_CONSULTAR_NFSE_FAIXA,
    METODO_CONSULTAR_DADOS_CADASTRAIS,
    METODO_CONSULTAR_DPS_DISPONIVEL,
    METODO_CONSULTAR_URL_NFSE,
)
from pynfe.processamento.assinatura_nfse_nacional import AssinaturaNFSeNacional
from pynfe.processamento.serializacao_nfse_nacional import (
    serializar_dps,
    serializar_lote_sincrono,
    serializar_lote_assincrono,
    serializar_cancelar_nfse,
    serializar_consultar_lote,
    serializar_consultar_nfse_por_dps,
    serializar_consultar_nfse_servico_prestado,
    serializar_consultar_dados_cadastrais,
    serializar_consultar_dps_disponivel,
    serializar_consultar_url_nfse,
)
from pynfe.entidades.dps import DPS, LoteDPS

NS = NAMESPACE_NFSE_NACIONAL
NAMESPACE_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"
logger = logging.getLogger(__name__)


def _xml_nfse_sem_prefixo(elemento: etree._Element) -> etree._Element:
    """
    Reescreve o XML NFSe sem prefixos de namespace (ex.: ns0:).

    O layout nacional veda prefixos; o validador ISS.net rejeita com E160 quando
    o lote é enviado com ns0: em todos os elementos.
    """
    xml_str = etree.tostring(elemento, encoding="unicode", pretty_print=False)
    xml_str = re.sub(r'\s*xmlns:ns\d+="' + re.escape(NS) + r'"', "", xml_str)
    xml_str = re.sub(r"ns\d+:", "", xml_str)
    # nsmap + set("xmlns") ou injeção dupla geram xmlns repetido e quebram o parser
    xml_str = re.sub(
        r'(\s+xmlns="' + re.escape(NS) + r'")(\s+xmlns="' + re.escape(NS) + r'")',
        r"\1",
        xml_str,
        count=1,
    )
    if f'xmlns="{NS}"' not in xml_str.split(">", 1)[0]:
        xml_str = xml_str.replace(
            "<" + etree.QName(elemento).localname,
            '<' + etree.QName(elemento).localname + ' xmlns="' + NS + '"',
            1,
        )
    # X509Certificate: base64 contínuo (sem quebras) — exigência comum do XSD xmldsig
    xml_str = re.sub(
        r"(<X509Certificate>)([\s\S]*?)(</X509Certificate>)",
        lambda m: m.group(1) + re.sub(r"\s+", "", m.group(2)) + m.group(3),
        xml_str,
    )
    return etree.fromstring(xml_str.encode("utf-8"))


def _garantir_xmlns_dps_no_lote(xml_str: str) -> str:
    """
    Declara xmlns em cada <DPS> dentro de ListaDps.

    O ISS.net valida cada DPS do lote como fragmento; sem xmlns explícito na tag
    raiz o conteúdo fica fora do namespace e retorna E160.
    """

    def _repl(match: re.Match) -> str:
        tag = match.group(0)
        if f'xmlns="{NS}"' in tag:
            return tag
        local = "DPS" if tag.startswith("<DPS") else "Dps"
        return tag.replace(f"<{local}", f'<{local} xmlns="{NS}"', 1)

    xml_str = re.sub(r"<DPS\s+versao=\"[^\"]+\"", _repl, xml_str)
    return re.sub(r"<Dps\s+versao=\"[^\"]+\"", _repl, xml_str)


def _garantir_xmlns_raiz_fragmento(xml_str: str, localname: str) -> str:
    """
    Declara xmlns no elemento raiz de um fragmento (nfseDadosMsg / nfseCabecMsg).

    O ISS.net valida EnviarLoteDpsSincronoEnvio isolado; sem xmlns explícito no
    fragmento, os elementos ficam sem namespace e retornam E160 no webservice.
    """
    if f'xmlns="{NS}"' in xml_str.split(">", 1)[0]:
        return xml_str
    pattern = rf"<{re.escape(localname)}((?:\s[^>]*)?)>"

    def _repl(match):
        attrs = match.group(1) or ""
        return f"<{localname}{attrs} xmlns=\"{NS}\">"

    return re.sub(pattern, _repl, xml_str, count=1)


class ComunicacaoNFSeNacional:
    """
    Comunicação com o webservice NFS-e Padrão Nacional (ISS.net / NotaControl).

    Parâmetros:
        certificado   – caminho para o arquivo .pfx ou .p12 (A1)
        senha         – senha do certificado
        homologacao   – True para ambiente de homologação (default: True)
        provider      – chave do provedor em NFSE_NACIONAL_URLS (default: "ISSNET")

    Exemplo de uso:
        from pynfe.processamento.comunicacao_nfse_nacional import ComunicacaoNFSeNacional
        from pynfe.entidades.dps import DPS, LoteDPS, PrestadorDPS, ...

        dps = DPS()
        dps.prestador = PrestadorDPS(cnpj="12345678000195", inscricao_municipal="123456")
        ...

        lote = LoteDPS()
        lote.numero_lote = "1"
        lote.prestador_cnpj = "12345678000195"
        lote.prestador_inscricao_municipal = "123456"
        lote.adicionar_dps(dps)

        comm = ComunicacaoNFSeNacional("cert.pfx", "senha")
        resultado = comm.enviar_lote_sincrono(lote)
    """

    def __init__(
        self,
        certificado: str,
        senha: str,
        homologacao: bool = True,
        provider: str = "ISSNET",
        url: str | None = None,
    ):
        self.certificado = certificado
        self.senha = senha
        self.ambiente = AMBIENTE_HOMOLOGACAO if homologacao else 1
        self.provider = provider.upper()
        self._assinador = AssinaturaNFSeNacional(certificado, senha)

        env_key = "HOMOLOGACAO" if homologacao else "PRODUCAO"
        default_url = NFSE_NACIONAL_URLS[self.provider][env_key]
        self._url = (url or default_url).replace("?WSDL", "")

    # ------------------------------------------------------------------ #
    # Métodos públicos – fluxos principais                                 #
    # ------------------------------------------------------------------ #

    def enviar_lote_sincrono(self, lote: LoteDPS) -> requests.Response:
        """
        Envia lote de DPS de forma síncrona (EnviarLoteDpsSincrono).
        Retorna imediatamente a NFS-e gerada ou a lista de erros.
        """
        lote_assinado = self._preparar_lote(lote, sincrono=True)
        return self._post_soap(
            METODO_ENVIAR_LOTE_DPS_SINCRONO,
            lote_assinado,
        )

    def recepcionar_lote(self, lote: LoteDPS) -> requests.Response:
        """
        Envia lote de DPS de forma assíncrona (RecepcionarLoteDps).
        Retorna protocolo; consultar resultado com consultar_lote().
        """
        lote_assinado = self._preparar_lote(lote, sincrono=False)
        return self._post_soap(
            METODO_RECEPCIONAR_LOTE_DPS,
            lote_assinado,
        )

    def gerar_nfse(self, dps: DPS) -> requests.Response:
        """
        Gera NFS-e a partir de uma única DPS (GerarNfse) — síncrono.
        """
        dps_xml = serializar_dps(dps)
        dps_assinada = self._assinador.assinar_dps(dps_xml)

        raiz = etree.Element(
            "{%s}GerarNfseEnvio" % NS,
            nsmap={None: NS},
        )
        raiz.append(dps_assinada)

        return self._post_soap(METODO_GERAR_NFSE, raiz)

    def cancelar_nfse(
        self,
        chave_nfse: str,
        codigo_motivo: int,
        motivo: str,
    ) -> requests.Response:
        """
        Cancela NFS-e pelo evento de cancelamento (CancelarNfse).
        Codes: 1=Erro na Emissão, 2=Serviço não Prestado, 9=Outros.
        """
        canc_xml = serializar_cancelar_nfse(chave_nfse, codigo_motivo, motivo)
        # Preenche dhEvento e tpAmb dinâmicamente
        self._preencher_cancelamento(canc_xml)
        canc_assinado = self._assinador.assinar_cancelamento(canc_xml)

        raiz = etree.Element(
            "{%s}CancelarNfseEnvio" % NS,
            nsmap={None: NS},
        )
        raiz.append(canc_assinado)

        return self._post_soap(METODO_CANCELAR_NFSE, raiz)

    def consultar_lote(
        self,
        prestador_doc: str,
        prestador_im: str,
        protocolo: str,
        usar_cpf: bool = False,
    ) -> requests.Response:
        xml = serializar_consultar_lote(
            prestador_doc, prestador_im, protocolo, usar_cpf=usar_cpf
        )
        return self._post_soap(METODO_CONSULTAR_LOTE_DPS, xml)

    def consultar_nfse_servico_prestado(
        self,
        prestador_doc: str,
        prestador_im: str,
        numero_nfse: str | None = None,
        data_inicial: str | None = None,
        data_final: str | None = None,
        pagina: int = 1,
        usar_cpf: bool = False,
    ) -> requests.Response:
        xml = serializar_consultar_nfse_servico_prestado(
            prestador_doc,
            prestador_im,
            numero_nfse=numero_nfse,
            data_inicial=data_inicial,
            data_final=data_final,
            pagina=pagina,
            usar_cpf=usar_cpf,
        )
        return self._post_soap(METODO_CONSULTAR_NFSE_PRESTADO, xml)

    def consultar_nfse_por_dps(
        self,
        prestador_doc: str,
        prestador_im: str,
        serie: str,
        numero_dps: str,
        usar_cpf: bool = False,
    ) -> requests.Response:
        xml = serializar_consultar_nfse_por_dps(
            prestador_doc, prestador_im, serie, numero_dps, usar_cpf=usar_cpf
        )
        return self._post_soap(METODO_CONSULTAR_NFSE_DPS, xml)

    def consultar_dados_cadastrais(
        self,
        prestador_cnpj: str,
        prestador_im: str,
    ) -> requests.Response:
        xml = serializar_consultar_dados_cadastrais(prestador_cnpj, prestador_im)
        return self._post_soap(METODO_CONSULTAR_DADOS_CADASTRAIS, xml)

    def consultar_dps_disponivel(
        self,
        prestador_doc: str,
        prestador_im: str,
        pagina: int = 1,
        usar_cpf: bool = False,
    ) -> requests.Response:
        xml = serializar_consultar_dps_disponivel(
            prestador_doc, prestador_im, pagina, usar_cpf=usar_cpf
        )
        return self._post_soap(METODO_CONSULTAR_DPS_DISPONIVEL, xml)

    def sincronizar_sequencia_dps(
        self,
        prestador_doc: str,
        prestador_im: str,
        usar_cpf: bool = False,
    ) -> dict:
        """
        Consulta série/nDPS disponíveis no cadastro ISS.net municipal.
        """
        from pynfe.utils.nfse.nacional.sequencia_dps import extrair_sequencia_dps_resposta

        resp = self.consultar_dps_disponivel(
            prestador_doc, prestador_im, pagina=1, usar_cpf=usar_cpf
        )
        if resp.status_code != 200:
            logger.warning(
                "ConsultarDpsDisponivel HTTP %s: %s",
                resp.status_code,
                (resp.text or "")[:500],
            )
            return {}
        return extrair_sequencia_dps_resposta(resp.text or "")

    def consultar_url_nfse(
        self,
        prestador_doc: str,
        prestador_im: str,
        numero_nfse: str | None = None,
        data_inicial: str | None = None,
        data_final: str | None = None,
        pagina: int = 1,
        usar_cpf: bool = False,
    ) -> requests.Response:
        xml = serializar_consultar_url_nfse(
            prestador_doc,
            prestador_im,
            numero_nfse=numero_nfse,
            data_inicial=data_inicial,
            data_final=data_final,
            pagina=pagina,
            usar_cpf=usar_cpf,
        )
        return self._post_soap(METODO_CONSULTAR_URL_NFSE, xml)

    # ------------------------------------------------------------------ #
    # Métodos internos                                                     #
    # ------------------------------------------------------------------ #

    def _preparar_lote(self, lote: LoteDPS, sincrono: bool) -> etree._Element:
        """Serializa, assina DPS individuais e assina o lote."""
        dps_xmls = [serializar_dps(dps) for dps in (lote.lista_dps or [])]
        fn_lote = serializar_lote_sincrono if sincrono else serializar_lote_assincrono
        return self._assinador.preparar_lote_assinado(lote, dps_xmls, fn_lote)

    def _preencher_cancelamento(self, xml: etree._Element) -> None:
        """Preenche dhEvento e tpAmb no cancelamento em tempo de execução."""
        ns = {"n": NS}
        dh_el = xml.find(".//n:dhEvento", ns)
        if dh_el is not None:
            dh_el.text = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"
        tp_el = xml.find(".//n:tpAmb", ns)
        if tp_el is not None:
            tp_el.text = str(self.ambiente)

    @staticmethod
    def _criar_cabecalho() -> etree._Element:
        """Cabeçalho nfseCabecMsg no namespace nacional, sem prefixos."""
        cabecalho = etree.Element(
            "{%s}cabecalho" % NS,
            nsmap={None: NS},
            versao=VERSAO_NFSE_NACIONAL,
        )
        vd = etree.SubElement(cabecalho, "{%s}versaoDados" % NS)
        vd.text = VERSAO_NFSE_NACIONAL
        return cabecalho

    def _construir_envelope_soap(
        self,
        metodo: str,
        dados_xml: etree._Element,
    ) -> str:
        """
        Monta o envelope SOAP 1.1 para o ISS.net Nacional.

        O ISS.net declara nfseCabecMsg/nfseDadosMsg como xs:any no WSDL,
        portanto espera XML EMBUTIDO DIRETAMENTE — não entity-encoded strings.

        Formato correto:
          <nfseCabecMsg><cabecalho ...>...</cabecalho></nfseCabecMsg>
          <nfseDadosMsg><EnviarLoteDpsSincronoEnvio ...>...</nfseDadosMsg>
        """
        dados_xml = _xml_nfse_sem_prefixo(dados_xml)
        dados_local = etree.QName(dados_xml).localname

        envelope = etree.Element(
            "{%s}Envelope" % NAMESPACE_SOAP,
            nsmap={
                "soap": NAMESPACE_SOAP,
                "xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "xsd": "http://www.w3.org/2001/XMLSchema",
            },
        )
        body = etree.SubElement(envelope, "{%s}Body" % NAMESPACE_SOAP)

        wrapper = etree.SubElement(
            body,
            "{%s}%s" % (NS, metodo),
            nsmap={None: NS},
        )

        cab_el = etree.SubElement(wrapper, "{%s}nfseCabecMsg" % NS)
        cab_el.append(self._criar_cabecalho())

        dados_el = etree.SubElement(wrapper, "{%s}nfseDadosMsg" % NS)
        dados_el.append(dados_xml)

        xml_str = etree.tostring(envelope, encoding="unicode", pretty_print=False)
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>' + xml_str

        # lxml omite xmlns nos filhos quando o pai já declara o NS; o ISS.net valida
        # cada fragmento (cabecalho, EnviarLote…, Dps) isoladamente — xmlns explícito evita E160.
        xml_str = _garantir_xmlns_raiz_fragmento(xml_str, "cabecalho")
        xml_str = _garantir_xmlns_raiz_fragmento(xml_str, dados_local)
        xml_str = _garantir_xmlns_dps_no_lote(xml_str)
        return xml_str

    def _post_header(self, metodo: str) -> dict:
        from urllib.parse import urlparse

        parsed = urlparse(self._url)
        origin = "%s://%s" % (parsed.scheme, parsed.netloc)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"%s/%s"' % (NS, metodo),
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/xml, application/soap+xml, application/xml, */*;q=0.9",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": origin,
            "Referer": "%s/" % origin,
            "Connection": "keep-alive",
        }
        return headers

    @staticmethod
    def _http_post(
        url: str,
        data: bytes,
        headers: dict,
        cert: tuple,
        timeout: int = 60,
    ) -> requests.Response:
        """POST SOAP com mTLS; curl_cffi quando disponível (ISSNet/WAF)."""
        try:
            from curl_cffi import requests as curl_requests  # type: ignore[import-untyped]

            return curl_requests.post(
                url,
                data=data,
                headers=headers,
                cert=cert,
                verify=False,
                timeout=timeout,
                impersonate="chrome120",
            )
        except ImportError:
            return requests.post(
                url,
                data=data,
                headers=headers,
                cert=cert,
                verify=False,
                timeout=timeout,
            )

    def _post_soap(
        self,
        metodo: str,
        dados_xml: etree._Element,
        timeout: int = 60,
    ) -> requests.Response:
        """Envia requisição SOAP com mTLS usando o certificado A1."""
        cert_a1 = CertificadoA1(self.certificado)
        chave, cert = cert_a1.separar_arquivo(self.senha, caminho=True)

        envelope = self._construir_envelope_soap(metodo, dados_xml)

        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        logger.info(
            "pynfse_nacional SOAP [%s] → %s\n%s",
            metodo,
            self._url,
            envelope[:3000],
        )

        try:
            with open("/tmp/nfse_soap_request.xml", "w", encoding="utf-8") as _f:
                _f.write(envelope)
        except Exception:
            pass

        try:
            result = self._http_post(
                self._url,
                data=envelope.encode("utf-8"),
                headers=self._post_header(metodo),
                cert=(cert, chave),
                timeout=timeout,
            )
            result.encoding = "utf-8"
            logger.info(
                "pynfse_nacional SOAP response [%s] HTTP %s:\n%s",
                metodo,
                result.status_code,
                result.text[:3000],
            )
            try:
                with open("/tmp/nfse_soap_response.xml", "w", encoding="utf-8") as _f:
                    _f.write(result.text)
            except Exception:
                pass
            return result
        except requests.exceptions.RequestException as e:
            raise e
        finally:
            cert_a1.excluir()

    @staticmethod
    def _normalizar_elemento_nfse(elemento: etree._Element) -> etree._Element:
        """Retorna elemento NFSe pronto para DANFSE (BrazilFiscalReport)."""
        tag = etree.QName(elemento).localname
        if tag == "NFSe":
            return elemento
        if tag == "CompNfse":
            inner = elemento.find(f"{{{NS}}}NFSe")
            if inner is None:
                inner = elemento.find(".//{%s}NFSe" % NS)
            if inner is not None:
                return inner
            return elemento
        if tag == "infNFSe":
            nfse = etree.Element(
                "{%s}NFSe" % NS,
                nsmap={None: NS},
                versao=VERSAO_NFSE_NACIONAL,
            )
            nfse.append(elemento)
            return nfse
        return elemento

    @staticmethod
    def extrair_nfse_xml_da_resposta(root: etree._Element) -> str | None:
        """
        Extrai XML da NFS-e autorizada (emissão síncrona ou consulta).

        Nacional v1.01: ListaNfse > CompNfse > NFSe > infNFSe
        Consulta por DPS: CompNfse > NFSe
        """
        ns = {"n": NS}

        for nfse in root.findall(".//n:NFSe", ns):
            normalizado = ComunicacaoNFSeNacional._normalizar_elemento_nfse(nfse)
            return etree.tostring(normalizado, encoding="unicode")

        comp = root.find(".//n:CompNfse", ns)
        if comp is not None:
            normalizado = ComunicacaoNFSeNacional._normalizar_elemento_nfse(comp)
            return etree.tostring(normalizado, encoding="unicode")

        inf = root.find(".//n:infNFSe", ns)
        if inf is not None:
            normalizado = ComunicacaoNFSeNacional._normalizar_elemento_nfse(inf)
            return etree.tostring(normalizado, encoding="unicode")

        lista = root.find(".//n:ListaNfse", ns)
        if lista is not None:
            for child in lista:
                tag = etree.QName(child).localname
                if tag in ("NFSe", "CompNfse", "infNFSe"):
                    normalizado = ComunicacaoNFSeNacional._normalizar_elemento_nfse(child)
                    return etree.tostring(normalizado, encoding="unicode")

        # Fallback: namespace-agnóstico (ABRASF municipal misto)
        for el in root.iter():
            tag = etree.QName(el).localname
            if tag in ("NFSe", "CompNfse", "infNFSe"):
                normalizado = ComunicacaoNFSeNacional._normalizar_elemento_nfse(el)
                return etree.tostring(normalizado, encoding="unicode")

        return None

    @staticmethod
    def extrair_urls_resposta(root: etree._Element) -> list[str]:
        """Extrai URLs de ConsultarUrlNfseResposta (ListaLinks/Links)."""
        ns = {"n": NS}
        urls: list[str] = []
        for links in root.findall(".//n:Links", ns):
            for child in links:
                tag = etree.QName(child).localname
                if tag.lower().endswith("url") and child.text:
                    urls.append(child.text.strip())
        for el in root.iter():
            tag = etree.QName(el).localname
            if tag in ("UrlVisualizacao", "Url", "LinkVisualizacao", "Link") and el.text:
                url = el.text.strip()
                if url.startswith("http") and url not in urls:
                    urls.append(url)
        return urls

    @staticmethod
    def extrair_nfse_resposta(resposta: requests.Response) -> dict:
        """
        Utilitário para parsear a resposta do webservice.
        Retorna dict com 'status', 'numero_lote', 'protocolo', 'nfse_xml', 'urls', 'erros'.
        """
        resultado = {
            "status": resposta.status_code,
            "raw": resposta.text,
            "protocolo": None,
            "nfse_xml": None,
            "urls": [],
            "erros": [],
        }

        if resposta.status_code != 200:
            snippet = (resposta.text or "").strip()
            if snippet.startswith("<!DOCTYPE") or snippet.startswith("<html"):
                resultado["erros"].append(
                    {
                        "codigo": f"HTTP_{resposta.status_code}",
                        "mensagem": (
                            f"Webservice retornou HTTP {resposta.status_code} "
                            "(operação pode não estar disponível neste endpoint ISSNet)."
                        ),
                    }
                )
            else:
                resultado["erros"].append(
                    {
                        "codigo": f"HTTP_{resposta.status_code}",
                        "mensagem": snippet[:500] or f"HTTP {resposta.status_code}",
                    }
                )
            return resultado

        try:
            root = etree.fromstring(resposta.content)
            ns = {"n": NS}

            prot = root.find(".//n:Protocolo", ns)
            if prot is not None and prot.text:
                resultado["protocolo"] = prot.text.strip()

            nfse_xml = ComunicacaoNFSeNacional.extrair_nfse_xml_da_resposta(root)
            if nfse_xml:
                resultado["nfse_xml"] = nfse_xml

            resultado["urls"] = ComunicacaoNFSeNacional.extrair_urls_resposta(root)

            for msg in root.findall(".//n:MensagemRetorno", ns):
                codigo = msg.findtext("n:Codigo", namespaces=ns)
                mensagem = msg.findtext("n:Mensagem", namespaces=ns)
                if codigo or mensagem:
                    resultado["erros"].append({"codigo": codigo, "mensagem": mensagem})

        except etree.XMLSyntaxError:
            resultado["erros"].append({"codigo": "XML_PARSE_ERROR", "mensagem": resposta.text})

        return resultado
