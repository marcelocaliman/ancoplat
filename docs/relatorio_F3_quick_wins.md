# Relatório — Fase 3: Quick wins UX

**Data de fechamento:** 2026-05-05
**Branch:** `feature/fase-3-quick-wins-ux`
**Plano de referência:** [`docs/plano_profissionalizacao.md`](plano_profissionalizacao.md), seção "Fase 3".
**Commits:** 6 atômicos.

---

## 1. Sumário executivo

Fase 3 fechada com 6 commits sobre a branch acima. Entrega 5 quick wins UX visuais que fecham gaps cosméticos com o QMoor sem mexer em física. **Tudo cosmético** — solver não foi tocado, regressão `cases_baseline.json` 3/3 preservada.

- **A1.5** — Painel agregado `LineSummaryPanel` (n. segs, L_total, peso seco, peso molhado) no topo da aba Linha.
- **D6** — Trecho grounded como linha pontilhada (`dash: 'dot'`). Cor **vermelha preservada** (decisão consciente — diverge da convenção cinza do QMoor; documentada em CLAUDE.md).
- **D7** — Ícones do startpoint conforme tipo: dispatcher `getStartpointSvg()` com 3 SVGs (semi-sub/FPSO existente + AHV + Barge novos) + opção `none` (omite ícone).
- **A2.5** — Dropdown "Tipo de plataforma" no grupo Fairlead da aba Ambiente; `boundary.startpoint_type` no schema (cosmético, nunca usado pelo solver).
- **D9** — 4 toggles no canto superior do plot (Maximize2 / Type / Tag / Image): equal-aspect, labels, legend, images. Ícones Lucide compactos com tooltip.

**Suite final:** 372 backend + 41 frontend = **413 testes verdes** + 3 skipados documentados. Zero regressão; gates F1 (BC-MOORPY, BC-FR-01, BC-EA-01) e F2 (BC-FAIRLEAD-SLOPE-01, validation_raises) todos verdes.

---

## 2. Decisões Q1–Q8 documentadas

| Q | Tema | Decisão | Onde está |
|---|---|---|---|
| **Q1** | Valores do enum `startpoint_type` | (a) Literal do plano: `"semisub"` (default), `"ahv"`, `"barge"`, `"none"` | `backend/solver/types.py` BoundaryConditions |
| **Q2** | Onde colocar o Select startpoint_type | (a) **Grupo "Fairlead" da aba Ambiente** (coesão com startpoint_depth/offsets) | `CaseFormPage.tsx` aba Ambiente |
| **Q3** | Cor do grounded pontilhado | (a) **Vermelho preservado** — decisão consciente, não cinza como QMoor. Princípio transversal #4: MoorPy/QMoor são referência, não target de paridade total. | `CatenaryPlot.tsx:650,703` + nota em CLAUDE.md |
| **Q4** | Layout dos toggles do plot | (a) Ícones compactos (24×24px) com tooltip, padrão Plotly modebar | `CatenaryPlot.tsx` `PlotToggleButton` |
| **Q5** | Painel agregado — campos | (a) Literal do plano: 4 campos. MBL_min/EA_min para Fase 5 (memorial). | `LineSummaryPanel.tsx` |
| **Q6** | Tipo de teste do plot | (b)+(c) **Functional + smoke**, sem snapshot frágil de Plotly | `catenary-plot-startpoint.test.ts` |
| **Q7** | Onde ficam SVGs novos | (a) **Inline em CatenaryPlot.tsx** (preserva padrão atual) | `CatenaryPlot.tsx:83-113` |
| **Q8** | startpoint_type retro-compat | Default `"semisub"` (preserva ícone pré-F3) | Pydantic Field default |

### Sem ajustes do mini-plano
Esta fase era mais leve que F1/F2 — nenhum ajuste do usuário no mini-plano. Q1–Q8 todos confirmados como propostos. R3.B (CatenaryPlot.tsx grande) mitigado com alterações cirúrgicas.

---

## 3. Decisão fechada: grounded pontilhado **vermelho** (não cinza como QMoor)

Registrada formalmente neste relatório e em `CLAUDE.md`:

