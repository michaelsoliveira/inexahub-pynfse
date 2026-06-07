import unittest

from pynfe.utils.nfse.nacional.id_dps import gerar_id_dps
from pynfe.utils.nfse.nacional.sequencia_dps import (
    extrair_sequencia_dps_resposta,
    resolver_sequencia_emissao,
)


class GerarIdDpsPortalTest(unittest.TestCase):
    def test_exemplo_macapa_portal_xsd(self):
        """Id XSD (45 chars) — serie 70002, nDPS 2."""
        id_dps = gerar_id_dps(
            "1600303",
            "1",
            "86245899249",
            "70002",
            "2",
            modo="issnet_portal",
        )
        self.assertEqual(len(id_dps), 45)
        self.assertEqual(
            id_dps,
            "DPS160030310008624589924970002100000000000002",
        )

    def test_portal_ui_id_encurtado_diferente_do_xsd(self):
        """Portal UI omite padding do nDPS no Id — webservice não aceita."""
        id_xsd = gerar_id_dps("1600303", "1", "86245899249", "70002", "2")
        id_ui = "DPS1600303100086245899249700022"
        self.assertNotEqual(id_xsd, id_ui)
        self.assertEqual(len(id_ui), 31)

    def test_nacional_padrao_padded(self):
        id_dps = gerar_id_dps(
            "5002704",
            "1",
            "86245899249",
            "1",
            "18",
            modo="nacional_padrao",
        )
        self.assertTrue(id_dps.startswith("DPS500270410008624589924900001"))
        self.assertTrue(id_dps.endswith("100000000000018"))


class SequenciaDpsTest(unittest.TestCase):
    def test_sync_incrementa_ultimo_ndps(self):
        serie, numero = resolver_sequencia_emissao(
            {"serie_rps": "1", "proximo_numero_rps": "99"},
            {"serie": "70002", "numero_dps": "2"},
        )
        self.assertEqual(serie, "70002")
        self.assertEqual(numero, "3")

    def test_extrair_xml_portal(self):
        xml = """
        <ConsultarDpsDisponivelResposta xmlns="http://www.sped.fazenda.gov.br/nfse">
          <IdentificacaoDps>
            <SerieDPS>70002</SerieDPS>
            <NumDPS>2</NumDPS>
          </IdentificacaoDps>
        </ConsultarDpsDisponivelResposta>
        """
        data = extrair_sequencia_dps_resposta(xml)
        self.assertEqual(data["serie"], "70002")
        self.assertEqual(data["numero_dps"], "2")
        self.assertEqual(data["proximo_numero_dps"], "3")


if __name__ == "__main__":
    unittest.main()
