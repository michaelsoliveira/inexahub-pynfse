# Comunicação SOAP ISSNet / Nota Control — ABRASF 2.04 (RPS) e legado 2.01
#
# Modelo principal (Macapá e demais Nota Control):
#   RPS → RecepcionarLoteRps(Sincrono) → ISSNet converte → NFS-e
#
# Cada contribuinte (clínica/autônomo) usa certificado A1, IM, série e faixa RPS próprios.
# Protocolo: HTTPS + mTLS | Envelope SOAP 1.1 (CDATA em ABRASF 2.04)
#
# Métodos: RecepcionarLoteRps, ConsultarLoteRps, ConsultarNfsePorRps, CancelarNfse

from __future__ import annotations

import re
import requests
from typing import Any, cast

import lxml.etree as etree

from pynfe.entidades.certificado import CertificadoA1
from pynfe.processamento.assinatura import AssinaturaA1
from pynfe.processamento.serializacao_nfse_issnet import (
    serializar_lote,
    serializar_rps,
    empacotar_rps_assinado,
    empacotar_lote_assinado,
    _sub,
    _cpf_cnpj_element,
)
from pynfe.utils.nfse.issnet import (
    VERSAO_ABRASF204,
    VERSAO_CABECALHO_ABRASF204,
    NAMESPACE_ABRASF,
    NAMESPACE_SERVICO_ISSNET,
    detectar_layout_issnet,
    namespace_servico_por_url,
    versao_abrasf_por_url,
    METODO_RECEPCIONAR_LOTE_SINCRONO,
    METODO_RECEPCIONAR_LOTE,
    METODO_GERAR_NFSE,
    METODO_CANCELAR_NFSE,
    METODO_CONSULTAR_NFSE_POR_RPS,
    METODO_CONSULTAR_LOTE_RPS,
    METODO_CONSULTAR_SITUACAO_LOTE,
)
from pynfe.utils.nfse.issnet.abrasf204 import url_webservice

NS = NAMESPACE_ABRASF
NAMESPACE_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"


# Reexportação retrocompatível — implementação em serializacao_nfse_issnet.py
__all__ = [
    "ComunicacaoISSNetMunicipal",
    "ComunicacaoISSNetAbrasf204",
    "serializar_rps",
    "serializar_lote",
    "url_por_municipio",
]


# ---------------------------------------------------------------------------
# Classe principal de comunicação
# ---------------------------------------------------------------------------

