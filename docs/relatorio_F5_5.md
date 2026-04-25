# Relatório F5.5 — Equilíbrio de plataforma sob carga ambiental

> Última iteração de física do MVP estático. Encerra o motor.

## Escopo

Antes do F5.5, o MVP era estático em arranjo neutro: o usuário fixava
T_fl ou X por linha; cada linha era resolvida isoladamente; o agregado
de forças era informativo (mostrava se o spread estava balanceado).
Não havia como responder a pergunta clássica:

> "Qual o offset da plataforma sob 200 kN de vento + 100 kN de corrente?"

F5.5 fecha esse gap.

## Faseamento

| Slice    | Conteúdo                                                              | Status  |
|----------|-----------------------------------------------------------------------|---------|
| F5.5.1   | Tipos `EnvironmentalLoad` + `PlatformEquilibriumResult`               | ✅      |
| F5.5.2   | Solver `solve_platform_equilibrium` (fsolve outer + per-line Range)   | ✅      |
| F5.5.3   | BCs de validação (BC-EQ-01..08)                                       | ✅      |
| F5.5.4   | Endpoints REST `POST /equilibrium` e `/equilibrium-preview`           | ✅      |
| F5.5.5   | Frontend: painel de equilíbrio + plan view com offset + setas         | ✅      |
| F5.5.6   | Curva de restauração (opcional, diagnóstico de stiffness)             | ⬜      |

## Física

**Convenção do offset**: a plataforma desloca **na direção da carga
aplicada**. Cabos do lado oposto se estendem e geram a força
restauradora em sentido contrário, balanceando o sistema.

Equação:

```
Σ F_lines(Δx, Δy) + F_env = 0
```

onde cada `F_line_i(Δ)` é a força horizontal da linha i sobre a
plataforma quando o fairlead está deslocado de Δ. A âncora fica
fixa no espaço.

## Algoritmo

[`backend/solver/equilibrium.py`](../backend/solver/equilibrium.py):

1. **Baseline** — resolve cada linha em `Δ=0` usando seu boundary
   spec original. O X resolvido determina a posição da âncora no
   plano da plataforma:
   `anchor_i = (R_i + X_baseline_i) · (cos θ_i, sin θ_i)`.
2. **Outer loop** — `scipy.optimize.fsolve` em duas variáveis
   (Δx, Δy) com função residual = `Σ F_lines(Δ) + F_env`.
3. **Inner per-line solve** — para cada Δ, calcula:
   - `fairlead_novo_i = R_i · (cos θ_i, sin θ_i) + Δ`
   - `vetor_i = anchor_i − fairlead_novo_i`
   - `X_novo_i = ‖vetor_i‖`
   - chama `solve()` em modo Range com `X_novo_i`
   - `F_i = H_i · vetor_i / ‖vetor_i‖` (radial outward na nova geometria)
4. **Critério de convergência**: `‖resíduo‖ ≤ 10 N` por padrão.

## Endpoints

| Método | Rota                                                  | Body                               | Resposta |
|--------|-------------------------------------------------------|------------------------------------|----------|
| POST   | `/api/v1/mooring-systems/{id}/equilibrium`            | `{Fx, Fy, Mz?}` (N e N·m)          | `PlatformEquilibriumResult` |
| POST   | `/api/v1/mooring-systems/equilibrium-preview`         | `{system: MooringSystemInput, env}`| Mesmo, sem persistir |

Equilíbrio **não persiste** — é input transiente. UI tipicamente chama
o endpoint à medida que o usuário move sliders de carga.

## Frontend

[`MooringSystemDetailPage.tsx`](../frontend/src/pages/MooringSystemDetailPage.tsx)
ganhou card **"Equilíbrio sob carga ambiental"**:

- Inputs `Fx` e `Fy` em kN (proa = +X, bombordo = +Y)
- Botão "Calcular equilíbrio" → POST → toast com offset/azimuth/iter
- Painel de resultado: offset (mag/azimuth/Δx/Δy), resíduo colorido,
  iterações, convergidas, máx. utilização, mensagem do solver
- Botão "Resetar" zera carga e remove overlay

