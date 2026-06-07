import unittest
from decimal import Decimal

from lxml import etree

from pynfe.processamento.serializacao_nfse_nacional import serializar_dps
from pynfe.utils.nfse.nacional import NAMESPACE_NFSE_NACIONAL
from pynfe.utils.nfse.nacional.construtor import construir_dps
from pynfe.utils.nfse.nacional.validacao import validar_cpf

NS = NAMESPACE_NFSE_NACIONAL

TOMADOR_VALIDO = {
    "tomador_nome": "MARIA DOS SANTOS",
    "tomador_doc": "52998224725",
    "tomador_cod_municipio": "1600303",
    "tomador_cep": "68908390",
    "tomador_logradouro": "Avenida Acre",
    "tomador_numero": "863",
    "tomador_bairro": "Pacoval",
}


class ValidarCpfTest(unittest.TestCase):
    def test_cpf_invalido(self):
        self.assertFalse(validar_cpf("10589101112"))

    def test_cpf_valido(self):
        self.assertTrue(validar_cpf("52998224725"))


class ConstruirDpsMeEppTest(unittest.TestCase):
    def _config_ecpf_me_epp(self):
        return {
            "tipo_certificado_nfse": "e_cpf",
            "cpf": "86245899249",
            "inscricao_municipal": "187523",
            "nome_prestador": "CLINICA DR. EDUARDO COSTA",
            "opcao_simples_nacional": 3,
            "regime_apuracao_simples": 1,
            "cod_municipio_emissao": "5002704",
            "ibge": "1600303",
            "homologacao": True,
            "cod_tributacao_nacional": "040101",
            "cod_tributacao_municipal": "401",
            "descricao_servico": "Consulta Tecnica",
            "valor_servicos": "150.00",
            "p_tot_trib_sn": Decimal("5.00"),
            "serie": "70002",
            "numero_dps": "3",
            "id_dps_modo": "issnet_portal",
        }

    def test_ecpf_com_me_epp_no_config_vira_nao_optante(self):
        cfg = self._config_ecpf_me_epp()
        cfg["opcao_simples_nacional"] = 1
        dps = construir_dps(cfg, TOMADOR_VALIDO)
        xml = serializar_dps(dps)

        self.assertEqual(xml.find(f".//{{{NS}}}opSimpNac").text, "1")
        self.assertIsNone(xml.find(f".//{{{NS}}}regApTribSN"))
        self.assertIsNone(xml.find(f".//{{{NS}}}prest/{{{NS}}}xNome"))
        self.assertEqual(xml.find(f".//{{{NS}}}serie").text, "70002")
        self.assertEqual(xml.find(f".//{{{NS}}}nDPS").text, "3")
        inf = xml.find(f".//{{{NS}}}infDPS")
        self.assertEqual(len(inf.get("Id")), 45)
        self.assertEqual(
            inf.get("Id"),
            "DPS500270410008624589924970002100000000000003",
        )

    def test_ecpf_homolog_regras_negocio(self):
        cfg = self._config_ecpf_me_epp()
        cfg["opcao_simples_nacional"] = 2
        dps = construir_dps(cfg, TOMADOR_VALIDO)
        xml = serializar_dps(dps)

        self.assertEqual(xml.find(f".//{{{NS}}}opSimpNac").text, "2")
        # Homolog ISSNet: cLocEmi=Campo Grande, incidência=Macapá → regEspTrib=5
        self.assertEqual(xml.find(f".//{{{NS}}}regEspTrib").text, "5")
        self.assertIsNone(xml.find(f".//{{{NS}}}regApTribSN"))
        self.assertIsNone(xml.find(f".//{{{NS}}}pAliq"))
        self.assertIsNotNone(xml.find(f".//{{{NS}}}IBSCBS"))
        self.assertIsNone(xml.find(f".//{{{NS}}}dest"))
        self.assertIsNone(xml.find(f".//{{{NS}}}imovel"))
        self.assertIsNone(xml.find(f".//{{{NS}}}gReeRepRes"))
        self.assertEqual(xml.find(f".//{{{NS}}}tpRetISSQN").text, "1")
        self.assertEqual(xml.find(f".//{{{NS}}}cLocEmi").text, "5002704")
        loc = xml.find(f".//{{{NS}}}cLocPrestacao")
        self.assertEqual(loc.text, "1600303")

    def test_tomador_cpf_invalido_rejeita(self):
        cfg = self._config_ecpf_me_epp()
        with self.assertRaises(ValueError):
            construir_dps(cfg, {**TOMADOR_VALIDO, "tomador_doc": "10589101112"})

    def test_iss_retido_com_tomador_cpf_forca_sem_retencao(self):
        cfg = self._config_ecpf_me_epp()
        cfg["homologacao"] = False
        cfg["iss_retido"] = True
        dps = construir_dps(cfg, TOMADOR_VALIDO)
        xml = serializar_dps(dps)
        self.assertEqual(xml.find(f".//{{{NS}}}tpRetISSQN").text, "1")


if __name__ == "__main__":
    unittest.main()