class ComunicacaoISSNetMunicipal:
    """
    Cliente SOAP ISSNet / Nota Control — ABRASF 2.04 (RPS) e legado 2.01.

    Fluxo principal (Macapá e demais municípios Nota Control):
      RPS assinado → RecepcionarLoteRpsSincrono → CompNfse

    Cada contribuinte usa certificado A1, IM, série e numeração RPS próprios
    (faixa autorizada pela prefeitura — multi-tenant SaaS).

    Use ``para_municipio(ibge=...)`` para resolver URL e layout automaticamente.
    """

    def __init__(
        self,
        certificado: str,
        senha: str,
        url: str,
        homologacao: bool = True,
        namespace_servico: str = NAMESPACE_SERVICO_ISSNET,
    ):
        self.certificado = certificado
        self.senha = senha
        self.url = url.rstrip("?WSDL").rstrip("?wsdl")
        self.homologacao = homologacao
        self._layout = detectar_layout_issnet(self.url)
        self._versao_abrasf = versao_abrasf_por_url(self.url)
        self._namespace_servico = (
            namespace_servico
            if namespace_servico != NAMESPACE_SERVICO_ISSNET
            else namespace_servico_por_url(self.url)
        )
        self._mensagem_cdata = self._layout == "abrasf204"
        self._assinador = AssinaturaA1(certificado, senha)

    @classmethod
    def para_municipio(
        cls,
        certificado: str,
        senha: str,
        ibge: str,
        *,
        homologacao: bool = True,
        ws_url: str | None = None,
    ) -> "ComunicacaoISSNetMunicipal":
        """Factory por IBGE do contribuinte (URL ABRASF 2.04 ou legado)."""
        url = url_webservice(ibge, homologacao, ws_url)
        return cls(certificado=certificado, senha=senha, url=url, homologacao=homologacao)

    @property
    def versao_abrasf(self) -> str:
        return self._versao_abrasf

    @property
    def layout(self) -> str:
        return self._layout

    def enviar_lote_sincrono(
        self,
        lista_rps: list,
        numero_lote: str = "1",
        emitente_cnpj_cpf: str | None = None,
        emitente_im: str | None = None,
    ) -> requests.Response:
        """
        Envia um lote de RPS de forma síncrona.

        Parâmetros:
            lista_rps        – lista de dicts com dados de cada RPS
                               (ver docstring de serializar_rps)
            numero_lote      – número do lote (sequencial)
            emitente_cnpj_cpf – CNPJ/CPF do emitente (se None, usa do primeiro RPS)
            emitente_im      – inscrição municipal (se None, usa do primeiro RPS)
        """
        if not lista_rps:
            raise ValueError("lista_rps não pode ser vazia")

        # Inferir emitente do primeiro RPS quando não fornecido explicitamente
        primeiro = lista_rps[0]
        cnpj_cpf = emitente_cnpj_cpf or primeiro.get("prest_cnpj_cpf", "")
        im = emitente_im or primeiro.get("prest_im", "")

        rps_assinados = [
            self._assinar_rps(serializar_rps(r, versao_abrasf=self._versao_abrasf))
            for r in lista_rps
        ]
        lote_xml = serializar_lote(
            rps_assinados,
            numero_lote,
            cnpj_cpf,
            im,
            sincrono=True,
            versao_abrasf=self._versao_abrasf,
        )
        lote_xml = self._assinar_lote(lote_xml)

        return self._post_soap(METODO_RECEPCIONAR_LOTE_SINCRONO, lote_xml)

    recepcionar_lote_rps_sincrono = enviar_lote_sincrono

    def recepcionar_lote(
        self,
        lista_rps: list,
        numero_lote: str = "1",
        emitente_cnpj_cpf: str | None = None,
        emitente_im: str | None = None,
    ) -> requests.Response:
        """Envia lote de forma assíncrona. Retorna protocolo para consulta posterior."""
        if not lista_rps:
            raise ValueError("lista_rps não pode ser vazia")

        primeiro = lista_rps[0]
        cnpj_cpf = emitente_cnpj_cpf or primeiro.get("prest_cnpj_cpf", "")
        im = emitente_im or primeiro.get("prest_im", "")

        rps_assinados = [
            self._assinar_rps(serializar_rps(r, versao_abrasf=self._versao_abrasf))
            for r in lista_rps
        ]
        lote_xml = serializar_lote(
            rps_assinados,
            numero_lote,
            cnpj_cpf,
            im,
            sincrono=False,
            versao_abrasf=self._versao_abrasf,
        )
        lote_xml = self._assinar_lote(lote_xml)

        return self._post_soap(METODO_RECEPCIONAR_LOTE, lote_xml)

    recepcionar_lote_rps = recepcionar_lote

    def gerar_nfse(self, rps: dict) -> requests.Response:
        """Gera NFS-e diretamente a partir de um único RPS (GerarNfse)."""
        rps_xml = self._assinar_rps(serializar_rps(rps, versao_abrasf=self._versao_abrasf))

        raiz = etree.Element("{%s}GerarNfseEnvio" % NS, nsmap={None: NS})

        prest = etree.SubElement(raiz, "{%s}Rps" % NS)
        prest.append(rps_xml)

        return self._post_soap(METODO_GERAR_NFSE, raiz)

    def cancelar_nfse(
        self,
        numero_nfse: str,
        cod_municipio: str,
        emitente_cnpj_cpf: str,
        emitente_im: str,
        codigo_cancelamento: str = "1",
    ) -> requests.Response:
        """
        Cancela uma NFS-e emitida.

        Parâmetros:
            numero_nfse         – número da NFS-e a cancelar
            cod_municipio       – IBGE 7 dígitos do município emitente
            emitente_cnpj_cpf   – CNPJ (14) ou CPF (11) do emitente
            emitente_im         – inscrição municipal do emitente
            codigo_cancelamento – "1"=Erro na emissão, "2"=Serviço não prestado,
                                  "3"=Erro de assinatura, "4"=Outros (default: "1")
        """
        raiz = etree.Element("{%s}CancelarNfseEnvio" % NS, nsmap={None: NS})

        pedido = etree.SubElement(raiz, "{%s}Pedido" % NS)
        inf_pedido = etree.SubElement(
            pedido, "{%s}InfPedidoCancelamento" % NS, Id="CancelamentoNfse"
        )

        id_nfse = _sub(inf_pedido, "IdentificacaoNfse")
        _sub(id_nfse, "Numero", numero_nfse)
        _cpf_cnpj_element(id_nfse, emitente_cnpj_cpf)
        _sub(id_nfse, "InscricaoMunicipal", emitente_im)
        _sub(id_nfse, "CodigoMunicipio", cod_municipio)

        _sub(inf_pedido, "CodigoCancelamento", codigo_cancelamento)

        # Assinar o pedido de cancelamento
        pedido_assinado = self._assinador.assinar(pedido)
        raiz.remove(pedido)
        raiz.append(pedido_assinado)

        return self._post_soap(METODO_CANCELAR_NFSE, raiz)

    def consultar_nfse_por_rps(
        self,
        numero_rps: str,
        serie_rps: str,
        tipo_rps: int,
        emitente_cnpj_cpf: str,
        emitente_im: str,
    ) -> requests.Response:
        """Consulta NFS-e pelo número de RPS correspondente."""
        raiz = etree.Element("{%s}ConsultarNfsePorRpsEnvio" % NS, nsmap={None: NS})

        id_rps = _sub(raiz, "IdentificacaoRps")
        _sub(id_rps, "Numero", numero_rps)
        _sub(id_rps, "Serie", serie_rps)
        _sub(id_rps, "Tipo", str(tipo_rps))

        prest = _sub(raiz, "Prestador")
        _cpf_cnpj_element(prest, emitente_cnpj_cpf)
        _sub(prest, "InscricaoMunicipal", emitente_im)

        return self._post_soap(METODO_CONSULTAR_NFSE_POR_RPS, raiz)

    def consultar_lote(
        self,
        protocolo: str,
        emitente_cnpj_cpf: str,
        emitente_im: str,
    ) -> requests.Response:
        """Consulta resultado de um lote assíncrono pelo protocolo."""
        raiz = etree.Element("{%s}ConsultarLoteRpsEnvio" % NS, nsmap={None: NS})

        prest = _sub(raiz, "Prestador")
        _cpf_cnpj_element(prest, emitente_cnpj_cpf)
        _sub(prest, "InscricaoMunicipal", emitente_im)

        _sub(raiz, "Protocolo", protocolo)

        return self._post_soap(METODO_CONSULTAR_LOTE_RPS, raiz)

    consultar_lote_rps = consultar_lote

    def consultar_situacao_lote(
        self,
        protocolo: str,
        emitente_cnpj_cpf: str,
        emitente_im: str,
    ) -> requests.Response:
        """Consulta situação de um lote assíncrono."""
        raiz = etree.Element("{%s}ConsultarSituacaoLoteRpsEnvio" % NS, nsmap={None: NS})

        prest = _sub(raiz, "Prestador")
        _cpf_cnpj_element(prest, emitente_cnpj_cpf)
        _sub(prest, "InscricaoMunicipal", emitente_im)

        _sub(raiz, "Protocolo", protocolo)

        return self._post_soap(METODO_CONSULTAR_SITUACAO_LOTE, raiz)

    # ------------------------------------------------------------------ #
    # Métodos internos                                                     #
    # ------------------------------------------------------------------ #

    def _assinar_elemento_por_id(self, elemento: etree._Element, id_val: str) -> etree._Element:
        import signxml
        from pynfe.utils import CustomXMLSigner, remover_acentos

        xml_str = remover_acentos(
            etree.tostring(elemento, encoding="unicode", pretty_print=False)
        )
        elemento = etree.fromstring(xml_str)

        signer = CustomXMLSigner(
            method=signxml.methods.enveloped,
            signature_algorithm="rsa-sha1",
            digest_algorithm="sha1",
            c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
        )
        signer.excise_empty_xmlns_declarations = True
        signer.namespaces = cast(dict[str, Any], {None: signer.namespaces["ds"]})

        signed = signer.sign(
            elemento,
            key=self._assinador.key,
            cert=self._assinador.cert,
            reference_uri="#%s" % id_val,
        )
        return etree.fromstring(
            etree.tostring(signed, encoding="unicode", pretty_print=False)
        )

    def _assinar_rps(self, inf_xml: etree._Element) -> etree._Element:
        """
        Assina InfDeclaracaoPrestacaoServico; Signature fica irmã dentro de Rps.
        """
        id_val = inf_xml.attrib.get("Id")
        if not id_val:
            raise ValueError("InfDeclaracaoPrestacaoServico não possui atributo Id.")
        signed = self._assinar_elemento_por_id(inf_xml, id_val)
        return empacotar_rps_assinado(signed)

    def _assinar_lote(self, envio_xml: etree._Element) -> etree._Element:
        """
        Assina LoteRps; Signature fica irmã de LoteRps (ABRASF 2.04 / Ginfes).
        """
        lote = envio_xml.find(".//{%s}LoteRps" % NS)
        if lote is None:
            raise ValueError("EnviarLoteRpsEnvio sem elemento LoteRps.")
        id_val = lote.attrib.get("Id")
        if not id_val:
            raise ValueError("LoteRps não possui atributo Id.")

        signed_lote = self._assinar_elemento_por_id(lote, id_val)
        parent = lote.getparent()
        idx = list(parent).index(lote)
        parent.remove(lote)
        parent.insert(idx, signed_lote)
        return empacotar_lote_assinado(envio_xml)

    def _criar_cabecalho(self) -> etree._Element:
        """Cabeçalho nfseCabecMsg conforme versão ABRASF do webservice."""
        cab_attr = (
            VERSAO_CABECALHO_ABRASF204
            if self._versao_abrasf == VERSAO_ABRASF204
            else self._versao_abrasf
        )
        cab = etree.Element(
            "{%s}cabecalho" % NS,
            versao=cab_attr,
            nsmap={None: NS},
        )
        vd = etree.SubElement(cab, "{%s}versaoDados" % NS)
        vd.text = self._versao_abrasf
        return cab

    def _construir_envelope(self, metodo: str, dados_xml: etree._Element) -> str:
        """Monta envelope SOAP 1.1 para ISSNet ABRASF."""
        if self._mensagem_cdata:
            return self._construir_envelope_cdata(metodo, dados_xml)

        envelope = etree.Element(
            "{%s}Envelope" % NAMESPACE_SOAP,
            nsmap={
                "soap": NAMESPACE_SOAP,
                "xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "xsd": "http://www.w3.org/2001/XMLSchema",
            },
        )
        body = etree.SubElement(envelope, "{%s}Body" % NAMESPACE_SOAP)

        # Wrapper do método no namespace do serviço ISSNet
        wrapper = etree.SubElement(
            body,
            "{%s}%s" % (self._namespace_servico, metodo),
            nsmap={None: self._namespace_servico},
        )

        # nfseCabecMsg
        cab_el = etree.SubElement(wrapper, "{%s}nfseCabecMsg" % self._namespace_servico)
        cab_el.append(self._criar_cabecalho())

        # nfseDadosMsg
        dados_el = etree.SubElement(wrapper, "{%s}nfseDadosMsg" % self._namespace_servico)
        dados_el.append(dados_xml)

        xml_str = etree.tostring(envelope, encoding="unicode", pretty_print=False)
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>' + xml_str

        # Garantir xmlns explícito no cabecalho e nos dados (validação por fragmento)
        xml_str = _garantir_xmlns(xml_str, "cabecalho", NS)
        dados_local = etree.QName(dados_xml).localname
        xml_str = _garantir_xmlns(xml_str, dados_local, NS)

        return xml_str

    def _construir_envelope_cdata(self, metodo: str, dados_xml: etree._Element) -> str:
        """
        Envelope ABRASF 2.04: nfseCabecMsg/nfseDadosMsg são xsd:string (CDATA).

        WSDL Macapá: targetNamespace http://nfse.abrasf.org.br
        """
        cab_xml = _fragmento_xml(self._criar_cabecalho())
        dados_xml_str = _fragmento_xml(dados_xml)
        cab_xml = _garantir_xmlns(cab_xml, "cabecalho", NS)
        dados_local = etree.QName(dados_xml).localname
        dados_xml_str = _garantir_xmlns(dados_xml_str, dados_local, NS)

        ns = self._namespace_servico
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="%s" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
            "<soap:Body>"
            '<%s xmlns="%s">'
            "<nfseCabecMsg><![CDATA[%s]]></nfseCabecMsg>"
            "<nfseDadosMsg><![CDATA[%s]]></nfseDadosMsg>"
            "</%s>"
            "</soap:Body>"
            "</soap:Envelope>"
        ) % (NAMESPACE_SOAP, metodo, ns, cab_xml, dados_xml_str, metodo)

    def _post_header(self, metodo: str) -> dict:
        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        origin = "%s://%s" % (parsed.scheme, parsed.netloc)
        # ASMX .NET: SOAPAction = namespace + método (ACBr ISSNet.ini)
        soap_action = '"%s/%s"' % (self._namespace_servico.rstrip("/"), metodo)

        return {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": soap_action,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/xml, application/soap+xml, application/xml, */*;q=0.9",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Origin": origin,
            "Referer": "%s/" % origin,
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }

    def _post_soap(
        self,
        metodo: str,
        dados_xml: etree._Element,
        timeout: int = 60,
    ) -> requests.Response:
        """Envia requisição SOAP com mTLS usando certificado A1."""
        cert_a1 = CertificadoA1(self.certificado)
        chave, cert = cert_a1.separar_arquivo(self.senha, caminho=True)

        envelope = self._construir_envelope(metodo, dados_xml)

        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        import logging as _log
        _logger = _log.getLogger(__name__)
        _logger.info("pynfse_issnet SOAP request [%s]:\n%s", metodo, envelope[:3000])

        try:
            with open("/tmp/nfse_issnet_request.xml", "w", encoding="utf-8") as _f:
                _f.write(envelope)
        except Exception:
            pass

        headers = self._post_header(metodo)

        try:
            result = self._http_post(
                self.url,
                data=envelope.encode("utf-8"),
                headers=headers,
                cert=(cert, chave),
                timeout=timeout,
            )
            result.encoding = "utf-8"
            _logger.info(
                "pynfse_issnet SOAP response HTTP %s:\n%s",
                result.status_code,
                result.text[:3000],
            )
            try:
                with open("/tmp/nfse_issnet_response.xml", "w", encoding="utf-8") as _f:
                    _f.write(result.text)
            except Exception:
                pass
            return result
        except requests.exceptions.RequestException as e:
            raise e
        finally:
            cert_a1.excluir()

    @staticmethod
    def _http_post(url: str, data: bytes, headers: dict, cert: tuple, timeout: int = 60):
        """POST SOAP com mTLS (certificado A1)."""
        _log = __import__("logging").getLogger(__name__)

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
            pass
        except Exception:
            _log.debug("curl_cffi falhou; usando requests", exc_info=True)

        return requests.post(
            url,
            data=data,
            headers=headers,
            cert=cert,
            verify=False,
            timeout=timeout,
        )

    @staticmethod
    def extrair_resposta(resposta: requests.Response) -> dict:
        """
        Parseia a resposta do webservice ABRASF.

        Retorna dict com:
            status          – HTTP status code
            raw             – texto da resposta
            numero_lote     – número do lote (se síncrono)
            protocolo       – protocolo (se assíncrono)
            nfse_xml        – XML da CompNfse (se emitida)
            numero_nfse     – número da NFS-e (se emitida)
            erros           – lista de {"codigo": ..., "mensagem": ...}
        """
        resultado = {
            "status": resposta.status_code,
            "raw": resposta.text,
            "numero_lote": None,
            "protocolo": None,
            "nfse_xml": None,
            "numero_nfse": None,
            "erros": [],
        }

        if resposta.status_code != 200:
            texto = (resposta.text or "").strip()
            cf_mitigated = (resposta.headers.get("cf-mitigated") or "").lower()
            mensagem = "HTTP %s" % resposta.status_code
            fault = _extrair_soap_fault(texto)
            if fault or _extrair_soap_fault_detalhe(texto):
                mensagem = _mensagem_soap_fault_http(resposta.status_code, texto, fault)
            elif resposta.status_code == 403 and (
                "cloudflare" in texto.lower()
                or "just a moment" in texto.lower()
                or cf_mitigated == "challenge"
            ):
                mensagem = (
                    "HTTP 403: ISSNet/Cloudflare bloqueou o acesso automatizado "
                    "(desafio WAF). Solicite à prefeitura/ISSNet a liberação do IP "
                    "fixo do servidor para integração SOAP, ou teste de uma rede "
                    "residencial/VPN autorizada."
                )
            elif resposta.status_code == 404 and "<html" in (texto or "").lower():
                # ASP.NET/IIS "Não é possível encontrar o recurso" — URL do webservice errada
                mensagem = (
                    "HTTP 404: URL do webservice ISSNet não encontrada. "
                    "O endpoint de homologação pode ter sido descontinuado ou movido. "
                    "Verifique a URL com o suporte ISSNet/Nota Control ou configure "
                    "issnet_ws_url diretamente na clínica."
                )
            elif texto:
                lower = texto[:500].lower()
                if "cloudflare" in lower or "<html" in lower:
                    mensagem = (
                        "HTTP %s: bloqueio WAF/proxy (resposta HTML)"
                        % resposta.status_code
                    )
                else:
                    mensagem = "HTTP %s: %s" % (resposta.status_code, texto[:500])
            resultado["erros"].append({
                "codigo": "HTTP_%s" % resposta.status_code,
                "mensagem": mensagem,
                "correcao": None,
                "raw_response": texto[:2000] if texto else None,
            })
            return resultado

        try:
            root = etree.fromstring(resposta.content)

            # SOAP Fault em HTTP 200 (comportamento de alguns endpoints .NET ASMX)
            soap_fault = _extrair_soap_fault(resposta.text)
            if soap_fault:
                mensagem_fault = soap_fault.strip()
                if mensagem_fault.lower() == "error":
                    mensagem_fault = (
                        "ISSNet retornou SOAP Fault genérico (faultstring=Error). "
                        "Possíveis causas: (1) IM não liberada para o webservice de "
                        "produção — solicite liberação à prefeitura/ISSNet; "
                        "(2) número de RPS já emitido (tente o próximo número); "
                        "(3) CNAE ou código de tributação municipal inválido para "
                        "este município; (4) série RPS não autorizada para a IM."
                    )
                resultado["erros"].append({
                    "codigo": "SOAP_FAULT",
                    "mensagem": mensagem_fault,
                    "correcao": None,
                })
                return resultado

            payload_xml = _extrair_payload_resposta_abrasf(root)
            if payload_xml is not None:
                root = payload_xml

            ns = {"n": NS}

            # Protocolo (envio assíncrono)
            prot = root.find(".//n:Protocolo", ns)
            if prot is not None:
                resultado["protocolo"] = prot.text

            # NFS-e emitida (síncrono/GerarNfse)
            comp = root.find(".//n:CompNfse", ns)
            if comp is not None:
                resultado["nfse_xml"] = etree.tostring(comp, encoding="unicode")
                num = comp.find(".//n:Numero", ns)
                if num is not None:
                    resultado["numero_nfse"] = num.text

            # Erros ABRASF
            for msg in root.findall(".//n:MensagemRetorno", ns):
                codigo = msg.findtext("n:Codigo", namespaces=ns)
                mensagem = msg.findtext("n:Mensagem", namespaces=ns)
                correcao = msg.findtext("n:Correcao", namespaces=ns)
                resultado["erros"].append({
                    "codigo": codigo,
                    "mensagem": mensagem,
                    "correcao": correcao,
                })

        except etree.XMLSyntaxError:
            resultado["erros"].append({
                "codigo": "XML_PARSE_ERROR",
                "mensagem": resposta.text,
                "correcao": None,
            })

        return resultado


