import unittest

from lxml import etree

from pynfe.processamento.comunicacao_nfse_nacional import ComunicacaoNFSeNacional
from pynfe.utils.nfse.nacional import NAMESPACE_NFSE_NACIONAL

NS = NAMESPACE_NFSE_NACIONAL


class ExtrairNfseXmlRespostaTest(unittest.TestCase):
    def test_nfse_nacional_v101(self):
        xml = f"""
        <EnviarLoteDpsSincronoResposta xmlns="{NS}">
          <NFSe versao="1.01">
            <infNFSe Id="NFS123">
              <nNFSe>42</nNFSe>
            </infNFSe>
          </NFSe>
        </EnviarLoteDpsSincronoResposta>
        """
        root = etree.fromstring(xml.encode())
        out = ComunicacaoNFSeNacional.extrair_nfse_xml_da_resposta(root)
        self.assertIsNotNone(out)
        self.assertIn("NFSe", out)
        self.assertIn("42", out)

    def test_lista_nfse_compnfse_wrapper(self):
        xml = f"""
        <EnviarLoteDpsSincronoResposta xmlns="{NS}">
          <ListaNfse>
            <CompNfse>
              <NFSe versao="1.01">
                <infNFSe Id="NFS456"><nNFSe>99</nNFSe></infNFSe>
              </NFSe>
            </CompNfse>
          </ListaNfse>
        </EnviarLoteDpsSincronoResposta>
        """
        root = etree.fromstring(xml.encode())
        out = ComunicacaoNFSeNacional.extrair_nfse_xml_da_resposta(root)
        self.assertIsNotNone(out)
        self.assertIn("<NFSe", out)
        self.assertNotIn("CompNfse", out)
        self.assertIn("99", out)

    def test_inf_nfse_sozinho(self):
        xml = f"""
        <ConsultarNfseDpsResposta xmlns="{NS}">
          <infNFSe Id="NFS789"><nNFSe>7</nNFSe></infNFSe>
        </ConsultarNfseDpsResposta>
        """
        root = etree.fromstring(xml.encode())
        out = ComunicacaoNFSeNacional.extrair_nfse_xml_da_resposta(root)
        self.assertIsNotNone(out)
        self.assertIn("<NFSe", out)
        self.assertIn("7", out)

    def test_compnfse_abrasf_legado(self):
        xml = """
        <root xmlns="http://www.abrasf.org.br/nfse.xsd">
          <CompNfse><Nfse><Numero>1</Numero></Nfse></CompNfse>
        </root>
        """
        root = etree.fromstring(xml.encode())
        out = ComunicacaoNFSeNacional.extrair_nfse_xml_da_resposta(root)
        self.assertIsNotNone(out)
        self.assertIn("CompNfse", out)


if __name__ == "__main__":
    unittest.main()
