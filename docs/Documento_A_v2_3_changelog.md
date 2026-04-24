# Documento A — Changelog v2.2 → v2.3

Este arquivo lista as correções e adições que devem ser incorporadas ao
`Documento_A_Especificacao_Tecnica_v2_2.docx` para produzir uma v2.3.

Como o arquivo `.docx` é binário, a propagação mecânica para o Word fica
a cargo do usuário. Até que seja feita, **esta é a fonte canônica** das
decisões ratificadas em F1a, F1b e na auditoria pré-F2.

Data da consolidação: 2026-04-24.
Commits de referência: d772332..c95ad2e.

---

## Correções na Seção 3 (Especificação do solver)

### 3.3.1 — Formulação geral da catenária (substitui texto atual)

A versão v2.2 apresentava equações assumindo âncora no vértice
(V_anchor = 0):

    h = a · (cosh(X_s/a) − 1)
    L_s = a · sinh(X_s/a)
    T_fl = H · cosh(X_s/a)

Isso é um **caso particular**. Para casos fully suspended com tração
alta no fairlead (ex.: BC-01 com T_fl=785 kN), V_anchor > 0, e a
formulação simplificada não aplica. A **forma geral** é:

    x(s) = a · asinh(s/a)          [medido do vértice da catenária]
    y(s) = sqrt(a² + s²) − a
    T(s) = w · sqrt(a² + s²)
    H    = a · w                    [constante no trecho suspenso]
    V(s) = w · s

Para âncora em s_a ≥ 0 e fairlead em s_f = s_a + L:

    X       = a · (asinh(s_f/a) − asinh(s_a/a))
    h       = sqrt(a²+s_f²) − sqrt(a²+s_a²)
    T_anchor= w · sqrt(a² + s_a²)
    T_fl    = w · sqrt(a² + s_f²)

A formulação v2.2 é recuperada impondo s_a = 0. O solver implementa a
forma geral e **despacha** entre suspensa e com touchdown via valores
críticos `T_fl_crit` e `X_crit` (`backend/solver/seabed.py:71-93`).

### 3.5.1 — Fallback de bisseção removido

A v2.2 mencionava:

> Fallback: bisseção pura se Brent não convergir em 50 iterações.

Essa linha deve ser **removida** ou alterada para:

> Solver usa `scipy.optimize.brentq`, que é método híbrido
> Brent-Dekker com fallback nativo de bisseção. Fallback externo
> adicional seria redundante e não está implementado.

O parâmetro `max_bisection_iter` foi removido de `SolverConfig` no
commit `5c7519c`.

### 3.3.2 — Correção elástica: método de resolução

A v2.2 descreve a fórmula `dL_stretched = dL · (1 + T̄/EA)` (correta),
mas não especifica o método numérico de resolução do ponto fixo. A v2.3
deve incluir:

> O ponto fixo `L_stretched = L · (1 + T̄(L_stretched)/EA)` é
> resolvido via `scipy.optimize.brentq` sobre
> `F(L_eff) = L_eff − L·(1+T̄(L_eff)/EA) = 0`. **Iteração de ponto fixo
> simples diverge** em casos de linha muito taut (L_stretched próximo
> de `√(X²+h²)`) por oscilação entre ambos os lados do fixo. Bracket
> explícito em limites físicos: `L_lo = √(X²+h²)·1.0001` para mode
> Range, `L_lo = L` para mode Tension; `L_hi_cap = (X+h)·0.9999` para
> mode Range, `L_hi_cap = L·100` para mode Tension.

---

## Correções na Seção 5 (Critérios de utilização)

A v2.2 descreve 4 perfis (MVP/Preliminary, API RP 2SK-like, DNV-like,
User-defined) mas deixa ambíguo quem classifica a tração. Esclarecer:

> A classificação é feita pelo próprio solver. `SolverResult.alert_level`
> assume um de: `ok | yellow | red | broken`. O facade `solve()` aceita
> `criteria_profile` e `user_limits` para selecionar os thresholds.
>
> Limites default por perfil (backend/solver/types.py PROFILE_LIMITS):
>   - MVP_Preliminary: 0.50 / 0.60 / 1.00
>   - API_RP_2SK:      0.50 / 0.60 / 0.80 (broken em 0.80 danificado)
>   - DNV_placeholder: 0.50 / 0.60 / 1.00 (idêntico a MVP até F4+)
>   - UserDefined:     usuário fornece UtilizationLimits

Alert = BROKEN dispara `INVALID_CASE` no `solve()`: "linha rompida" é
engenheiramente inviável mesmo que convirja matematicamente.

---

## Correções na Seção 6 (Casos de benchmark)

### 6.1.1 — BC-01 (manter como está)

Correto conforme v2.2. Validado contra MoorPy com ΔH < 0,001%.

