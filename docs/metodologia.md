# Metodologia — Projeto de IA (aplicada ao Case Asset Servicing)

> Funil: **dados → regras de negócio → contrato → arquitetura → código → entrega**.
> Cada fase produz **artefatos concretos** e só fecha quando passa no **gate**.
> Na primeira passada as fases são sequenciais; descobertas da Fase 4 podem reabrir as Fases 1–2. Quando isso acontecer, atualize o artefato e registre em `docs/decisoes.md`.

---

## Princípios

1. **Dados antes de design.** O problema real está nos PDFs, não no enunciado. Leia tudo antes de desenhar qualquer coisa.
2. **O LLM extrai, o código decide.** O modelo lê e interpreta. Validação, confiança e roteamento são determinísticos, testáveis e explicáveis.
3. **Sem evidência, sem valor.** Todo campo aponta para a origem (página + trecho literal). Campo ausente é `null` + motivo, nunca um valor plausível.
4. **Confiança se calcula, não se pergunta.** A autoavaliação do LLM é só um sinal. Combine com sinais verificáveis: trecho encontrado no texto, regras aprovadas, match no golden record, qualidade da leitura do PDF.
5. **Medir antes de ajustar.** Sem gabarito e eval, toda mudança de prompt é palpite.
6. **Errar para o lado humano.** Aprovar automaticamente um valor errado custa muito mais do que mandar um valor certo para revisão.
7. **Simples o bastante para estender ao vivo.** Cada abstração precisa se pagar. Se você não consegue explicar uma linha, ela não entra.
8. **Decisão registrada na hora.** Toda escolha relevante vai para `docs/decisoes.md` quando é tomada. O README sai daí.

---

## Fase 0 — Imersão nos dados

**Objetivo:** saber exatamente o que o sistema vai enfrentar. A fase responde a três perguntas; o formato dos artefatos varia de projeto para projeto.

1. **O que o sistema vai enfrentar?** Leia os dados. Um LLM pode acelerar a análise, mas o entendimento precisa ser seu. Para cada documento (ou amostra, se forem muitos), anote: formato, tipo, campos presentes e ausentes, terminologia, problemas (ambiguidade, dado conflitante, mais de um item por documento, divergência com a base de referência).
2. **Qual é a resposta certa para cada entrada?** Monte o **gabarito** antes de qualquer código: valores esperados, quais campos *devem* sair vazios e quais registros *devem* ir para revisão humana (e por quê).
3. **Que linguagem do domínio preciso dominar?** Só o que o domínio exigir: taxonomia (se a tarefa envolve classificar), glossário (se o domínio é técnico), princípios de interpretação derivados dos dados.

**Teste de cada seção:** ela precisa ter um consumidor numa fase seguinte (prompt, schema, regras, eval). Se não alimenta nada, sai.

**Artefatos (neste projeto):** `docs/inventario.md` (registro descritivo do lote; congela após a fase), `docs/dominio.md` (especificação viva: taxonomia, glossário, princípios), `tests/evals/gabarito.csv` e as primeiras entradas de `docs/decisoes.md`.

**Gate:** para cada documento você sabe dizer qual é a saída correta e qual é o principal problema.

---

## Fase 1 — Escopo e regras de negócio

**Objetivo:** fechar o que o sistema entrega, para quem, e o que todo registro precisa cumprir. As regras são comportamento de negócio, não código: escritas no vocabulário de `dominio.md`, elas definem o que o schema da Fase 2 precisa carregar.

