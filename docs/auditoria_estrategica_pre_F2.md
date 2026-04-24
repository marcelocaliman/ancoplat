# Auditoria Estratégica Pré-Fase 2

Data: 2026-04-24
Auditor: Claude Code (sessão F1b)
Escopo: documentação + código produzidos em F0, F1a, F1b
Regra de ouro: **nenhum `.py` foi modificado nesta auditoria.** Este documento é o único artefato.

---

## Seção A — Sumário executivo

1. **Coerência interna**: ⚠️ PARCIAL — CLAUDE.md está **desatualizado** (afirma que F1a é "próximo passo"); Documento A v2.2 não reflete os 2 desvios metodológicos de F1b nem a redefinição de BC-04/BC-09.
2. **Cobertura de decisões**: ⚠️ PARCIAL — dois desvios metodológicos (catenária generalizada + brentq elástico) estão em docstrings de módulos, mas **fora** do CLAUDE.md que é o primeiro ponto de leitura de uma nova sessão. Pendência R5Studless continua rastreável.
3. **Completude do briefing**: ❌ PRECISA ATENÇÃO — Seção 7.2 (endpoints API) não tem schemas de request/response, códigos de erro, nem versão. Modelo de dados da API (além de `line_types`) não está desenhado. Estas lacunas bloqueiam abertura da F2.
4. **Preparação para escala**: ⚠️ PARCIAL — solver tem `List[LineSegment]` mas rejeita `len>1`; arquitetura permite extensão. Banco SQLite só tem 1 tabela (`line_types`); faltam `cases`, `executions`, `configs` para persistência. Campo `category` e `endpointGrounded` do MVP v2 ausentes nos schemas.
5. **Dívida técnica**: ⚠️ PARCIAL — sem TODOs no código (limpo), mas há 3 campos mortos (`SeabedConfig.depth`, `SolverConfig.max_bisection_iter`, param `w` em `find_touchdown`), um bug de reporting (`iters_est` sempre 1), e um import local (`import math` dentro de função em solver.py).
6. **Riscos de continuidade**: ⚠️ PARCIAL — se Marcelo pausar 3 meses, o CLAUDE.md desatualizado induz próxima sessão a refazer F1a. Desvios metodológicos estão encapsulados em docstrings mas não aparecem no ponto de entrada da documentação.

**Veredicto geral**: Nada BLOQUEANTE. A F2 pode começar, mas 4 ações ALTAS devem entrar antes para evitar retrabalho e confusão.

---

## Seção B — Achados detalhados

### 1. Coerência interna entre documentos

**O que está bem**
- Decisões fechadas da F1a (qmoor_ea default, R5Studless preservado, legacy_id, conversão SI na seed) estão corretamente registradas no CLAUDE.md e no script `seed_catalog.py`.
- Relatório F1b ([docs/relatorio_F1b.md](docs/relatorio_F1b.md)) documenta os dois desvios metodológicos da F1b na Seção 5 ("Decisões de implementação que merecem atenção").