> O AncoPlat exibe a porção apoiada (grounded) da linha como **linha pontilhada vermelha** (`dash: 'dot'`, cor `palette.grounded` ≈ #DC2626). O QMoor 0.8.5 usa cinza pontilhado. Adotamos vermelho como decisão consciente porque:
>
> 1. Vermelho destaca melhor a porção apoiada do que cinza, especialmente em plots com fundo claro/escuro alternativos (sistema de tema do AncoPlat).
> 2. Princípio transversal #4 do plano de profissionalização: "MoorPy/QMoor são referência de validação, não target de paridade total". Cinza seria nivelamento por baixo sem ganho técnico.
> 3. Engenheiros novos no AncoPlat acostumados com QMoor reconhecem o padrão "sólido = suspended, pontilhado = grounded" — o que pesa é a textura, não a cor.

Plano §274 documenta a decisão. CLAUDE.md (atualizado neste commit) inclui na seção de decisões UX. Daqui a 6 meses, a citação garante rastreabilidade.

---

## 4. Métricas atingidas

| Critério | Métrica alvo | Atingido | Evidência |
|---|---|---|---|
| `LineSummaryPanel` na aba Linha com agregados corretos | Soma para 1, 3, 10 segments + visual | ✅ 7 testes em `line-summary.test.ts` | unit |
| Grounded pontilhado vermelho em todos os plots | 2 call-sites + legend | ✅ `dash: 'dot'` em CatenaryPlot.tsx:650,703 + legend | inspeção |
| Trocar `startpoint_type` muda apenas o ícone | Solver não chamado, props propaga | ✅ propagação via `boundary.startpoint_type → CatenaryPlot.startpointType` | functional |
| Toggle equal-scale alterna 1:1 vs auto | Estado interno + Plotly layout | ✅ `equalAspectLocal` controla `yAxis.scaleanchor` | inspeção |
| Toggles labels/legend/images alternam visibilidade | 3 toggles independentes | ✅ Plotly `images: []`, `annotations: []` + `{showLegend && ...}` | inspeção |
| Suite backend ≥ 365 verde | zero regressão | ✅ **372 + 3 skipped** | pytest |
| Suite frontend ≥ 32 + N novos | zero regressão | ✅ **41 verde** | npm test |
| TS build sem erro | binário | ✅ | npm run build |
| `cases_baseline_regression` 3/3 verde | gate Princípio #1 | ✅ | regression |
| BC-MOORPY 7/7 ativos preservados | rtol≤1e-4 | ✅ | regression |
| BC-FR-01 + BC-EA-01 + BC-FAIRLEAD-SLOPE-01 preservados | F1+F2 gates | ✅ | regression |
| CLAUDE.md atualizado com decisão grounded vermelho | citação §274 do plano | ✅ | grep |

---

## 5. Histórico de commits da fase

```
38e03ef  feat(line): LineSummaryPanel com agregados (A1.5)
570c7de  feat(plot): toggles equal-aspect/labels/legend/images (D9)
43a9403  feat(plot): grounded pontilhado vermelho + ícones startpoint_type (D6+D7)
4f02cd6  feat(form): Select 'Tipo de plataforma' no grupo Fairlead (A2.5)
e92a263  feat(types): startpoint_type enum cosmético (A2.5+D7)
[este]   docs(fase-3): relatório + CLAUDE.md + plano + decisão grounded vermelho
```

---

## 6. Divergências do plano original

Nenhuma significativa. As 8 decisões Q1–Q8 alinharam exatamente com o plano. R3.B (CatenaryPlot.tsx grande) foi mitigado cirurgicamente — modificações em sites pontuais com referências de linha exatas, sem refactor amplo.

Pequena observação operacional: o `CatenaryPlot.tsx` cresceu de ~1300 para ~1500 linhas com SVGs novos + dispatcher + toggles + helper component. Próximos toques nesse arquivo (Fase 4 ProfileType taxonomy, Fase 9 polish) devem considerar extrair os SVGs e helpers para arquivos separados — pendência registrada para Fase 9.

---

## 7. Estado da UI após Fase 3

**Aba Linha (CaseFormPage):**
```
┌─────────────────────────────────────────────────────────────────┐
│ SEGMENTOS: 3   COMPRIMENTO TOTAL: 1000.00 m                     │
│ PESO MOLHADO: 462.16 kN  PESO SECO: 540.40 kN                   │
└─────────────────────────────────────────────────────────────────┘

[Segmento 1 — chain]   [Segmento 2 — wire]   [Segmento 3 — chain]
  length / w / EA / ...  length / w / EA / ...  length / w / EA / ...
```

**Aba Ambiente — grupo Fairlead** (adições da F3 destacadas):
```
FAIRLEAD
  Profundidade abaixo da água    [m]
  Offset horizontal (cosmético)  [m]
  Offset vertical (cosmético)    [m]
  Tipo de plataforma             [Semi-Sub / FPSO ▼]   ← novo F3
                                 ├ AHV (Anchor Handler)
                                 ├ Barge
                                 └ Sem ícone
```

**Plot (CatenaryPlot)** — controles novos:
```
                                                        ⊞ T 🏷 🖼  ← toggles F3
  [Legenda HTML]
  ─────────────  (suspended sólido colorido)
  · · · · · · ·  (grounded pontilhado vermelho)  ← muda em F3
  ⛴ Fairlead     ← ícone muda conforme startpoint_type (F3)
  ⚓ Âncora
```

Os 4 botões pequenos no canto superior direito controlam:
- ⊞ Maximize2 → equal-aspect (1:1)
- T Type → labels Fairlead/Âncora
- 🏷 Tag → legenda HTML
- 🖼 Image → ícones SVG (plataforma, âncora, boias)

---

## 8. Pendências para fases seguintes

- **Fase 4** (Diagnostics maturidade + ProfileType taxonomy): SVGs do plot já estão prontos para exibir variações de ProfileType conforme o regime catenário detectado.
- **Fase 5** (Reports/memorial): MBL_min e EA_min entram no memorial técnico, complementando os 4 campos do `LineSummaryPanel`.
- **Fase 9** (UI polish): considerar extrair SVGs do `CatenaryPlot.tsx` (que cresceu para ~1500 linhas) para `frontend/src/components/common/plot-icons/` ou similar.

---

## 9. Critério de fechamento da fase

| Critério | Status |
|---|---|
| Branch dedicada com 6 commits atômicos | ✅ |
| Sem mudanças fora do escopo (solver intacto) | ✅ Apenas types.py (campo cosmético) + frontend |
| Suite backend verde | ✅ 372 + 3 skip |
| Suite frontend verde | ✅ 41 |
| TS build | ✅ |
| `cases_baseline_regression` 3/3 verde | ✅ |
| BC-MOORPY 7/7 + BC-FR-01 + BC-EA-01 + BC-FAIRLEAD-SLOPE-01 preservados | ✅ |
| CLAUDE.md atualizado com decisão grounded vermelho | ✅ |
| Relatório com tabela Q1–Q8 documentada | ✅ |
| Pendências documentadas | ✅ §8 |

**Fase 3 está pronta para merge.** Aguardando OK do usuário conforme protocolo. Não inicio Fase 4.
