import datetime
import unittest
from decimal import Decimal

from lxml import etree

from pynfe.entidades.dps import (
    DPS,
    PrestadorDPS,
    ServicoCodigo,
    ServicoDPS,
    ServicoLocalPrestacao,
    TomadorDPS,
    ValoresDPS,
    InfoTributacao,
    TribMunicipal,
)
from pynfe.processamento.serializacao_nfse_nacional import (
    serializar_dps,
    serializar_lote_sincrono,
    _normalizar_cod_trib_municipal,
    _format_c_trib_mun,
    _format_c_trib_mun_issnet,
    _resolver_cod_nbs,
    _format_n_dps,
    _format_n_dps_elemento,
    _format_serie_id,
    _format_serie_elemento,
    _format_numero_lote,
    _id_lote,
    resolve_cod_municipio_emissao,
)
from pynfe.utils.nfse.nacional import ISSNET_HOMOLOGACAO_CLOC_EMI
from pynfe.entidades.dps import LoteDPS
from pynfe.utils.nfse.nacional import NAMESPACE_NFSE_NACIONAL

NS = NAMESPACE_NFSE_NACIONAL


class IssnetSchemaCamposTest(unittest.TestCase):
    def test_c_trib_mun_seis_digitos(self):
        self.assertEqual(_format_c_trib_mun("040101", "401"), "040101")
        self.assertEqual(_format_c_trib_mun("040101", ""), "040101")

    def test_c_trib_mun_issnet_dez_digitos_legado(self):
        self.assertEqual(_format_c_trib_mun_issnet("040101", "401", "1600303"), "1600303401")

    def test_cod_nbs_default_medicina(self):
        self.assertEqual(_resolver_cod_nbs("040101", None), "123012200")


class NormalizarCodTribMunicipalTest(unittest.TestCase):
    def test_tres_digitos_mantem(self):
        self.assertEqual(_normalizar_cod_trib_municipal("040101", "401"), "401")

    def test_seis_digitos_deriva_item_subitem(self):
        # 040101 = item 04 + subitem 01 → serviço 4.01 → 401
        self.assertEqual(_normalizar_cod_trib_municipal("040101", "040101"), "401")

    def test_fallback_do_nacional_item_subitem(self):
        self.assertEqual(_normalizar_cod_trib_municipal("040101", ""), "401")

    def test_outros_servicos_saude(self):
        # 04.02 → 402, 04.03 → 403
        self.assertEqual(_normalizar_cod_trib_municipal("040201", ""), "402")
        self.assertEqual(_normalizar_cod_trib_municipal("040301", ""), "403")


class FormatNDpsTest(unittest.TestCase):
    def test_id_nao_comeca_com_zero(self):
        self.assertEqual(_format_n_dps("18"), "100000000000018")
        self.assertEqual(_format_n_dps("1"), "100000000000001")

    def test_id_mantem_quando_ja_valido(self):
        self.assertEqual(_format_n_dps("100000000000018"), "100000000000018")

    def test_elemento_sem_padding(self):
        self.assertEqual(_format_n_dps_elemento("18"), "18")
        self.assertEqual(_format_n_dps_elemento("100000000000018"), "18")


class FormatSerieElementoTest(unittest.TestCase):
    def test_serie_id_com_padding(self):
        self.assertEqual(_format_serie_id("1"), "00001")
        self.assertEqual(_format_serie_id("00001"), "00001")
        self.assertEqual(_format_serie_id("RPS01"), "00001")


class ResolveCodMunicipioEmissaoTest(unittest.TestCase):
    def test_homologacao_forca_campo_grande(self):
        self.assertEqual(
            resolve_cod_municipio_emissao("1600303", True),
            ISSNET_HOMOLOGACAO_CLOC_EMI,
        )

    def test_producao_mantem_ibge_clinica(self):
        self.assertEqual(resolve_cod_municipio_emissao("1600303", False), "1600303")

    def test_portal_usa_ibge_real_em_producao(self):
        self.assertEqual(
            resolve_cod_municipio_emissao("1600303", False, portal=True),
            "1600303",
        )

    def test_portal_homolog_forca_campo_grande(self):
        self.assertEqual(
            resolve_cod_municipio_emissao("1600303", True, portal=True),
            "5002704",
        )


class FormatNumeroLoteTest(unittest.TestCase):
    def test_ts_num15_dig_com_padding(self):
        self.assertEqual(_format_numero_lote("18"), "000000000000018")
        self.assertEqual(_format_numero_lote("10"), "000000000000010")


class IdLoteNacionalTest(unittest.TestCase):
    def test_id_lote_modelo_issnet(self):
        self.assertEqual(_id_lote("10"), "Lote10")
        self.assertEqual(_id_lote("000000000000010"), "Lote10")
        self.assertEqual(_id_lote("18"), "Lote18")


class SerializarLoteSincronoTest(unittest.TestCase):
    def test_lote_dps_id_e_numero_lote(self):
        lote = LoteDPS()
        lote.numero_lote = "10"
        lote.prestador_cnpj = "73148327000189"
        lote.prestador_inscricao_municipal = "187523"
        xml = serializar_lote_sincrono(lote, [])
        lote_el = xml.find(f".//{{{NS}}}LoteDps")
        self.assertEqual(lote_el.get("Id"), "Lote10")
        num = xml.find(f".//{{{NS}}}NumeroLote")
        self.assertEqual(num.text, "000000000000010")
        qty = xml.find(f".//{{{NS}}}QuantidadeDps")
        self.assertIsNotNone(qty)
        self.assertEqual(qty.text, "0")