1. **Proposta de valor (1 frase).** Se não cabe numa frase, o escopo ainda está aberto.
2. **Usuário e uso.** Quem consome a saída e que pergunta precisa responder olhando só o JSON, sem reabrir o PDF?
3. **In / Out / Deferred.** O que entra nesta entrega, o que fica explicitamente de fora (e por quê), o que fica para depois. É o rascunho da seção de trade-offs do README.
4. **Premissas.** Tudo que o enunciado não diz e você vai assumir. Cada premissa vira uma entrada em `docs/decisoes.md`.
5. **Regras de coerência.** Cada regra com ID, classes a que se aplica, descrição, comportamento (revisão humana / alerta), mensagem descritiva e caso de teste Dado → Então. Parâmetros que dependem do contexto (alíquota vigente, checagens ligadas ou desligadas) ficam em configuração.
6. **Validação contra a base de referência.** Por qual chave cruzar, o que conta como match, o que é divergência e o que acontece em cada caso.
7. **Campos por classe.** Obrigatórios, opcionais e não aplicáveis, para cada tipo de evento.

**Artefatos:** `docs/regras.md` e seção "Escopo" em `docs/decisoes.md`.

**Gate:** toda regra tem caso de teste; aplicadas ao gabarito, as regras com comportamento de revisão humana reproduzem a coluna de revisão humana (ou a diferença está explicada).

---

## Fase 2 — Contrato de saída e incerteza

**Objetivo:** definir, antes do código, o formato da saída e quando um registro não pode seguir sozinho.

1. **Schema de saída.** O JSON por documento e o relatório de exceções. Ele carrega tudo que as regras da Fase 1 precisam avaliar. Para cada campo, no mínimo: valor, status (encontrado / não encontrado / não se aplica / adiado), evidência (página/trecho), confiança + justificativa, resultado da validação, flag de revisão + motivo.
2. **Modelo de confiança.** Quais sinais, como combiná-los, como chegar nos níveis, e qual justificativa legível acompanha cada nível.
3. **Política de roteamento.** Tabela de condições → `auto` ou `revisão humana`, com códigos de motivo: regra de revisão humana, confiança baixa, `INDETERMINADO`. Defina o que roteia o campo e o que roteia o documento inteiro.
4. **Métricas de eval** contra o gabarito:
   - acurácia por campo e do tipo de evento;
   - **valores inventados** (preenchido quando o gabarito é vazio ou `n/a`): meta zero;
   - **erros não roteados** (valor errado que saiu como `auto`): meta zero. É a métrica que mais importa.

**Artefatos:** exemplos JSON preenchidos à mão em `docs/exemplos/` e a tabela de confiança/roteamento em `docs/decisoes.md`.

**Gate:** você preencheu o schema à mão para o documento mais fácil e para o mais difícil do lote; aplicada ao gabarito, a política de roteamento reproduz a coluna de revisão humana; todo motivo de revisão tem uma condição que o dispara; toda métrica tem meta.

---

## Fase 3 — Arquitetura mínima

**Objetivo:** o menor desenho que cumpre as Fases 1–2 e que você consegue defender e estender ao vivo.

1. **Caso de uso → pipeline.** Fluxo principal e alternativos; para cada etapa: entrada, saída, se é LLM ou determinística, quais regras roda, o que pode dar errado e o que acontece quando dá. O caso de uso dá os verbos (etapas, funções, tools); o schema e a taxonomia dão os substantivos.
2. **Quanto de "agente".** A decisão central do case: o que o LLM decide sozinho (quais tools chama, se reextrai depois de uma falha) e o que o código impõe. Registre as alternativas e o porquê.
3. **Desenho das tools.** Para cada uma: nome, propósito, entrada, saída, erros. Pequenas, determinísticas, testáveis isoladamente.
4. **Stack com justificativa.** Provider/modelo, leitura de PDF, OCR ou visão para escaneados, validação de schema, testes. Para cada escolha: por quê, e por que não a alternativa. Menos dependências, menos para defender.
5. **Estrutura de módulos.** Um módulo por estágio. Interface só onde há troca real prevista.

**Artefatos:** diagrama do pipeline (ASCII ou Mermaid) e seção "Arquitetura" em `docs/decisoes.md`.

**Gate:** cada requisito do enunciado aponta para um estágio ou tool, e cada estágio tem seu caminho de falha definido.

---

## Fase 4 — Construção incremental

**Objetivo:** ter algo funcionando ponta a ponta cedo e melhorar guiado por métricas.

