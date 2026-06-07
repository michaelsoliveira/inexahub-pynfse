import unittest
from unittest.mock import Mock

from lxml import etree

from pynfe.processamento.comunicacao_nfse_issnet import ComunicacaoISSNetMunicipal
from pynfe.utils.nfse.issnet import format_provider_reference_id, parse_provider_reference_id


class EnvelopeAbrasf204Test(unittest.TestCase):
    def test_envelope_usa_namespace_abrasf204(self):
        from pynfe.processamento.comunicacao_nfse_issnet import serializar_lote
        from pynfe.utils.nfse.issnet import (
            NAMESPACE_SERVICO_ABRASF204,
            detectar_layout_issnet,
            namespace_servico_por_url,
            versao_abrasf_por_url,
        )

        url = "https://nfse.issnetonline.com.br/abrasf204/macapa/nfse.asmx"
        self.assertEqual(detectar_layout_issnet(url), "abrasf204")
        self.assertEqual(namespace_servico_por_url(url), NAMESPACE_SERVICO_ABRASF204)
        self.assertEqual(versao_abrasf_por_url(url), "2.04")

        comm = ComunicacaoISSNetMunicipal.__new__(ComunicacaoISSNetMunicipal)
        comm._namespace_servico = namespace_servico_por_url(url)
        comm._versao_abrasf = versao_abrasf_por_url(url)
        comm._mensagem_cdata = True
        comm.url = url

        lote = serializar_lote([], "1", "86245899249", "187523", versao_abrasf="2.04")
        envelope = comm._construir_envelope("RecepcionarLoteRpsSincrono", lote)

        self.assertIn('xmlns="http://nfse.abrasf.org.br"', envelope)
        self.assertNotIn("issnetonline.com.br/webservices/nfse", envelope)
        self.assertIn("<nfseCabecMsg><![CDATA[", envelope)
        self.assertIn('versao="2.04"', envelope)

        headers = comm._post_header("RecepcionarLoteRpsSincrono")
        self.assertEqual(
            headers["SOAPAction"],
            '"http://nfse.abrasf.org.br/RecepcionarLoteRpsSincrono"',
        )