### 6.1.2 — BC-04 — rótulo incorreto: é fully suspended, NÃO touchdown

A v2.2 rotula BC-04 como "Elástico com touchdown, modo Tension", mas
com os parâmetros especificados (h=1000, L=1800, T_fl=150 t=1471 kN,
wire 3"):

    T_fl_crit = w·(h² + L²)/(2h) ≈ 201·4,240,000/2000 ≈ 426 kN
    T_fl_input = 1471 kN  >>  T_fl_crit = 426 kN

Portanto a linha está **totalmente suspensa**. O rótulo correto é
"Elástico **sem** touchdown, modo Tension" — teste elástico em regime
suspenso com atrito (irrelevante quando L_g=0) e EA=34,25 MN.

### 6.1.3 — BC-05 — mesmo rótulo incorreto

BC-05 (X=1450 m, mesma geometria de BC-04) também é fully suspended
(X=1450 > X_crit≈1404). Corrigir rótulo para "Elástico sem touchdown,
modo Range".

### 6.2 — BCs definidos (substitui "entradas a definir")

Os BCs abaixo foram definidos em F1b e validados contra MoorPy dentro
das tolerâncias da Seção 6.3 (geom 0,5%, força 1%, grounded 2%):

**BC-02 — Catenária pura com touchdown + atrito moderado**
  - h=300 m, L=700 m, wire 3" (w=13,78 lbf/ft, EA≈∞ (rígido))
  - μ=0,30 (wire em argila firme, Seção 4.4)
  - Modo Tension, T_fl=150 kN
  - Output esperado: X≈594 m, L_g≈102 m, T_anchor≈83,5 kN

**BC-07 — Linha longa, tração baixa, grande grounded**
  - h=100 m, L=2000 m, wire 3"
  - μ=0,30
  - Modo Tension, T_fl=30 kN (> w·h≈20,1 kN, mas << T_fl_crit)
  - Output esperado: X≈1947 m, L_g≈1859 m (93% grounded), T_anchor=0

**BC-08 — μ=1,0 (atrito elevado)**
  - Mesma geometria de BC-02 (h=300, L=700, wire 3", T_fl=150 kN)
  - μ=1,0
  - Output esperado: X, L_g idênticos a BC-02 (μ não afeta geometria);
    T_anchor significativamente menor

**BC-09 — μ=0 (sem atrito)**
  - Mesma geometria de BC-02
  - μ=0,0
  - Output esperado: X≈594 m, L_g≈102 m, T_anchor=H≈89,7 kN
    (sem redução por atrito)

**Observação sobre BC-09 original**: a v2.2 sugeria usar os parâmetros
de BC-04 com μ=0. Isso daria linha fully suspended (T_fl=1471 kN >>
T_fl_crit=426 kN), inútil para testar touchdown sem atrito. A
redefinição acima garante touchdown claro.

**BC-10 — Multi-segmento**
  - Permanece escopo v2.1 (correto conforme v2.2).

---

## Adições na Seção 7 (Arquitetura) — novos campos

### 7.1 — Restrições explícitas do MVP v1

Adicionar:

> O MVP v1 assume:
>   - Fairlead na superfície (`startpoint_depth = 0`).
>   - Âncora no seabed (`endpoint_grounded = True`).
>   - Uma única linha homogênea (`len(line_segments) == 1`).
>
> Valores fora desses defaults são validados pelo facade `solve()`
> e retornam `INVALID_CASE` com mensagem explícita. Suporte para
> âncora elevada e fairlead afundado fica para v2+.

### 7.2 — Endpoints API — detalhamento

A v2.2 lista apenas método+rota+função. O desenho completo
(request/response schemas, códigos HTTP, CORS, versionamento,
persistência, perfis de critério) está em
[`docs/plano_F2_api.md`](plano_F2_api.md). A v2.3 deve apontar para
esse documento como anexo.

---

## Resumo das divergências v2.2 → v2.3

| Seção | Natureza | Status |
|-------|----------|:------:|
| 3.3.1 | Correção: formulação geral (não só âncora no vértice) | CRÍTICO |
| 3.3.2 | Adição: método (brentq no ponto fixo elástico) | IMPORTANTE |
| 3.5.1 | Remoção: fallback de bisseção manual | COSMÉTICO |
| 5     | Adição: 4 perfis de critério + AlertLevel | IMPORTANTE |
| 6.1.2 | Correção: BC-04 é suspended, não touchdown | CRÍTICO |
| 6.1.3 | Correção: BC-05 mesma questão | CRÍTICO |
| 6.2   | Definição: BC-02, BC-07, BC-08, BC-09 concretos | IMPORTANTE |
| 7.1   | Adição: restrições MVP v1 explícitas | IMPORTANTE |
| 7.2   | Referência: detalhes em plano_F2_api.md | IMPORTANTE |

---

*Fim do changelog v2.3.*