**O que pode melhorar**
- [CLAUDE.md:17-25](CLAUDE.md#L17-L25) — seção "Estado atual" diz:
  ```
  ✅ F0 — Setup do ambiente (concluído)
  ⏳ F1a — Importação do catálogo QMoor para SQLite (próximo passo)
  ⬜ F1b — Implementação do solver
  ```
  Na realidade F1a e F1b **estão concluídas**. Quem retomar a sessão vai partir do pressuposto errado de que ainda tem um mês de trabalho pela frente.

**O que está ausente**
- Documento A v2.2, Seção 3.3.1, apresenta a formulação "âncora no vértice" como se fosse suficiente — mas BC-01 (T_fl=785 kN) **exige** V_anchor > 0, i.e., formulação geral. Isso foi descoberto em F1b mas não voltou ao Documento A. Outra Claude lendo apenas o Documento A vai implementar a forma simplificada e falhar no BC-01.
- Documento A v2.2, Seção 6.1.2, especifica BC-04 como "Elástico com touchdown" com T_fl=150 t. Em F1b descobrimos que **esse caso é fully suspended** (T_fl > T_fl_crit para aquela geometria). O rótulo "com touchdown" do BC-04 está errado. BC-05 (Range com X=1450) é também fully suspended. O relatório F1b menciona; o Documento A ainda não foi atualizado.
- Documento A v2.2, Seção 6.1.1 e 6.2, usa BC-01 e BC-09 com a mesma geometria do BC-04 (h=1000, L=1800). Em F1b tivemos que redefinir BC-09 com outra geometria (h=300, L=700, T_fl=150 kN) para ter touchdown real com μ=0. Documento A não foi sincronizado.
- Documento A v2.2, Seção 3.5.1, menciona "Fallback: bisseção pura se Brent não convergir em 50 iterações". No código atual **não há fallback de bisseção implementado** — usa-se brentq (que já é método híbrido) exclusivamente. `SolverConfig.max_bisection_iter=200` é declarado mas não lido. O Documento A promete algo que o código não entrega.

### 2. Cobertura de decisões tomadas

**O que está bem**
- **Pendência R5Studless** (μ=0,6 vs μ=1,0 das demais chains) está **triplamente rastreável**: CLAUDE.md seção "Atrito de seabed", docstring de [backend/data/seed_catalog.py:13-19](backend/data/seed_catalog.py#L13-L19), e detecção automática em runtime com warning. ✅
- Decisões fechadas de F1a (EA, id, unidades) em CLAUDE.md. ✅
- Desvios F1b documentados em docstrings de módulos: [backend/solver/catenary.py:1-33](backend/solver/catenary.py#L1-L33) (catenária generalizada), [backend/solver/elastic.py:17-19](backend/solver/elastic.py#L17-L19) (brentq no elástico). ✅

**O que pode melhorar**
- Os dois desvios metodológicos de F1b **não aparecem no CLAUDE.md**, que é o primeiro arquivo que qualquer Claude Code novo lê para obter contexto. Estão enterrados em docstrings de módulos que podem não ser lidos até o momento de editar aquele arquivo específico. Isso é a pior forma de perda de contexto — a informação existe mas não está onde seria encontrada.
- Decisões de redefinição de BC-02, BC-07, BC-08, BC-09 estão no [relatorio_F1b.md](docs/relatorio_F1b.md) e nos docstrings dos testes, mas **não no CLAUDE.md** nem no Documento A. Se alguém for revisar os BCs no futuro, vai comparar com a Seção 6.1 do Documento A e ficar confuso.

**O que está ausente**
- Classificação de utilização (Seção 5 do Documento A: alerta amarelo T/MBL ≥ 0,50, vermelho ≥ 0,60) **não é computada** no `SolverResult`. O campo `utilization` existe, mas não há `alert_level` ou similar que a UI possa consumir direto. Decisão implícita: "a UI que compute o alerta". Não registrada em lugar algum.
- O disclaimer obrigatório da Seção 10 do Documento A ("Os resultados apresentados são estimativas…") não tem lugar reservado no `SolverResult` nem no plano F2. Decisão implícita: "a UI injeta como texto fixo". Não registrada.
- Decisão implícita: **âncora sempre no seabed**. `SeabedConfig.depth` existe mas não é usado; fairlead está implicitamente à profundidade 0 (superfície). MVP v2 PDF Seção 5.1 tem `startpointDepth` e `endpointGrounded` como campos obrigatórios — nosso solver ignora ambos. Isso não é um bug, mas é uma **premissa implícita que restringe casos de uso** e não está documentada.

### 3. Completude do briefing técnico

**O que está bem**
- Seções 3 (solver), 4 (catálogo), 5 (utilização) do Documento A estão detalhadas e permitiram a F1b com precisão.
- A Seção 6 (saídas obrigatórias) do MVP v2 PDF serviu como contrato de SolverResult. ✅

**O que pode melhorar**
- **Seção 7.2 (Endpoints API) do Documento A** lista rotas com método e função, mas **não** especifica:
  - Formato de request/response (JSON schema ou exemplos)
  - Códigos HTTP esperados (200, 400, 422, 500)
  - Códigos de erro application-level
  - Autenticação (pessoal/local = sem auth? cookies? token?)
  - Versionamento (`/api/v1/…`?)
  - CORS (Vite/React roda em porta diferente do FastAPI por padrão)
  - Paginação em `GET /api/cases` (se lista ficar grande)
  - Rate limiting (uso pessoal = irrelevante, mas explicitar)
  - Limite de tamanho de payload (.moor importado pode ser grande?)

  Para abrir F2 com segurança, precisamos responder pelo menos: formato do request/response de `/api/cases/{id}/solve`, `/api/import`, `/api/line-types`.

- **Seção 7.1 (Componentes)** diz "Backend API (FastAPI): endpoints REST para CRUD de casos…" mas **não define o modelo persistido** de caso. O que um "caso" é na prática? Apenas o input do usuário? Também armazena o SolverResult? Cached? TTL? Schema SQL?

**O que está ausente**
- **Schema SQL completo** para além de `line_types`. Seção 5 do MVP v2 PDF desenha o payload `.moor`, mas nada diz como persisti-lo no SQLite: `cases(id, name, json_blob, created_at)`? Normalizado em várias tabelas? Histórico de execuções separado?
- **Contrato do formato `.moor`** (import/export). Temos um exemplo em JSON na Seção 5.2 do MVP v2 PDF, mas não um schema formal (Pydantic) equivalente. Seção 9.3 diz "Exportar em .moor" — o solver produz dicionário em quê? O QMoor original tinha um formato específico que não foi replicado em lugar algum.
- **Critérios de utilização configuráveis** (Seção 5 do Documento A define 4 perfis: MVP/Preliminary, API RP 2SK-like, DNV-like, User-defined). Nenhum desses perfis está implementado ou mesmo esboçado no código ou nos schemas. F2 precisa decidir onde eles moram (tabela SQL? arquivos de config? hard-coded?).
- **Disclaimer obrigatório** (Seção 10). Nenhum código/schema reserva espaço para ele. Quem acrescenta? API? Frontend?
- **Estrutura do relatório PDF** (Seção 9.3 do Documento A: "Exportar PDF do relatório simples"). Sem schema, sem biblioteca escolhida (reportlab? weasyprint?), sem template.

### 4. Preparação para escala futura

**O que está bem**
- `solver.solve()` aceita `Sequence[LineSegment]` — assinatura multi-segmento **pronta**, só rejeita `len > 1` com `NotImplementedError` claro. ✅ Evolução v2.1 sem mudar interface pública.
- Separação de módulos por responsabilidade (catenary, seabed, friction, elastic, solver) facilita adicionar novas físicas sem impactar as existentes. ✅
- `SolverResult` tem todos os campos da Seção 6 do MVP v2; adicionar campos no futuro é retrocompatível (Pydantic default). ✅

**O que pode melhorar**
- O código do solver **nunca foi testado** com `len(line_segments) > 1`. Mesmo que a assinatura permita, a função interna assume homogeneidade. Adicionar um teste *smoke* que confirme `NotImplementedError` quando `len>1` documentaria a fronteira de escopo.
- O modelo `LineSegment` **não tem campo `category`** (Wire / StuddedChain / Polyester). Seção 5.1 do MVP v2 PDF trata `category` como obrigatório (decisão do revisor também: atrito depende do tipo). Adicionar agora (opcional, default "Wire"?) evita migração quebrada depois.

**O que está ausente**
- **Banco SQLite vazio além de `line_types`.** Nenhuma tabela para casos salvos, execuções, configurações. Tudo que a Seção 4.4 (Persistência e auditoria) do MVP v2 pede precisa ser desenhado na F2 sem base prévia. Risco: F2 improvisa um schema "provisório" que depois é difícil migrar.
- **Representação futura de multi-linha (spread mooring)**: o revisor (resposta P-17) recomenda deixar a arquitetura preparada para `Line, Segment, Connection, Seabed, BoundaryCondition, Result` de forma extensível. Hoje temos `LineSegment` e `BoundaryConditions` como classes, mas `Line`, `Connection`, `Body` (plataforma) não existem. Quando v2 chegar e multi-linha for necessário, será refactor grande.
- **Batimetria variável** (Seção 9 do Documento A, escopo v2): `SeabedConfig` só tem `μ` e um campo `depth` morto. Nenhum gancho para perfil de profundidade `z(x)`.
- **Categoria de caso** (intacto vs danificado — Seção 5): nenhum schema tem essa dimensão.

### 5. Dívida técnica e pendências

**O que está bem**
- **Zero TODOs/FIXMEs/HACKs** no código produtivo. Grep confirma. Limpeza exemplar.
- Testes passando 100% (45/45), cobertura 96%. ✅
- Seed script tem cabeçalho `PENDÊNCIAS DE VALIDAÇÃO` formal para R5Studless. ✅

**Dívida identificada (nenhuma BLOQUEANTE)**

| ID | Arquivo | Linhas | Natureza |
|----|---------|--------|----------|
| DT-01 | [backend/solver/types.py:100-102](backend/solver/types.py#L100-L102) | `SeabedConfig.depth` declarado mas **nunca lido** em lugar algum do código. Campo morto. |
| DT-02 | [backend/solver/types.py:121](backend/solver/types.py#L121) | `SolverConfig.max_bisection_iter=200` declarado. Documento A promete fallback de bisseção, **código não tem fallback**. Campo morto + promessa quebrada. |
| DT-03 | [backend/solver/seabed.py:43-54](backend/solver/seabed.py#L43-L54) | `find_touchdown(a, w, h)` aceita `w` mas o descarta com `del w`. Parâmetro cosmético que confunde o leitor. |
| DT-04 | [backend/solver/elastic.py:35](backend/solver/elastic.py#L35) | `from typing import Callable` import nunca usado. |
| DT-05 | [backend/solver/elastic.py:187](backend/solver/elastic.py#L187) | `iters_est = 1 # pelo menos uma avaliação` — contador **sempre** reporta 1 iteração, mesmo quando brentq usa 20+. `SolverResult.iterations_used` é diagnóstico incorreto. |
| DT-06 | [backend/solver/solver.py:127](backend/solver/solver.py#L127) | `import math` **dentro** da função `solve()`. Convenção Python pede imports no topo do módulo. |
| DT-07 | [backend/solver/friction.py:38-90](backend/solver/friction.py#L38-L90) | `apply_seabed_friction()` retorna `SeabedFrictionProfile` detalhado (incluindo `s_slack`), mas **nenhum outro código consome isso** — só testes unitários. Não é bug, é função exposta mas sem integração com o SolverResult (que expõe apenas `tension_magnitude` concatenado). |
| DT-08 | [backend/solver/tests/test_camada2_seabed.py](backend/solver/tests/test_camada2_seabed.py) | Caso patológico "L - X > h" (linha com slack no seabed, revisor P-02 cita como patológico) é **rejeitado** pelo solver com ValueError convertido a INVALID_CASE. Não é bug, mas a decisão de não tratar esse caso **não está documentada** em nenhum lugar além do comentário em `_touchdown_range_mode`. |

**Pendências adiadas que precisam ser fechadas**

- **P-13, P-14, P-15 do Documento B** (revisor): sugeriram "MoorPy como referência aberta" + "validação marco" — feito. Porém, o revisor **não rodou** MoorPy nem OrcaFlex. Nossa validação é 100% MoorPy-self-vs-self (usa-se MoorPy como verdade de referência). Não é validação por terceira ferramenta. Considerar se isso é suficiente para a natureza pessoal do uso, ou se um dia queremos OrcaFlex/Ariane/Mimosa para fechamento.
- **BC-10 (multi-segmento)**: adiado para v2.1, consistente. Nada a fazer.
- **Decisões BC-02/07/08/09 redefinidos** (F1b): relatório F1b recomendou "validar com o engenheiro revisor quando possível". Pendência externa.

**Suposições implícitas no código não validadas**

- **Âncora no seabed (startpoint_depth=0 implícito)**: nenhum teste ou doc valida o caso da âncora elevada do fundo (trampolim, etc.). MVP v2 PDF tem `startpointDepth` e `endpointGrounded` como obrigatórios. Nosso código ignora. Se um dia alguém exportar `.moor` de uma config diferente, vai quebrar silenciosamente.
- **Linha homogênea** (um `LineSegment`): fronteira clara (rejeita `len>1`), ok.
- **Solver 2D puro**: sem ganchos para corrente/onda/3D. Consistente com escopo, mas o cabeçalho de `catenary.py` diz "2D no plano vertical contendo fairlead e âncora" — não fala do caso 3D. Não é dívida, é escopo.

### 6. Riscos de continuidade

**Cenário "Marcelo pausa 3 meses e volta"**

- O único "ponto de entrada" documentado é o CLAUDE.md. **Está desatualizado** (vide Achado 1). Risco ALTO de começar a F1a novamente achando que não foi feita.
- Desvios metodológicos de F1b (catenária geral + brentq) estão em docstrings de módulos. Marcelo provavelmente leria o CLAUDE.md primeiro, não os docstrings. Risco MÉDIO de re-questionar decisões já tomadas.
- Relatório [docs/relatorio_F1b.md](docs/relatorio_F1b.md) existe e é excelente — mas **não é linkado** do CLAUDE.md nem do README.md. Quem não souber da existência não vai achar.
- README.md diz "🚧 Em desenvolvimento — Fase 1: solver isolado" — desatualizado também (solver está pronto).

**Cenário "outro dev assume"**

- Documento A v2.2 é auto-suficiente para entender **domínio**.
- Documento B com respostas do revisor é excelente para entender **premissas físicas** (μ por solo, propriedades típicas, etc.).
- Relatório F1b é suficiente para entender **estado do solver** e **validações MoorPy**.
- **Porém**: três "mapas" independentes que não se referenciam diretamente. Um índice mestre no README.md ou no CLAUDE.md apontando para cada documento, com uma linha dizendo "leia este quando precisar saber X", economiza tempo significativo.

**Risco de dívida F2→F3**

- F2 pode começar e criar tabelas SQL provisórias (`cases` com json_blob inteiro, sem schema normalizado). Quando F3 (frontend) tentar consumir, vai ter dificuldade. Previsível. Mitigável com ação A4 abaixo.

---

## Seção C — Lista de ações recomendadas, priorizadas

| ID | Ação | Justificativa | Prioridade | Esforço | Tipo |
|----|------|---------------|:----------:|:-------:|------|
| **A1** | Atualizar seção "Estado atual" do CLAUDE.md para refletir F1a e F1b como ✅ concluídas, e F2 como ⏳ próximo passo. Adicionar mini-índice linkando `docs/relatorio_F1b.md` e o `Documento_B_…docx` do revisor. | Ponto de entrada desatualizado é o maior risco de retrabalho e confusão. | **ALTA** | TRIVIAL | documentação |
| **A2** | Adicionar seção "Decisões de implementação — Fase 1b" no CLAUDE.md registrando: (a) catenária na forma geral (anchor pode ter V>0), (b) brentq no loop elástico (não ponto-fixo), (c) redefinição de BC-02/07/08/09 por falta de geometria de touchdown nos parâmetros originais, (d) `max_bisection_iter` do Documento A não é usado (brentq já é híbrido). | Sem isso, próxima sessão vai reabrir decisões já fechadas e possivelmente desfazer um refactor robusto. | **ALTA** | PEQUENO | documentação |
| **A3** | Atualizar README.md: mover "em desenvolvimento Fase 1" para "✅ F1 completa, F2 em planejamento". Adicionar links para `docs/Documento_A_…docx`, `docs/relatorio_F1b.md`, e `CLAUDE.md`. | README é o rosto externo do repo. | **MÉDIA** | TRIVIAL | documentação |
| **A4** | Antes de escrever código na F2, criar `docs/plano_F2_api.md` com: (a) schema SQL completo (`cases`, `executions`, configs, além de `line_types`); (b) contrato de request/response JSON para cada endpoint da Seção 7.2 do Documento A; (c) códigos HTTP e erros application-level; (d) decisão sobre autenticação, CORS, versionamento; (e) biblioteca PDF escolhida (reportlab/weasyprint/outra). | Seção 7.2 do Documento A é lista de rotas sem detalhes; pular este passo gera schema improvisado que vira débito técnico estrutural. | **ALTA** | MÉDIO | documentação |
| **A5** | Adicionar campo `alert_level: Literal["ok", "yellow", "red", "broken"]` ao `SolverResult` ou `utilization_bucket`, computado dentro do solver conforme thresholds da Seção 5 do Documento A (0.50, 0.60, 1.00). Só depois disso, que F2 expõe corretamente. | Decisão implícita "UI computa alerta" nunca registrada; precisa virar explícita antes da UI. | **MÉDIA** | PEQUENO | refatoração |
| **A6** | Adicionar ao `LineSegment` o campo opcional `category: Literal["Wire","StuddedChain","StudlessChain","Polyester"] \| None` refletindo Seção 5.1 do MVP v2 e Seção 4.2 do Documento A. Default `None` (retrocompatível). | Ausência força F2 a manter acoplamento externo (endpoint recebe category separado do segmento). Melhor consertar fonte. | **MÉDIA** | PEQUENO | refatoração |
| **A7** | Remover ou documentar `SeabedConfig.depth` (campo morto) e `SolverConfig.max_bisection_iter` (campo morto + promessa do Documento A não cumprida). Escolher: deletar e atualizar Documento A, ou implementar o fallback prometido. | Código exposto que diverge da documentação é fonte perene de confusão. | **BAIXA** | PEQUENO | refatoração de código |
| **A8** | Corrigir `iters_est = 1` em [elastic.py:187](backend/solver/elastic.py#L187) — instrumentar brentq (wrapper que conta chamadas) para reportar iterações reais em `SolverResult.iterations_used`. | Campo de diagnóstico está mentindo. Não quebra nada, mas compromete debug futuro. | **BAIXA** | PEQUENO | refatoração de código |
| **A9** | Mover `import math` do meio da função para o topo de [solver.py](backend/solver/solver.py). Remover `from typing import Callable` não usado de [elastic.py](backend/solver/elastic.py). | Housekeeping; não afeta execução. | **BAIXA** | TRIVIAL | refatoração de código |
| **A10** | Remover parâmetro `w` de `find_touchdown()` em [seabed.py:43](backend/solver/seabed.py#L43) ou documentar no Documento A por que a assinatura precisa daquele parâmetro ghost (parece "uniformity" sem necessidade real). | Legibilidade; função pública exportada. | **BAIXA** | TRIVIAL | refatoração de código |
| **A11** | Adicionar um teste smoke que confirme `NotImplementedError` (ou `INVALID_CASE`) quando `solve([seg1, seg2], …)`. Documenta a fronteira de v1 como contrato verificável. | Atualmente a fronteira é só um `if`, não um teste. | **BAIXA** | TRIVIAL | refatoração de código |
| **A12** | Propagar para o Documento A v2.2 (ou gerar um v2.3) as decisões validadas: (i) usar formulação geral da catenária; (ii) BC-04/BC-05 são fully suspended, não touchdown (rótulo errado); (iii) BC-02/07/08/09 redefinidos. | Documento A é a fonte canônica. Se não é atualizado, perde função de "briefing definitivo". | **MÉDIA** | MÉDIO | documentação |
| **A13** | Rodar os 10 BCs contra **outra ferramenta que não MoorPy** quando/se o revisor puder (OrcaFlex, Ariane, Mimosa). Hoje nossa validação é MoorPy-vs-nosso solver; uma terceira fonte aumenta confiança. | Não é bloqueante (MoorPy é referência aberta aceitável), mas elevaria o rigor. | **BAIXA** | GRANDE | validação externa necessária |
| **A14** | Decidir posição sobre suporte a **âncora elevada do seabed** (startpoint_depth > 0 ou endpointGrounded=false). Hoje o código assume silenciosamente que âncora está no seabed. Ou documentar explicitamente essa restrição e rejeitar o caso contrário, ou planejar como suportar. | Premissa implícita sem registro. F2 precisa decidir antes de expor endpoints que recebem `endpointGrounded`. | **MÉDIA** | TRIVIAL (se for rejeitar) ou GRANDE (se for suportar) | decisão pendente |

### Ordenação sugerida

1. **Antes de tocar código da F2**: A1, A2, A3, A4 (documentação — minutos a poucas horas; desbloqueiam contexto).
2. **Antes de expor endpoints**: A5, A6, A14 (refatorações pequenas no solver + 1 decisão).
3. **Paralelo à F2**: A7, A8, A9, A10, A11 (housekeeping) e A12 (atualizar Documento A).
4. **Futuro distante**: A13 (validação externa quando houver oportunidade).

---

## Seção D — Perguntas para o usuário

Para fechar a auditoria com 100% de confiança, gostaria de respostas a:

**Q1 — CLAUDE.md como fonte única.**
Você quer que o CLAUDE.md continue sendo o "índice mestre" (ação A1), ou prefere que eu crie um `docs/STATE.md` mais verboso e que o CLAUDE.md aponte para ele?

**Q2 — Formato `.moor`.**
O QMoor 0.8.5 original tinha um formato `.moor` específico. Temos o payload JSON de exemplo (Seção 5.2 do MVP v2 PDF), mas não um schema formal. Na F2, você quer compatibilidade binária com `.moor` original, ou um novo formato QMoor-Web (JSON) é aceitável? Se o `.moor` original é proprietário/desconhecido, podemos considerar que "exportar `.moor`" significa "exportar JSON que MoorPy ou outras ferramentas consigam consumir"?

**Q3 — Autenticação na API.**
Uso pessoal = local = `localhost`. Devemos ter zero autenticação (confia no firewall local), ou prefere algo simples (token em `.env`, basic auth)? Importa para F2.

**Q4 — Persistência de resultados.**
Quando `/api/cases/{id}/solve` é chamado, o SolverResult é apenas retornado, ou também **persistido** em tabela de execuções com timestamp? E se for persistido, por quanto tempo / quantas últimas execuções por caso?

**Q5 — Âncora elevada (Q crítica).**
Seu uso prático inclui casos onde a âncora NÃO está no seabed (ex.: pendant, ancora em talude com depth diferente de water_depth)? Se sim, A14 vira prioridade ALTA; se não, viramos a restrição explícita e seguimos em frente.

**Q6 — Critérios de utilização configuráveis.**
Seção 5 do Documento A lista 4 perfis (MVP, API RP 2SK-like, DNV, User-defined). Para F2, implementamos os 4 desde o início ou só o "MVP/Preliminary" (default) e adiamos os outros para uma v1.1?

**Q7 — Validação de terceira ferramenta.**
Você tem acesso viável (mesmo trial) a OrcaFlex / Ariane / Mimosa / QMoor-desktop para rodar os 10 BCs e comparar? Se não, deixo A13 como item aberto sem urgência. Se sim, vale marcar janela de tempo.

**Q8 — Perfis de linha sem peso próprio.**
Hoje `LineSegment.w > 0` é validador Pydantic rígido. No futuro vai ter boias distribuídas (peso efetivo negativo por trecho)? Ou sempre teremos `w > 0`? Afeta a generalização do solver.

**Q9 — Escopo explícito de qual documento é canônico.**
Temos: Documento A v2.2, Documentação MVP v2 (PDF), CLAUDE.md, relatorio_F1b.md, Documento B respondido. Hoje o CLAUDE.md diz que o Documento A v2.2 é "briefing definitivo". Mas Seção 6 do MVP v2 PDF é quem define os campos obrigatórios de SolverResult. Se os dois divergirem no futuro (já divergem em alguns pontos), qual vence? Sugestão: deixar explícito em CLAUDE.md.

---

*Fim da auditoria.*