[`MooringSystemPlanView.tsx`](../frontend/src/components/common/MooringSystemPlanView.tsx)
ganhou prop `equilibrium?`:

- Plataforma desloca pra `offset_xy`; fairleads e linhas redesenham
  na nova geometria
- Fantasma da posição neutra fica em pontilhado pra comparação
- Seta cinza tracejada do centro neutro → centro deslocado (vetor offset)
- Seta rosa partindo da plataforma deslocada → carga ambiental aplicada
- Aggregate-resultant arrow (do modo neutro) é ocultada quando há
  equilíbrio (informação substituída pelas duas setas novas)

## BCs de validação

[`backend/api/tests/test_platform_equilibrium_f5_5.py`](../backend/api/tests/test_platform_equilibrium_f5_5.py) — 14 testes verde.

| BC          | Descrição                                                          |
|-------------|--------------------------------------------------------------------|
| BC-EQ-01    | Spread 4× sem carga → offset zero, resíduo zero                    |
| BC-EQ-02    | Carga +X 50 kN → offset +X (mesmo sentido), Y desprezível          |
| BC-EQ-03    | Carga oblíqua 30°/40 kN → offset em ~30° (mesmo sentido)           |
| BC-EQ-04    | Tripé 0/120/240° + carga +X → offset +X                            |
| BC-EQ-05    | line_results inclui todas as 4 linhas no caso convergido           |
| BC-EQ-06    | Carga +Y 30 kN → offset +Y, X desprezível                          |
| BC-EQ-07    | Resíduo / carga < 0.1% em equilíbrio convergido                    |
| BC-EQ-08    | Agregados (n_converged, max_utilization) populados                 |
| —           | EnvironmentalLoad default zero, magnitude(3,4)=5                   |
| API         | POST /equilibrium carga zero (offset zero)                         |
| API         | POST /equilibrium carga +X (offset +X, resíduo < 10 N)             |
| API         | POST /equilibrium id inexistente → 404                             |
| API         | POST /equilibrium-preview com input completo                       |

Suite total backend: **260 testes verde**.

## Decisões técnicas

1. **Equilíbrio não é persistido**. Diferente do `solve` (estado
   neutro, persistido em `mooring_system_executions`), o equilíbrio
   é uma derivação a partir de F_env transiente. Persistir cada
   experimento de carga inflaria o histórico sem benefício.

2. **Modo Range é forçado por linha**. Mesmo que a linha tenha sido
   originalmente especificada em modo Tension, no equilíbrio a
   geometria (X) é dada pelo offset; T_fl é resultado, não input.

3. **Linhas que falham no baseline saem do equilíbrio**. Se uma
   linha não converge no estado neutro, sua âncora fica indefinida e
   ela é silenciosamente excluída da iteração de equilíbrio. O
   `n_converged` no resultado reflete isso.

4. **Mz reservado, não usado**. Yaw seria um terceiro grau de
   liberdade. No mooring radial (fairleads em (R cos θ, R sin θ),
   linhas saindo radialmente), `M_z = Σ r × F = 0` por construção. Pra
   acoplar yaw seria preciso fairleads não-centrados ou linhas
   tangenciais — fora do escopo MVP.

5. **fsolve em vez de Newton manual**. SciPy já dá Levenberg-Marquardt
   robusto. Tipicamente converge em 5–15 iterações, com tolerância
   de 1 mm no offset. Para casos extremos (cargas muito acima da
   capacidade restauradora) o solver retorna `converged=False` mas
   ainda devolve o melhor offset encontrado pra o usuário inspecionar.

## F5.5 — encerrada

Com este slice, o motor estático do app está fechado em termos
físicos. O que segue (F5.5.6 e além) é diagnóstico/UX:

- **F5.5.6 (opcional)**: curva de restauração — sweep da magnitude
  de carga ao longo de uma direção fixa, plot offset × força. Útil
  pra caracterizar a "stiffness" do mooring sem rodar solves manuais.
- **Validação MoorPy multi-linha**: MoorPy suporta sistemas; uma
  bateria de comparação numérica seria a validação cruzada do solver.
- **Tipo de âncora explícito** (drag/pile/suction): com thresholds
  de uplift próprios; foi mencionado em F5.4.6b.