Ordem:
1. **Esqueleto ponta a ponta:** 1 documento fácil → JSON válido no schema. Feio, mas completo.
2. **Regras determinísticas com TDD:** traduza os casos de teste de `docs/regras.md` em pytest. Teste falha → implementa → passa.
3. **Lote completo + script de eval:** roda nos 8 documentos, compara com o gabarito, imprime as métricas.
4. **Ciclo de melhoria:** olhe os erros → mude **uma** coisa (prompt, leitura do PDF, regra) → rode o eval → registre. Pare quando as metas forem atingidas ou o gap estiver entendido e documentado.
5. **Calibração de confiança e roteamento:** confira que todo erro restante foi roteado.
6. **Relatório de exceções.**

Práticas:
- Respostas do LLM em cache em disco: iteração barata, execução reproduzível, debug ao vivo sem depender da API.
- Temperatura 0 e versão do modelo fixada.
- Log por documento: texto lido, chamadas ao LLM, tools chamadas, decisão final.

**Gate:** testes verdes e eval nas metas (ou cada falha explicada).

---

## Fase 5 — Entrega e defesa

**Objetivo:** o avaliador roda, entende e confia; você defende e estende ao vivo.

- **README:** como rodar; arquitetura (diagrama); decisões e trade-offs, **incluindo o que decidiu não fazer**; premissas; resultados do eval, honestos; limitações conhecidas.
- **Saídas geradas** commitadas: JSONs + relatório de exceções.
- **Teste do clone limpo:** clonar em outra pasta, seguir o README, rodar.
- **Ensaio da sessão ao vivo (45 min, estender e depurar).** Pratique as mudanças prováveis: novo tipo de evento, nova regra, novo campo, trocar o provider, depurar um documento que falha. Cada uma deve ser uma mudança pequena e localizada; se não for, simplifique o código antes de entregar.
- Liste as 10 perguntas mais difíceis que podem te fazer e responda cada uma em uma frase.

**Gate:** o clone limpo funciona e você explica qualquer linha do repositório.

---

## Timebox

| Fase | Esforço |
|---|---|
| 0 — Imersão | ~10% |
| 1 — Escopo e regras de negócio | ~15% |
| 2 — Contrato e incerteza | ~10% |
| 3 — Arquitetura | ~5% |
| 4 — Construção | ~45% |
| 5 — Entrega e defesa | ~15% |

Se uma fase estourar, reduza a profundidade (e mova o resto para Deferred), mas não pule a fase.

---

## Versionamento

- Um commit por trabalho concluído.
- Mensagem curta, em português: `tipo(escopo): descrição` (`feat`, `fix`, `test`, `docs`, `refactor`, `chore`).
- O histórico conta a evolução do raciocínio: cada artefato fechado é um commit.

---

## Formato de `docs/decisoes.md`

```markdown
### D-03 — <título curto>
- **Contexto:** o problema ou a lacuna.
- **Opções:** A, B, C.
- **Decisão:** o que foi escolhido.
- **Por quê / custo:** o que se ganha e do que se abre mão.
```

---

## Como trabalhamos (você + Claude)

- **Você** é dono de cada artefato e de cada decisão, e escreve o código.
- **Claude** revisa contra o gate, aponta lacunas, desafia decisões, explica conceitos e bibliotecas e, quando você pede, redige rascunhos de documentação (inventário, domínio, regras, decisões, gabarito).
- Tudo que Claude redigir, você lê linha a linha antes do commit: na sessão ao vivo, quem defende é você.
- Ao fim de cada fase: artefato → revisão → você decide o que ajustar → commit → fase fechada.

---

## Visão geral

```
[0 DADOS]       → inventário + domínio + gabarito
[1 REGRAS]      → escopo + premissas + regras de coerência + campos por classe
[2 CONTRATO]    → schema + confiança + roteamento + métricas
[3 ARQUITETURA] → pipeline + tools + stack
[4 CÓDIGO]      → esqueleto → TDD → eval → iteração
[5 ENTREGA]     → README + saídas + ensaio da sessão ao vivo
```