# ---------------------------------------------------------------------------
# Utilitários públicos
# ---------------------------------------------------------------------------

def url_por_municipio(ibge: str, homologacao: bool = False) -> str:
    """Reexporta URL ISSNet — ver pynfe.utils.nfse.issnet.url_por_municipio."""
    from pynfe.utils.nfse.issnet import url_por_municipio as _url

    return _url(ibge, homologacao=homologacao)


def _fragmento_xml(elemento: etree._Element) -> str:
    """Serializa elemento XML sem declaração <?xml ...?>."""
    xml = etree.tostring(elemento, encoding="unicode", pretty_print=False).strip()
    if xml.startswith("<?xml"):
        xml = xml.split("?>", 1)[-1].strip()
    return xml


def _extrair_soap_fault(texto: str) -> str | None:
    """Extrai faultstring de resposta SOAP Fault, se houver."""
    detalhe = _extrair_soap_fault_detalhe(texto)
    return detalhe.get("faultstring") if detalhe else None


def _extrair_soap_fault_detalhe(texto: str) -> dict[str, str] | None:
    """Extrai faultcode, faultstring e detail de um SOAP Fault."""
    if not texto or "fault" not in texto.lower():
        return None
    try:
        root = etree.fromstring(texto.encode("utf-8"))
    except etree.XMLSyntaxError:
        return None

    out: dict[str, str] = {}
    for el in root.iter():
        local = etree.QName(el.tag).localname
        if local in ("faultstring", "faultcode", "detail") and (el.text or "").strip():
            out[local] = el.text.strip()
        elif local == "detail" and len(el) and "detail" not in out:
            out["detail"] = etree.tostring(el, encoding="unicode", pretty_print=False)[:500]

    if not out.get("faultstring") and not out.get("faultcode"):
        return None
    return out


