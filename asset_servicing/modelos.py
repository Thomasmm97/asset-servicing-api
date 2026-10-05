"""Classes de dados: as internas do pipeline e as do contrato de saída (docs/contrato.md)."""

from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class TipoPdf(str, Enum):
    NATIVO = "NATIVO"
    ESCANEADO = "ESCANEADO"


class Status(str, Enum):
    APROVADO = "APROVADO"
    REVISAO_HUMANA = "REVISAO_HUMANA"
    ERRO = "ERRO"


class TipoEvento(str, Enum):
    DIVIDENDO = "DIVIDENDO"
    JCP = "JCP"
    BONIFICACAO = "BONIFICACAO"
    DESDOBRAMENTO = "DESDOBRAMENTO"
    GRUPAMENTO = "GRUPAMENTO"
    INDETERMINADO = "INDETERMINADO"


class MotivoIndeterminado(str, Enum):
    FORA_DA_TAXONOMIA = "FORA_DA_TAXONOMIA"
    SINAIS_CONFLITANTES = "SINAIS_CONFLITANTES"
    EVIDENCIA_INSUFICIENTE = "EVIDENCIA_INSUFICIENTE"


class NivelConfianca(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAIXA = "BAIXA"


class BaseReferencia(str, Enum):
    CONFERE = "CONFERE"
    DIVERGE = "DIVERGE"
    NAO_ENCONTRADO = "NAO_ENCONTRADO"


class Comportamento(str, Enum):
    REVISAO_HUMANA = "REVISAO_HUMANA"
    ALERTA = "ALERTA"


class CodigoErro(str, Enum):
    FALHA_MODELO = "FALHA_MODELO"
    PDF_ILEGIVEL = "PDF_ILEGIVEL"
    FALHA_OCR = "FALHA_OCR"
    ERRO_INTERNO = "ERRO_INTERNO"


class ErroProcessamento(Exception):
    """Falha que impede processar o documento; vira `status: ERRO` (D-18)."""

    def __init__(self, codigo: CodigoErro, detalhe: str):
        super().__init__(detalhe)
        self.codigo = codigo
        self.detalhe = detalhe


# ---------- Leitura ----------

class Palavra(BaseModel):
    texto: str
    pagina: int
    inicio: int  # posição no texto da leitura
    fim: int
    confianca: float | None  # OCR, 0–1; None em PDF nativo


class Leitura(BaseModel):
    documento: str
    tipo_pdf: TipoPdf
    texto: str
    palavras: list[Palavra]


# ---------- Extração (também é o schema da saída estruturada do modelo) ----------

class Citacao(BaseModel):
    pagina: int
    trecho: str


class CampoExtraido(BaseModel):
    valor: str | None = Field(description="Valor copiado exatamente como está no texto, sem converter formato. null se ausente ou adiado.")
    trecho: str | None = Field(description="A linha da tabela com o rótulo do campo e o valor, copiada literalmente; sem tabela, a menor frase com rótulo e valor.")
    pagina: int | None
    adiado: bool = Field(description="true se o emissor adiou o valor ('a definir'); o trecho mostra o adiamento.")


class Indeterminacao(BaseModel):
    motivo: MotivoIndeterminado
    classes_candidatas: list[TipoEvento]
    justificativa: str


class Classificacao(BaseModel):
    valor: TipoEvento
    sinais: list[Citacao] = Field(description="Trechos literais que mostram a natureza do evento.")
    titulo: str = Field(description="Título do aviso, copiado literalmente.")
    indeterminacao: Indeterminacao | None = Field(description="Só para INDETERMINADO.")


class Extracao(BaseModel):
    tipo_evento: Classificacao
    razao_social: CampoExtraido
    cnpj: CampoExtraido
    isin: CampoExtraido
    ticker: CampoExtraido
    classe: CampoExtraido = Field(description="Valor: ON ou PN (da linha do valor, do sufixo do ticker ou do código de classe do ISIN).")
    data_aprovacao: CampoExtraido
    data_com: CampoExtraido = Field(description="Data com; em grupamento e desdobramento, a data-base.")
    data_ex: CampoExtraido = Field(description="Data ex; em grupamento e desdobramento, início da negociação com a nova quantidade.")
    data_pagamento: CampoExtraido = Field(description="Data de pagamento; em bonificação, data do crédito das ações.")
    valor_bruto: CampoExtraido = Field(description="Valor bruto em dinheiro por ação.")
    aliquota_irrf: CampoExtraido = Field(description="Alíquota de IR retida na fonte que leva do valor bruto ao valor líquido por ação informado no aviso. null se o aviso não informa valor líquido por ação ou se a alíquota é regra geral (ex.: por beneficiário, acima de um limite mensal).")
    valor_liquido: CampoExtraido = Field(description="Valor líquido por ação, depois do IR retido.")
    proporcao: CampoExtraido = Field(description="Valor no formato antes:depois, em inteiros (1 ação nova para cada 20 → 20:21; 10 ações viram 1 → 10:1).")
    custo_atribuido: CampoExtraido = Field(description="Custo atribuído por ação bonificada.")
    moeda: CampoExtraido = Field(description="Valor em ISO 4217 (R$ → BRL); trecho com o símbolo.")


CAMPOS_EXTRAIDOS = [n for n in Extracao.model_fields if n != "tipo_evento"]


# ---------- Validação ----------

class Ocorrencia(BaseModel):
    regra: str
    comportamento: Comportamento
    campos: list[str]
    mensagem: str


class Resultado(BaseModel):
    aprovadas: list[str] = []
    ocorrencias: list[Ocorrencia] = []


@dataclass
class ChamadaFerramenta:
    id: str
    nome: str


@dataclass
class RespostaModelo:
    conteudo: str | None
    chamadas: list[ChamadaFerramenta] = field(default_factory=list)
    cached_tokens: int = 0
    do_cache_local: bool = False


# ---------- Saída (contrato) ----------

class Apontamento(BaseModel):
    regra: str
    mensagem: str


class Confianca(BaseModel):
    nivel: NivelConfianca
    ocr: float | None = Field(ge=0, le=1)
    modelo: float | None  # sempre None: o modelo escolhido não devolve logprobs (D-26)
    justificativa: str


class Campo(BaseModel):
    valor: str | None
    moeda: str | None = None              # só em valores monetários
    citacao: Citacao | None
    confianca: Confianca | None
    base_referencia: BaseReferencia | None = None  # só em emissor e ativo
    motivos: list[Apontamento]
    alertas: list[Apontamento]

    @computed_field
    @property
    def revisao_humana(self) -> bool:
        return bool(self.motivos)


class CampoTipoEvento(BaseModel):
    valor: TipoEvento
    citacoes: list[Citacao]
    confianca: Confianca | None
    motivos: list[Apontamento]
    alertas: list[Apontamento]

    @computed_field
    @property
    def revisao_humana(self) -> bool:
        return bool(self.motivos)


class Emissor(BaseModel):
    razao_social: Campo
    cnpj: Campo


class Ativo(BaseModel):
    isin: Campo
    ticker: Campo
    classe: Campo


class Campos(BaseModel):
    emissor: Emissor
    ativo: Ativo
    data_aprovacao: Campo
    data_com: Campo
    data_ex: Campo
    data_pagamento: Campo | None = None
    data_credito: Campo | None = None
    valor_bruto: Campo | None = None
    aliquota_irrf: Campo | None = None
    valor_liquido: Campo | None = None
    proporcao: Campo | None = None
    custo_atribuido: Campo | None = None

    def todos(self) -> dict[str, Campo]:
        """Campos preenchidos, achatados (emissor e ativo abertos)."""
        planos = {n: getattr(self.emissor, n) for n in Emissor.model_fields}
        planos |= {n: getattr(self.ativo, n) for n in Ativo.model_fields}
        planos |= {n: getattr(self, n) for n in self.model_fields_set if n not in ("emissor", "ativo")}
        return planos


class RegraAprovada(BaseModel):
    regra: str
    descricao: str


class Erro(BaseModel):
    codigo: CodigoErro
    mensagem: str


class Registro(BaseModel):
    documento: str
    trace_id: str
    tipo_pdf: TipoPdf | None
    erro: Erro | None
    regras_aprovadas: list[RegraAprovada]
    tipo_evento: CampoTipoEvento | None
    campos: Campos | None

    @computed_field
    @property
    def status(self) -> Status:
        if self.erro:
            return Status.ERRO
        em_revisao = self.tipo_evento.revisao_humana or any(c.revisao_humana for c in self.campos.todos().values())
        return Status.REVISAO_HUMANA if em_revisao else Status.APROVADO
