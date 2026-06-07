# Assinatura digital para NFS-e Padrão Nacional v1.01
#
# O manual exige assinatura em dois níveis (seção 7.3.3):
#   1. Assinar cada DPS individualmente (namespace http://www.sped.fazenda.gov.br/nfse)
#   2. Agrupar as DPS assinadas em um lote
#   3. Assinar o lote completo com o mesmo namespace
#
# Algoritmos exigidos pelo validador ISS.net/NotaControl (v1.01):
#   CanonicalizationMethod: http://www.w3.org/TR/2001/REC-xml-c14n-20010315
#   SignatureMethod: http://www.w3.org/2000/09/xmldsig#rsa-sha256
#   DigestMethod: http://www.w3.org/2000/09/xmldsig#sha256

import re
from typing import Union

import signxml
from lxml import etree

from pynfe.entidades.certificado import CertificadoA1
from pynfe.utils import CustomXMLSigner, remover_acentos
from pynfe.utils.nfse.nacional import NAMESPACE_NFSE_NACIONAL

NS = NAMESPACE_NFSE_NACIONAL


def _garantir_xmlns_dps_raiz(xml_str: str) -> str:
    """
    Declara xmlns na tag raiz <DPS> antes da assinatura.

    O ISS.net valida cada DPS como fragmento isolado (E160). Se o xmlns só existir
    por herança do lote, o validador pós-envio injeta xmlns na tag — invalidando
    a assinatura (E0714). O xmlns deve fazer parte do documento assinado.
    """

    def _repl(match: re.Match) -> str:
        tag = match.group(0)
        if f'xmlns="{NS}"' in tag:
            return tag
        local = "DPS" if tag.startswith("<DPS") else "Dps"
        return tag.replace(f"<{local}", f'<{local} xmlns="{NS}"', 1)

    xml_str = re.sub(r"<DPS\s+versao=\"[^\"]+\"", _repl, xml_str, count=1)
    return re.sub(r"<Dps\s+versao=\"[^\"]+\"", _repl, xml_str, count=1)


class AssinaturaNFSeNacional:
    """
    Assina documentos DPS e lotes conforme o padrão NFS-e Nacional v1.01.

    Uso:
        assinador = AssinaturaNFSeNacional(certificado_path, senha)

        # 1. Assina cada DPS individualmente
        dps_assinadas = [assinador.assinar_dps(dps_xml) for dps_xml in lista_dps_xml]

        # 2. Monta o lote com as DPS assinadas
        lote_xml = serializar_lote_sincrono(lote, dps_assinadas)

        # 3. Assina o lote completo
        lote_assinado = assinador.assinar_lote(lote_xml)
    """

    def __init__(self, certificado: str, senha: str):
        self._key, self._cert = CertificadoA1(certificado).separar_arquivo(senha)

    def _assinar_elemento(
        self,
        xml: etree._Element,
        retorna_string: bool = False,
    ) -> Union[str, etree._Element]:
        """
        Assina um elemento XML conforme os parâmetros exigidos pelo manual NFS-e Nacional.
        O elemento deve ter um atributo 'Id' para ser referenciado.
        """
        # Recupera o Id do elemento a assinar
        referencia = xml.find(".//*[@Id]")
        if referencia is None:
            raise ValueError(
                "Elemento XML não possui atributo 'Id' — obrigatório para assinatura NFS-e Nacional."
            )
        id_valor = referencia.attrib["Id"]

        # Remove acentos (requisito da assinatura)
        xml_str = remover_acentos(etree.tostring(xml, encoding="unicode", pretty_print=False))
        xml = etree.fromstring(xml_str)

        signer = CustomXMLSigner(
            method=signxml.methods.enveloped,
            signature_algorithm="rsa-sha256",
            digest_algorithm="sha256",
            c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
        )
        signer.excise_empty_xmlns_declarations = True

        # Usa apenas o namespace de assinatura sem prefixo
        ns = {None: signer.namespaces["ds"]}
        signer.namespaces = ns

        ref_uri = "#%s" % id_valor
        assinado = signer.sign(
            xml,
            key=self._key,
            cert=self._cert,
            reference_uri=ref_uri,
        )

        # Reparse para garantir compatibilidade lxml 6.x
        xml_assinado_str = etree.tostring(assinado, encoding="unicode", pretty_print=False)
        assinado = etree.fromstring(xml_assinado_str)

        if retorna_string:
            return xml_assinado_str
        return assinado

    def assinar_dps(
        self,
        dps_xml: etree._Element,
        retorna_string: bool = False,
    ) -> Union[str, etree._Element]:
        """
        Etapa 1: assina uma DPS individualmente.
        O namespace http://www.sped.fazenda.gov.br/nfse deve estar presente no elemento.
        """
        xml_str = etree.tostring(dps_xml, encoding="unicode", pretty_print=False)
        xml_str = _garantir_xmlns_dps_raiz(xml_str)
        raiz = etree.fromstring(xml_str.encode("utf-8"))
        return self._assinar_elemento(raiz, retorna_string=retorna_string)

    def assinar_lote(
        self,
        lote_xml: etree._Element,
        retorna_string: bool = False,
    ) -> Union[str, etree._Element]:
        """
        Etapa 3: assina o lote completo (que já contém as DPS assinadas).
        O LoteDps deve ter um atributo 'Id'.
        """
        return self._assinar_elemento(lote_xml, retorna_string=retorna_string)

    def assinar_cancelamento(
        self,
        cancelamento_xml: etree._Element,
        retorna_string: bool = False,
    ) -> Union[str, etree._Element]:
        """Assina o pedido de registro de evento (cancelamento)."""
        return self._assinar_elemento(cancelamento_xml, retorna_string=retorna_string)

    def preparar_lote_assinado(
        self,
        lote,
        lista_dps_xml: list,
        serializar_lote_fn,
    ) -> etree._Element:
        """
        Executa o fluxo completo de assinatura:
          1. Assina cada DPS da lista
          2. Monta o XML do lote com as DPS assinadas
          3. Assina o lote
          Retorna o lote assinado pronto para envio.
        """
        dps_assinadas = [self.assinar_dps(dps_xml) for dps_xml in lista_dps_xml]
        lote_xml = serializar_lote_fn(lote, dps_assinadas)
        return self.assinar_lote(lote_xml)