def _mensagem_soap_fault_http(
    status_code: int,
    texto: str,
    fault: str | None,
) -> str:
    """Monta mensagem de erro incluindo corpo bruto do SOAP Fault."""
    detalhe = _extrair_soap_fault_detalhe(texto) or {}
    partes = [f"HTTP {status_code}"]
    if detalhe.get("faultcode"):
        partes.append(f"faultcode={detalhe['faultcode']}")
    if fault:
        partes.append(f"faultstring={fault}")
    if detalhe.get("detail"):
        partes.append(f"detail={detalhe['detail'][:300]}")

    if fault and fault.strip().lower() == "error" and status_code >= 500:
        partes.append(
            "ISSNet retornou Fault genérico. Verifique: (1) IM/CPF liberados para "
            "webservice produção; (2) CodigoTributacaoMunicipio (ex.: 0401, não CNAE); "
            "(3) alíquota como fração 0.0500; (4) cabeçalho versao=2.04."
        )

    corpo = (texto or "").strip()
    if corpo:
        partes.append(f"raw={corpo[:800]}")
    return " | ".join(partes)


def _extrair_payload_resposta_abrasf(root: etree._Element) -> etree._Element | None:
    """
    ABRASF 2.04 encapsula o XML de retorno em <outputXML> (string/CDATA).
    Retorna o elemento raiz parseado do payload interno, ou None.
    """
    for el in root.iter():
        if etree.QName(el.tag).localname != "outputXML":
            continue
        inner = (el.text or "").strip()
        if not inner:
            continue
        try:
            return etree.fromstring(inner.encode("utf-8"))
        except etree.XMLSyntaxError:
            return None
    return None


def _garantir_xmlns(xml_str: str, localname: str, namespace: str) -> str:
    """Garante que o elemento raiz de um fragmento tenha xmlns explícito."""
    if f'xmlns="{namespace}"' in xml_str.split(f"<{localname}", 1)[-1].split(">", 1)[0]:
        return xml_str
    pattern = rf"<{re.escape(localname)}((?:\s[^>]*)?)>"

    def _repl(m):
        attrs = m.group(1) or ""
        if f'xmlns="{namespace}"' in attrs:
            return m.group(0)
        return f"<{localname}{attrs} xmlns=\"{namespace}\">"

    return re.sub(pattern, _repl, xml_str, count=1)


# Alias explícito para integrações ABRASF 2.04 (Nota Control / RPS)
ComunicacaoISSNetAbrasf204 = ComunicacaoISSNetMunicipal
