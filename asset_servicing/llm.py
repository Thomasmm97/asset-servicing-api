"""Tudo o que fala com o modelo: cliente (cache local, backoff), extração estruturada e agente de validação (D-27, D-28)."""

import hashlib
import json
import os
import threading
import time
from collections import deque

from openai import OpenAI, RateLimitError

from . import config
from .modelos import ChamadaFerramenta, CodigoErro, ErroProcessamento, Extracao, Leitura, RespostaModelo, Resultado
from .regras import FERRAMENTAS
from .saida import registrar

PROMPT_EXTRACAO = """Extraia os campos do aviso de evento corporativo conforme o schema.
- valor: copie exatamente como está no texto, sem converter formato; só proporcao, classe e moeda vêm no formato descrito no schema. Campo ausente: valor, trecho e pagina null.
- trecho: a linha da tabela com o rótulo do campo e o valor, copiada literalmente; sem tabela, a menor frase com rótulo e valor.
- Valor adiado pelo emissor ("a definir"): valor null, adiado true, trecho com o adiamento.
- Extraia os valores por ação que o aviso informar, mesmo que não combinem com o tipo de evento.
Classifique tipo_evento pela natureza (origem, base legal, forma de cálculo, tributação), nunca pelo título:
- DIVIDENDO: lucro ou reservas de lucros distribuídos em dinheiro.
- JCP: remuneração do capital próprio, calculada sobre o patrimônio líquido e limitada à TJLP, com IR retido na fonte.
- BONIFICACAO: ações novas gratuitas por capitalização de reservas, com custo atribuído.
- DESDOBRAMENTO: mais ações, sem mudar o capital. GRUPAMENTO: menos ações.
- INDETERMINADO: fora da taxonomia, sinais conflitantes ou evidência insuficiente; preencha indeterminacao."""

PROMPT_AGENTE = """Valide o registro de evento corporativo chamando as ferramentas de validação aplicáveis.
Os valores já estão carregados nas ferramentas. Ao terminar, responda apenas: concluído."""

ESQUEMAS_FERRAMENTAS = [
    {"type": "function", "function": {"name": nome, "description": descricao, "parameters": {"type": "object", "properties": {}}}}
    for nome, descricao in [
        ("validar_identificacao", "Confere emissor e ativo na base de referência e o formato e a coerência de ISIN, CNPJ, ticker e classe."),
        ("validar_datas", "Confere a ordem das datas, a data ex como pregão seguinte à data com e as datas em dias de pregão da B3."),
        ("validar_valores_e_proporcao", "Confere valores em dinheiro (bruto, líquido, alíquota, moeda) ou a proporção e o custo atribuído, conforme o tipo de evento."),
    ]
]

_cliente: OpenAI | None = None
_trava = threading.Lock()
_chamadas_recentes: deque[float] = deque()


