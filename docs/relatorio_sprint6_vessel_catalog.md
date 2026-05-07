# Sprint 6 — Vessel padronizado + polish visual

> Branch: `feature/sprint6-vessel-catalog`
> Commits: 50, 51+52, 53-55, 56+57, 58
> Status: ✅ Sprint completa, 8 commits sequenciais
> Data: 2026-05-07

## Contexto

Usuário identificou via screenshot QMoor que:
1. Vessel não aparecia no preview live da edição (bug).
2. Vessel deveria ser catálogo padronizado (dropdown), não input livre.
3. Plot do AncoPlat divergia visualmente do QMoor (square laranja em vez de embarcação).

## Decisão fechada #20

**Decisão:** Catálogo `vessel_types` análogo a `buoys` (F6) e `line_types` (F1a). Editor refatorado com `VesselPicker` no topo + override manual com badge "do catálogo"/"manual". 5 SVGs dedicados no plot por `vessel_type`.

## Mapa dos 8 commits

| # | Tema | Status |
|---|---|---|
| 50 | DB tabela vessel_types + SQLAlchemy + seed 9 vessels | ✅ +6 testes |
| 51+52 | Schemas Pydantic + 5 endpoints REST /vessel-types | ✅ +11 testes |
| 53-55 | VesselPicker + VesselEditor refatorado + fix preview | ✅ +5 testes |
| 56+57 | 5 SVGs por vessel_type + AHV deck SVG (refine Sprint 5) | ✅ visual |
| 58 | Docs + decisão #20 + CHANGELOG + CLAUDE | ✅ |

## Arquitetura entregue

### Backend

- `backend/api/db/models.py`: `VesselTypeRecord` com 9+ campos físicos.
- `backend/data/seed_vessels.py`: 9 vessels canônicos:
  - 2× FPSO (P-77 + Suezmax genérico)
  - 2× Semisubmersible (Atlanta + genérico)
  - 1× Spar
  - 2× AHV (200 te + 100 te)
  - 1× Drillship
  - 1× Barge MODU
- `backend/api/schemas/vessels.py`: VesselCreate/Update/Output Pydantic.
- `backend/api/services/vessel_service.py`: list/get/create/update/delete + IMMUTABLE_SOURCES.
- `backend/api/routers/vessels.py`: 5 endpoints REST com 403 para seed.

### Frontend

- `frontend/src/components/common/VesselPicker.tsx`: popover com busca debounced.
- `frontend/src/components/common/VesselEditor.tsx`: VesselPicker no topo + badge "do catálogo"/"manual".
- `frontend/src/lib/caseSchema.ts`: `vessel.catalog_id` opcional (rastreabilidade Q7).
- `frontend/src/pages/CaseFormPage.tsx`: `vessel={values.vessel}` passado ao CatenaryPlot do preview live.
- `frontend/src/api/types.ts`: tipos VesselOutput/Create/Update inline (openapi.ts pendente regen).
- `frontend/src/api/endpoints.ts`: listVessels/getVessel/createVessel/updateVessel/deleteVessel.

### Plot SVGs

- `semisubSvg`: 4 colunas + deck + heliponto.
- `fpsoSvg`: casco navio + torre + helideck à proa.
- `sparSvg`: cilindro vertical longo + deck topo.
- `ahvSvg` (existia): refinado para uso como SVG image em AHV mid-line.
- `bargeSvg` (existia): reutilizado para Barge/MODU.
- Dispatcher `getVesselSvg(vessel_type, color)` com mapeamento conservador.

## Suite numérica

- Backend: 954 → 971 passed (+17). Zero regressão.
- Frontend: 207 passed (estabilidade preservada — testes vessel-editor atualizados para QueryClientProvider).

## Pendências v1.4+

1. Catálogo expandido com vessels comerciais reais (Damen, ULSTEIN, Bourbon).
2. Render 3D do casco com perspectiva (não 2D plano).
3. Auto-orientação do casco baseada na linha de mooring.
4. SVGs adicionais (Heavy Lift Vessel, Pipelay, Crane Vessel).
5. Multi-vessel por caso (hoje 1 vessel host).

## Próximos passos

1. PR para main com 8 commits.
2. Deploy SSH + smoke prod.
3. Tag `v1.3.0` (bump minor: catálogo novo + UX vessel completo).
4. Atualizar CLAUDE.md + decisões fechadas + CHANGELOG.
