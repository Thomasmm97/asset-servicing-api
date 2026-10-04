"""Confiança (D-20, R-CNF-01), chaves por classe (D-17) e status calculado (D-21)."""

from asset_servicing.modelos import (Apontamento, CampoExtraido, Leitura, NivelConfianca, Palavra, Status, TipoPdf)
from asset_servicing.montagem import calcular_confianca, registro_de_erro
from asset_servicing.modelos import CodigoErro

EXTRAIDO = CampoExtraido(valor="22/06/2026", trecho="Data-base (data com) 22/06/2026", pagina=1, adiado=False)


def _escaneado(confianca):
    return Leitura(documento="x.pdf", tipo_pdf=TipoPdf.ESCANEADO, texto="22/06/2026",
                   palavras=[Palavra(texto="22/06/2026", pagina=1, inicio=0, fim=10, confianca=confianca)])


def test_ocr_abaixo_do_limite_e_baixa_e_vai_para_revisao():
    confianca, ocorrencias = calcular_confianca("data_com", EXTRAIDO, (0, 10), _escaneado(0.62), ["rótulo do campo na citação"])
    assert confianca.nivel == NivelConfianca.BAIXA and [o.regra for o in ocorrencias] == ["R-CNF-01"]


def test_confirmado_e_alta_sem_confirmacao_e_media():
    assert calcular_confianca("data_com", EXTRAIDO, (0, 10), _escaneado(0.96), ["R-DAT-03"])[0].nivel == NivelConfianca.ALTA
    assert calcular_confianca("data_com", EXTRAIDO, (0, 10), _escaneado(0.96), [])[0].nivel == NivelConfianca.MEDIA


def test_valor_nulo_nao_tem_confianca():
    vazio = CampoExtraido(valor=None, trecho=None, pagina=None, adiado=False)
    assert calcular_confianca("data_com", vazio, None, _escaneado(0.96), []) == (None, [])


def test_status_de_erro_e_registro_sem_campos():
    r = registro_de_erro("x.pdf", "x-1", None, CodigoErro.PDF_ILEGIVEL, "arquivo corrompido")
    assert r.status == Status.ERRO and r.campos is None and "corrompido" in r.erro.mensagem