class SerializarRpsAbrasf204Test(unittest.TestCase):
    def test_lote_rps_tem_wrapper_prestador(self):
        """ABRASF tcLoteRps: CpfCnpj/InscricaoMunicipal devem estar dentro de <Prestador>."""
        from pynfe.processamento.serializacao_nfse_issnet import serializar_lote

        NS = "http://www.abrasf.org.br/nfse.xsd"
        lote_el_raiz = serializar_lote([], "1", "86245899249", "187523", versao_abrasf="2.04")
        lote_el = lote_el_raiz.find("{%s}LoteRps" % NS)

        # CpfCnpj e InscricaoMunicipal devem ser filhos de Prestador, não de LoteRps
        filhos_diretos = [etree.QName(c.tag).localname for c in lote_el]
        self.assertNotIn("CpfCnpj", filhos_diretos)
        self.assertNotIn("InscricaoMunicipal", filhos_diretos)
        self.assertIn("Prestador", filhos_diretos)

        prestador = lote_el.find("{%s}Prestador" % NS)
        self.assertIsNotNone(prestador)
        cpf_cnpj = prestador.find("{%s}CpfCnpj" % NS)
        self.assertIsNotNone(cpf_cnpj)
        im = prestador.find("{%s}InscricaoMunicipal" % NS)
        self.assertIsNotNone(im)
        self.assertEqual(im.text, "187523")

    def test_assinatura_lote_fora_de_lote_rps(self):
        from pynfe.processamento.serializacao_nfse_issnet import (
            empacotar_lote_assinado,
            serializar_lote,
        )

        lote = serializar_lote([], "1", "86245899249", "187523", versao_abrasf="2.04")
        lote_el = lote.find(".//{http://www.abrasf.org.br/nfse.xsd}LoteRps")
        sig = etree.Element("{%s}Signature" % "http://www.w3.org/2000/09/xmldsig#")
        lote_el.append(sig)
        packed = empacotar_lote_assinado(lote)
        for child in lote_el:
            self.assertNotEqual(etree.QName(child.tag).localname, "Signature")
        sig_el = packed.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature")
        self.assertIsNotNone(sig_el)
        self.assertEqual(sig_el.getparent(), packed)

    def test_assinatura_fora_de_inf_declaracao(self):
        from pynfe.processamento.serializacao_nfse_issnet import (
            empacotar_rps_assinado,
            serializar_rps,
        )

        inf = serializar_rps(
            {"numero": "1", "serie": "3", "data_emissao": "2026-06-06", "competencia": "2026-06-06",
             "item_lista_servico": "04.01", "discriminacao": "Teste", "cod_municipio": "1600303",
             "valor_servicos": "10", "prest_cnpj_cpf": "86245899249", "prest_im": "187523"},
            versao_abrasf="2.04",
        )
        sig = etree.Element("{%s}Signature" % "http://www.w3.org/2000/09/xmldsig#")
        inf.append(sig)
        packed = empacotar_rps_assinado(inf)
        inf_el = packed.find(".//{http://www.abrasf.org.br/nfse.xsd}InfDeclaracaoPrestacaoServico")
        self.assertIsNotNone(inf_el)
        for child in inf_el:
            self.assertNotEqual(etree.QName(child.tag).localname, "Signature")
        sig_el = packed.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature")
        self.assertIsNotNone(sig_el)
        self.assertEqual(sig_el.getparent(), packed)

    def test_layout_v204_nota_control(self):
        from pynfe.processamento.comunicacao_nfse_issnet import serializar_rps

        xml = etree.tostring(
            serializar_rps(
                {
                    "numero": "4",
                    "serie": "3",
                    "data_emissao": "2026-06-05",
                    "competencia": "2026-06-05",
                    "simples": 2,
                    "incentivo": 2,
                    "item_lista_servico": "04.01",
                    "cod_cnae": "8630501",
                    "cod_tributacao_mun": "0401",
                    "discriminacao": "Consulta",
                    "cod_municipio": "1600303",
                    "iss_retido": 2,
                    "valor_servico": "23.00",
                    "aliquota": "0.05",
                    "prest_cnpj_cpf": "86245899249",
                    "prest_im": "187523",
                    "toma_cnpj_cpf": "74794485204",
                    "toma_razao_social": "Paciente Teste",
                    "toma_endereco": "Rua A",
                    "toma_numero": "1",
                    "toma_bairro": "Centro",
                    "toma_cod_municipio": "1600303",
                    "toma_uf": "AP",
                    "toma_cep": "68900000",
                },
                versao_abrasf="2.04",
            ),
            encoding="unicode",
        )

        self.assertIn("<TomadorServico>", xml)
        self.assertIn("<IncentivoFiscal>2</IncentivoFiscal>", xml)
        self.assertIn("<OptanteSimplesNacional>2</OptanteSimplesNacional>", xml)
        self.assertIn("<CodigoCnae>8630501</CodigoCnae>", xml)
        self.assertIn("<CodigoTributacaoMunicipio>0401</CodigoTributacaoMunicipio>", xml)
        self.assertIn("<Aliquota>0.0500</Aliquota>", xml)
        self.assertNotIn("<NaturezaOperacao>", xml)
        self.assertNotIn("<IncentivadorCultural>", xml)
        self.assertNotIn("<Tomador>", xml)
        # ABRASF tcValoresDeclaracaoServico xs:sequence: ValorIss deve preceder Aliquota
        pos_iss = xml.index("<ValorIss>")
        pos_aliq = xml.index("<Aliquota>")
        self.assertLess(pos_iss, pos_aliq, "ValorIss deve aparecer antes de Aliquota")

    def test_tomador_sem_endereco_emite_placeholder(self):
        """ABRASF tcDadosTomador: Endereco é Choice 1-1; deve ser emitido mesmo sem dados."""
        from pynfe.processamento.comunicacao_nfse_issnet import serializar_rps

        xml = etree.tostring(
            serializar_rps(
                {
                    "numero": "5",
                    "serie": "3",
                    "data_emissao": "2026-06-06",
                    "competencia": "2026-06-06",
                    "simples": 2,
                    "incentivo": 2,
                    "item_lista_servico": "04.01",
                    "discriminacao": "Consulta medica",
                    "cod_municipio": "1600303",
                    "iss_retido": 2,
                    "valor_servico": "22.00",
                    "aliquota": "0.05",
                    "prest_cnpj_cpf": "86245899249",
                    "prest_im": "187523",
                    "toma_cnpj_cpf": "74794485204",
                    "toma_razao_social": "Paciente Teste 1",
                    "toma_cod_municipio": "1600303",
                    "toma_uf": "AP",
                    # toma_endereco ausente — caso clínico sem endereço de paciente
                },
                versao_abrasf="2.04",
            ),
            encoding="unicode",
        )

        self.assertIn("<TomadorServico>", xml)
        self.assertIn("<Endereco>", xml)
        self.assertIn("NAO INFORMADO", xml)
        self.assertIn("<Cep>00000000</Cep>", xml)
        self.assertIn("<Uf>AP</Uf>", xml)