def chamar_modelo(mensagens: list[dict], schema: type[Extracao] | None = None,
                  ferramentas: list[dict] | None = None, usar_cache: bool = True) -> RespostaModelo:
    """Única porta para o provider. Cache local por hash da requisição; até MAX_RETRIES retries com backoff (D-13)."""
    requisicao = {"modelo": config.MODELO, "mensagens": mensagens, "ferramentas": ferramentas,
                  "schema": schema.model_json_schema() if schema else None}
    chave = hashlib.sha256(json.dumps(requisicao, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    arquivo = config.PASTA_CACHE / f"{chave}.json"
    if usar_cache and arquivo.exists():
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        resposta = RespostaModelo(conteudo=dados["conteudo"], cached_tokens=dados["cached_tokens"], do_cache_local=True,
                                  chamadas=[ChamadaFerramenta(**c) for c in dados["chamadas"]])
        registrar("chamada_modelo", cache_local=True, hash=chave[:12])
        return resposta
    erro = None
    for tentativa in range(config.MAX_RETRIES + 1):
        try:
            resposta = _chamar_api(mensagens, schema, ferramentas)
            registrar("chamada_modelo", cache_local=False, hash=chave[:12], tentativa=tentativa,
                      cached_tokens=resposta.cached_tokens)
            if usar_cache:
                _gravar_cache(arquivo, resposta)
            return resposta
        except Exception as e:
            erro = e
            registrar("falha_modelo", tentativa=tentativa, erro=f"{type(e).__name__}: {e}")
            if tentativa < config.MAX_RETRIES:
                time.sleep(max(2 ** tentativa, 60 / config.LIMITE_RPM * 3) if isinstance(e, RateLimitError) else 2 ** tentativa)
    raise ErroProcessamento(CodigoErro.FALHA_MODELO, f"{type(erro).__name__}: {erro}")


def extrair(leitura: Leitura, problemas: list[str] | None = None, usar_cache: bool = True) -> Extracao:
    """Extração e classificação numa única chamada estruturada. `problemas` alimenta o retry de alucinação."""
    usuario = f"Documento: {leitura.documento}\n\n{leitura.texto}"
    if problemas:
        usuario += "\n\nA resposta anterior tinha estes problemas; releia o texto e corrija:\n- " + "\n- ".join(problemas)
    mensagens = [{"role": "system", "content": PROMPT_EXTRACAO}, {"role": "user", "content": usuario}]
    resposta = chamar_modelo(mensagens, schema=Extracao, usar_cache=usar_cache)
    return Extracao.model_validate_json(resposta.conteudo)


def validar(valores: dict[str, object], tipo_evento: str, usar_cache: bool = True) -> list[Resultado]:
    """Agente: o modelo escolhe as ferramentas; o código injeta os valores e chama as que faltarem (D-27)."""
    visiveis = {k: str(v) for k, v in valores.items() if v is not None}
    mensagens = [{"role": "system", "content": PROMPT_AGENTE},
                 {"role": "user", "content": json.dumps({"tipo_evento": tipo_evento, "valores": visiveis}, ensure_ascii=False)}]
    resultados: dict[str, Resultado] = {}
    for _ in range(config.MAX_RODADAS_AGENTE):
        resposta = chamar_modelo(mensagens, ferramentas=ESQUEMAS_FERRAMENTAS, usar_cache=usar_cache)
        if not resposta.chamadas:
            break
        mensagens.append({"role": "assistant", "content": resposta.conteudo, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.nome, "arguments": "{}"}} for c in resposta.chamadas]})
        for chamada in resposta.chamadas:
            funcao = FERRAMENTAS.get(chamada.nome)
            resultado = funcao(valores) if funcao else Resultado()
            if funcao:
                resultados.setdefault(chamada.nome, resultado)
            registrar("ferramenta", nome=chamada.nome, chamada_por="modelo", ocorrencias=len(resultado.ocorrencias))
            mensagens.append({"role": "tool", "tool_call_id": chamada.id, "content": json.dumps(
                {"aprovadas": resultado.aprovadas, "ocorrencias": [o.mensagem for o in resultado.ocorrencias]}, ensure_ascii=False)})
        if resultados.keys() == FERRAMENTAS.keys():  # todas chamadas: outra rodada só traria "concluído"
            break
    for nome, funcao in FERRAMENTAS.items():
        if nome not in resultados:
            resultados[nome] = funcao(valores)
            registrar("ferramenta", nome=nome, chamada_por="código", ocorrencias=len(resultados[nome].ocorrencias))
    return list(resultados.values())


def _respeitar_limite():
    """No máximo LIMITE_RPM chamadas em qualquer janela de 60 s, somando todas as threads."""
    while True:
        with _trava:
            agora = time.monotonic()
            while _chamadas_recentes and agora - _chamadas_recentes[0] >= 60:
                _chamadas_recentes.popleft()
            if len(_chamadas_recentes) < config.LIMITE_RPM:
                _chamadas_recentes.append(agora)
                return
            espera = 60 - (agora - _chamadas_recentes[0]) + 0.05
        time.sleep(espera)


def _chamar_api(mensagens, schema, ferramentas) -> RespostaModelo:
    _respeitar_limite()
    cliente = _obter_cliente()
    if schema:
        r = cliente.chat.completions.parse(model=config.MODELO, messages=mensagens, response_format=schema)
        if r.choices[0].message.parsed is None:
            raise ValueError(r.choices[0].message.refusal or "resposta sem conteúdo estruturado")
    else:
        r = cliente.chat.completions.create(model=config.MODELO, messages=mensagens, tools=ferramentas)
    mensagem = r.choices[0].message
    detalhes = getattr(r.usage, "prompt_tokens_details", None)
    return RespostaModelo(conteudo=mensagem.content,
                          chamadas=[ChamadaFerramenta(id=t.id, nome=t.function.name) for t in (mensagem.tool_calls or [])],
                          cached_tokens=getattr(detalhes, "cached_tokens", 0) or 0)


def _obter_cliente() -> OpenAI:
    global _cliente
    if _cliente is None:
        _cliente = OpenAI(base_url=config.URL_BASE, api_key=_chave_api(), max_retries=0, timeout=120)
    return _cliente


def _chave_api() -> str:
    if chave := os.environ.get(config.VARIAVEL_CHAVE):
        return chave
    env = config.RAIZ / ".env"
    if env.exists():
        for linha in env.read_text(encoding="utf-8").splitlines():
            if linha.startswith(config.VARIAVEL_CHAVE + "="):
                return linha.split("=", 1)[1].strip().strip("\"'")
    return "sem-chave"  # sem chave, só o cache local responde


def _gravar_cache(arquivo, resposta: RespostaModelo):
    """Gravação atômica: várias threads escrevem no cache ao mesmo tempo (D-25)."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(f".{os.getpid()}.{time.time_ns()}.tmp")
    dados = {"conteudo": resposta.conteudo, "cached_tokens": resposta.cached_tokens,
             "chamadas": [{"id": c.id, "nome": c.nome} for c in resposta.chamadas]}
    temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, arquivo)
