# Sprint 1 — Import QMoor 0.8.0 (v1.1.0)

**Branch:** `feature/qmoor-import-sprint1`
**Estratégia:** Tier A — schema rico, cálculo simples. **Solver core
permanece intocado** em v1.0; a Sprint 1 enriquece o modelo de dados e
o pipeline de import sem afetar a física validada das fases F1-F11.

## Resumo executivo

A Sprint 1 destrava o caminho para "produção real" do AncoPlat:
modelos profissionais como o KAR006 (Karoon Energy) podem ser
importados do QMoor 0.8.0 com fidelidade total — múltiplas linhas,
múltiplos profiles operacionais, vessel/plataforma, perfil de corrente
V(z), pendant multi-segmento e metadata operacional do projeto.

| | Antes Sprint 1 | Após Sprint 1 |
|---|---|---|
| Cases por import .moor | 1 | até `n_lines × n_profiles` |
| Vessel/plataforma | ausente | `CaseInput.vessel` opcional |
| Perfil de corrente V(z) | ausente | `CaseInput.current_profile` (≤20 layers) |
| Pendant multi-segmento | 1 segmento | até 5 trechos |
| Metadata operacional | implícita (description) | `CaseInput.metadata` (≤20 chaves) |
| Drag distribuído | manual | helper opt-in `discretize_current_profile()` |
| Backend tests | 665 | 820 (+155) |
| Frontend tests | 181 | 187 (+6) |

## Decisões de design

### 1. Vessel é case-level metadata, NÃO `kind="vessel"`
Mapeia direto à estrutura QMoor JSON (vessels é top-level, não item
dentro de mooringLines[].profiles[].segments[]). Não conflita com
AHV/buoy/clump (esses representam carga aplicada num ponto da linha,
semantically diferente do hull). Solver não precisa de filtro novo.

### 2. CurrentProfile é METADADO em v1.0
Solver não consome diretamente. Helper `discretize_current_profile()`
em `backend/solver/current_discretizer.py` é opt-in: caller (UI ou
endpoint dedicado) decide quando converter o perfil em AHVs pontuais.
Esta separação garante:
1. Round-trip do JSON QMoor preserva o perfil EXATO.
2. Cálculo continua reprodutível bit-a-bit em casos sem discretização.
3. Discretização vira função pura, testável independentemente.

Modelo físico (Morison estático): `F_i = 0.5 · ρ · Cd · D · Δs · V²`.
Defaults: ρ = 1025 kg/m³, Cd = 1.2.

### 3. Editor de vessel/current/metadata é Tier B (post-v1.1.0)
Sprint 1 entrega DISPLAY read-only via `ImportedModelCard`. Editor
manual desses campos será tratado em sprint posterior — o caso de uso
crítico v1.1.0 é "preservar fielmente o que veio do QMoor".

### 4. PendantSegment lenient
Apenas `length` é obrigatório; demais campos opcionais. Pendants em
exports QMoor frequentemente carregam só o nome do material e o
comprimento — schema rígido bloquearia imports legítimos. Os campos
não são consumidos pelo solver, então tolerância não compromete física.

## Commits

```
5f3fdde feat(schema): adiciona metadata operacional opcional em CaseInput
f8f898f feat(schema): adiciona PendantSegment + LineAttachment.pendant_segments[]
e957398 feat(schema): adiciona Vessel + CaseInput.vessel (case-level metadata)
f327a78 feat(schema): adiciona CurrentProfile + CaseInput.current_profile
1479f1c feat(solver): adiciona current_discretizer (CurrentProfile → AHVs)
7f45762 feat(import): parser QMoor 0.8.0 (multi-line × multi-profile → list[CaseInput])
b2c3965 feat(import-qmoor-0.8): endpoints REST + UI dialog com profile selector
ce2677c feat(ui): ImportedModelCard exibe vessel/corrente/metadata em CaseDetail
d9128eb test(qmoor-0.8): E2E import → solve → export pipeline
```

## Gates

- ✅ `cases_baseline_regression` 3/3 (rtol=1e-9 preservado).
- ✅ Backend suite: 820 passed, 6 skipped, 6 xfailed.
- ✅ Frontend suite: 187 passed (20 test files).
- ✅ Build frontend: passa em ~1.5s.
- ⏸ E2E real do KAR006: pula até user dropar arquivo em
  `docs/audit/qmoor_kar006_sample.json`.

## Pendências post-Sprint 1 (Tier B)

1. **Editor manual** dos novos campos (vessel, current_profile,
   metadata) em CaseFormPage. Hoje só read-only.
2. **Discretização auto** com botão na UI: "Aplicar arrasto distribuído"
   chama `discretize_current_profile()` e adiciona AHVs ao caso. Exigirá
   D020 (warning) documentando idealização (mesmo modelo de F8/AHV).
3. **Round-trip QMoor 0.8.0 export**: hoje só import. `.moor v3` ou
   exporter dedicado para gerar JSON QMoor 0.8.0 a partir do CaseInput.
4. **openapi.ts regen**: tipos novos (vessel, current_profile, etc.)
   ainda não estão em `frontend/src/types/openapi.ts`. ImportedModelCard
   usa tipos inline + cast `as unknown` no consumidor. Regenerar quando
   o ciclo de codegen for re-rodado.
5. **KAR006 real ground truth**: anexar JSON ao repo (sob NDA se
   aplicável) e validar que o import produz cases que solve sem erro.

## Próximos passos imediatos

1. Mergear `feature/qmoor-import-sprint1` para `main`.
2. Bump versão para v1.1.0-rc.1.
3. Smoke prod com payload sintético antes de tag v1.1.0.
4. Quando user passar o JSON KAR006 real, rodar
   `pytest backend/api/tests/test_qmoor_v0_8_e2e.py::test_kar006_real_se_disponivel`
   como gate adicional antes da tag.

## Arquivos novos

- `backend/api/services/moor_qmoor_v0_8.py` — parser QMoor 0.8.0
- `backend/solver/current_discretizer.py` — discretizador opt-in
- `backend/api/tests/fixtures/qmoor_v0_8_synthetic.py` — fixtures
- `backend/api/tests/test_qmoor_v0_8_parser.py` — 28 testes
- `backend/api/tests/test_qmoor_v0_8_endpoints.py` — 11 testes
- `backend/api/tests/test_qmoor_v0_8_e2e.py` — 3 testes
- `backend/solver/tests/test_pendant_segments_schema.py` — 17 testes
- `backend/solver/tests/test_vessel_schema.py` — 24 testes
- `backend/solver/tests/test_current_profile_schema.py` — 19 testes
- `backend/solver/tests/test_current_discretizer.py` — 29 testes
- `frontend/src/components/common/ImportedModelCard.tsx`
- `frontend/src/test/imported-model-card.test.tsx` — 6 testes

## Arquivos modificados

- `backend/api/schemas/cases.py` — `metadata` + `vessel` + `current_profile`
- `backend/api/routers/moor_io.py` — 2 novos endpoints
- `backend/api/tests/test_cases_api.py` — 6 testes metadata
- `backend/solver/types.py` — `PendantSegment`, `Vessel`,
  `CurrentLayer`, `CurrentProfile`, `LineAttachment.pendant_segments`
- `frontend/src/api/endpoints.ts` — `previewQmoorV08`, `commitQmoorV08`
- `frontend/src/pages/ImportExportPage.tsx` — selector QMoor 0.8.0
- `frontend/src/pages/CaseDetailPage.tsx` — integra `ImportedModelCard`