class ExtrairRespostaIssnetTest(unittest.TestCase):
    def test_http_nao_200_preenche_erros(self):
        resp = Mock()
        resp.status_code = 403
        resp.headers = {"cf-mitigated": "challenge"}
        resp.text = "<html><title>Just a moment... | Cloudflare</title></html>"
        resp.content = resp.text.encode("utf-8")

        resultado = ComunicacaoISSNetMunicipal.extrair_resposta(resp)

        self.assertEqual(resultado["status"], 403)
        self.assertIsNone(resultado["nfse_xml"])
        self.assertTrue(resultado["erros"])
        self.assertEqual(resultado["erros"][0]["codigo"], "HTTP_403")
        self.assertIn("Cloudflare", resultado["erros"][0]["mensagem"])

    def test_lista_vazia_de_erros_e_falsy(self):
        """Garante que erros=[] não passa silenciosamente em if resultado.get('erros')."""
        resp = Mock()
        resp.status_code = 502
        resp.headers = {}
        resp.text = "Bad Gateway"
        resp.content = resp.text.encode("utf-8")

        resultado = ComunicacaoISSNetMunicipal.extrair_resposta(resp)
        self.assertTrue(bool(resultado.get("erros")))

    def test_http500_inclui_corpo_bruto(self):
        soap_fault_body = (
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<s:Body><s:Fault>"
            "<faultcode>s:Client</faultcode>"
            "<faultstring>Error</faultstring>"
            "</s:Fault></s:Body></s:Envelope>"
        )
        resp = Mock()
        resp.status_code = 500
        resp.headers = {}
        resp.text = soap_fault_body
        resp.content = soap_fault_body.encode("utf-8")

        resultado = ComunicacaoISSNetMunicipal.extrair_resposta(resp)

        self.assertEqual(resultado["erros"][0]["codigo"], "HTTP_500")
        self.assertIn("raw=", resultado["erros"][0]["mensagem"])
        self.assertIn("faultstring=Error", resultado["erros"][0]["mensagem"])
        self.assertEqual(resultado["erros"][0].get("raw_response"), soap_fault_body)

    def test_soap_fault_http200_detectado(self):
        """SOAP Fault genérico em HTTP 200 deve ser reportado como erro SOAP_FAULT."""
        soap_fault_body = (
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<s:Body><s:Fault>"
            "<faultcode>s:Client</faultcode>"
            "<faultstring>Error</faultstring>"
            "</s:Fault></s:Body></s:Envelope>"
        )
        resp = Mock()
        resp.status_code = 200
        resp.headers = {}
        resp.text = soap_fault_body
        resp.content = soap_fault_body.encode("utf-8")

        resultado = ComunicacaoISSNetMunicipal.extrair_resposta(resp)

        self.assertIsNone(resultado["nfse_xml"])
        self.assertTrue(bool(resultado["erros"]))
        self.assertEqual(resultado["erros"][0]["codigo"], "SOAP_FAULT")
        self.assertIn("Fault genérico", resultado["erros"][0]["mensagem"])

    def test_soap_fault_mensagem_especifica_preservada(self):
        """Faultstring com texto real deve ser preservado sem substituição."""
        soap_fault_body = (
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<s:Body><s:Fault>"
            "<faultcode>s:Client</faultcode>"
            "<faultstring>CPF do prestador não cadastrado</faultstring>"
            "</s:Fault></s:Body></s:Envelope>"
        )
        resp = Mock()
        resp.status_code = 200
        resp.headers = {}
        resp.text = soap_fault_body
        resp.content = soap_fault_body.encode("utf-8")

        resultado = ComunicacaoISSNetMunicipal.extrair_resposta(resp)

        self.assertEqual(resultado["erros"][0]["codigo"], "SOAP_FAULT")
        self.assertIn("CPF do prestador", resultado["erros"][0]["mensagem"])