class SerializarDpsNacionalTest(unittest.TestCase):
    def _dps_minima(self) -> DPS:
        dps = DPS()
        dps.ambiente = 2
        dps.data_hora_emissao = datetime.datetime(2026, 6, 5, 0, 52, 51)
        dps.versao_aplicativo = "inexahub-test"
        dps.serie = "1"
        dps.numero_dps = "10"
        dps.data_competencia = datetime.date(2026, 6, 4)
        dps.tipo_emitente = 1
        dps.cod_municipio_emissao = "1600303"

        prest = PrestadorDPS()
        prest.cnpj = "73148327000189"
        prest.inscricao_municipal = "187523"
        prest.opcao_simples_nacional = 3
        prest.regime_especial_tributacao = 0
        prest.nome = "CLINICA TESTE"
        dps.prestador = prest

        toma = TomadorDPS()
        toma.cpf = "86245899249"
        toma.razao_social = "Tomador Teste"
        dps.tomador = toma

        serv = ServicoDPS()
        serv.local_prestacao = ServicoLocalPrestacao()
        serv.local_prestacao.cod_municipio = "1600303"
        serv.codigo = ServicoCodigo()
        serv.codigo.cod_tributacao_nacional = "040101"
        serv.codigo.cod_tributacao_municipal = "040101"
        serv.codigo.descricao_servico = "Consulta Medica"
        dps.servico = serv

        trib_mun = TribMunicipal()
        trib_mun.tributacao_issqn = 1
        trib_mun.tipo_retencao_issqn = 1
        trib_mun.aliquota = Decimal("5.00")
        tributacao = InfoTributacao()
        tributacao.trib_municipal = trib_mun
        tributacao.ind_tot_trib = 0

        valores = ValoresDPS()
        valores.valor_servico = Decimal("155.00")
        valores.tributacao = tributacao
        dps.valores = valores
        dps.incluir_ibscbs = False
        return dps

    def test_c_trib_mun_seis_digitos_sem_c_nbs(self):
        xml = serializar_dps(self._dps_minima())
        self.assertEqual(etree.QName(xml).localname, "DPS")
        serie = xml.find(f".//{{{NS}}}serie")
        self.assertEqual(serie.text, "1")
        n_dps = xml.find(f".//{{{NS}}}nDPS")
        self.assertEqual(n_dps.text, "10")
        c_trib_mun = xml.find(f".//{{{NS}}}cTribMun")
        self.assertIsNotNone(c_trib_mun)
        self.assertEqual(c_trib_mun.text, "401")
        self.assertIsNotNone(xml.find(f".//{{{NS}}}cNBS"))
        x_nome = xml.find(f".//{{{NS}}}prest/{{{NS}}}xNome")
        self.assertIsNone(x_nome)

    def test_c_trib_nac_mantem_seis_digitos(self):
        xml = serializar_dps(self._dps_minima())
        c_trib_nac = xml.find(f".//{{{NS}}}cTribNac")
        self.assertEqual(c_trib_nac.text, "040101")

    def test_trib_elemento_minusculo_no_xml(self):
        xml = serializar_dps(self._dps_minima())
        self.assertIsNone(xml.find(f".//{{{NS}}}Trib"))
        trib = xml.find(f".//{{{NS}}}trib")
        self.assertIsNotNone(trib)

    def test_tomador_endereco_usa_tag_end_minuscula(self):
        dps = self._dps_minima()
        toma = TomadorDPS()
        toma.cpf = "86245899249"
        toma.razao_social = "Tomador Teste"
        toma.cod_municipio = "1600303"
        toma.cep = "68900000"
        toma.logradouro = "Rua A"
        toma.numero = "10"
        toma.bairro = "Centro"
        dps.tomador = toma
        xml = serializar_dps(dps)
        self.assertIsNone(xml.find(f".//{{{NS}}}End"))
        end_el = xml.find(f".//{{{NS}}}toma/{{{NS}}}end")
        self.assertIsNotNone(end_el)
        c_mun = xml.find(f".//{{{NS}}}toma/{{{NS}}}end/{{{NS}}}endNac/{{{NS}}}cMun")
        self.assertEqual(c_mun.text, "1600303")

    def test_ibscbs_sempre_presente(self):
        dps = self._dps_minima()
        dps.incluir_ibscbs = False
        xml = serializar_dps(dps)
        self.assertIsNotNone(xml.find(f".//{{{NS}}}IBSCBS"))

    def test_ibscbs_quando_habilitado(self):
        dps = self._dps_minima()
        dps.incluir_ibscbs = True
        dps.ibscbs_modo = "completo"
        xml = serializar_dps(dps)
        ibscbs = xml.find(f".//{{{NS}}}IBSCBS")
        self.assertIsNotNone(ibscbs)
        c_ind = xml.find(f".//{{{NS}}}IBSCBS/{{{NS}}}cIndOp")
        self.assertEqual(c_ind.text, "010101")
        cst = xml.find(f".//{{{NS}}}IBSCBS/{{{NS}}}valores/{{{NS}}}trib/{{{NS}}}gIBSCBS/{{{NS}}}CST")
        self.assertEqual(cst.text, "000")

    def test_tot_trib_simples_usa_p_tot_trib_sn(self):
        dps = self._dps_minima()
        dps.prestador.opcao_simples_nacional = 3
        dps.prestador.regime_apuracao_simples = 1
        dps.valores.tributacao.ind_tot_trib = None
        dps.valores.tributacao.p_tot_trib_sn = Decimal("6.00")
        xml = serializar_dps(dps)
        self.assertIsNone(xml.find(f".//{{{NS}}}indTotTrib"))
        p_sn = xml.find(f".//{{{NS}}}pTotTribSN")
        self.assertIsNotNone(p_sn)
        self.assertEqual(p_sn.text, "6.00")


if __name__ == "__main__":
    unittest.main()