class Abrasf204HelpersTest(unittest.TestCase):
    def test_codigo_tributacao_deriva_item_lc116(self):
        from pynfe.utils.nfse.issnet.abrasf204 import codigo_tributacao_municipio

        self.assertEqual(codigo_tributacao_municipio("04.01", cnae="8630501"), "0401")
        self.assertEqual(
            codigo_tributacao_municipio("04.01", cnae="8630501", config_val="1234"),
            "1234",
        )

    def test_aliquota_xml_valor_fracao(self):
        from pynfe.utils.nfse.issnet.abrasf204 import aliquota_xml_valor

        self.assertEqual(aliquota_xml_valor(0.05, abrasf204=True), 0.05)
        self.assertEqual(aliquota_xml_valor(5.0, abrasf204=True), 0.05)


class ContextoRpsContribuinteTest(unittest.TestCase):
    def test_serie_macapa_producao(self):
        from pynfe.utils.nfse.issnet.abrasf204 import ContextoRpsContribuinte

        ctx = ContextoRpsContribuinte.resolver(
            "1600303",
            homologacao=False,
            serie_rps="70002",
            proximo_numero_rps="125",
        )
        self.assertEqual(ctx.serie_rps, "3")
        self.assertEqual(ctx.numero_rps, "125")
        self.assertTrue(ctx.abrasf204)
        self.assertIn("abrasf204/macapa", ctx.ws_url)

    def test_serie_macapa_homologacao(self):
        from pynfe.utils.nfse.issnet.abrasf204 import ContextoRpsContribuinte

        ctx = ContextoRpsContribuinte.resolver("1600303", homologacao=True)
        self.assertEqual(ctx.serie_rps, "8")
        # ISSNet ABRASF 2.04 (Nota Control) não possui endpoint de homologação
        # público separado — ibge_homologacao aponta para o próprio município.
        self.assertEqual(ctx.ibge_prestacao, "1600303")


class ProviderReferenceIdIssnetTest(unittest.TestCase):
    def test_serie_rps_sem_prefixo_duplicado(self):
        ref = format_provider_reference_id("RPS", "18")
        self.assertEqual(ref, "RPS:000000000000018")
        self.assertNotIn("RPSRPS", ref)

    def test_parse_novo_formato(self):
        serie, numero = parse_provider_reference_id("RPS:000000000000018")
        self.assertEqual(serie, "RPS")
        self.assertEqual(numero, "18")

    def test_parse_legado_rps_prefix(self):
        serie, numero = parse_provider_reference_id("RPSA000000000000018")
        self.assertEqual(serie, "A")
        self.assertEqual(numero, "18")


if __name__ == "__main__":
    unittest.main()
