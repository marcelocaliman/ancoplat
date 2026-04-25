# Manual do Usuário — AncoPlat

> Versão do app: 0.1.0 (F4) · Última atualização: 25 de abril de 2026

---

## 1. O que é o AncoPlat

AncoPlat é um aplicativo local de **análise estática de linhas de
ancoragem offshore**. Você descreve um cabo (geometria, propriedades,
critério de utilização), o app resolve a equação da catenária elástica
com contato no seabed e atrito de Coulomb, e devolve tração no fairlead,
distribuição de tensões ao longo da linha, ângulos críticos e a
classificação operacional (OK / amarelo / vermelho / broken). Os
resultados foram validados contra o MoorPy (NREL) em 9 casos de
benchmark, com desvio < 1 % em força e < 0,5 % em geometria.

O aplicativo roda inteiramente em `localhost:5173` (UI) e `localhost:8000`
(API). Não envia dados a serviços externos.

---

## 2. Criando um caso (passo a passo)

### 2.1. Abrir o formulário

Caminhos equivalentes:

- Sidebar → "Casos" → botão **"Novo caso"**.
- Atalho de teclado **`Cmd+K`** → digite "novo caso" → Enter.
- Atalho rápido `g c` (vai para Casos) e clicar em "Novo".

### 2.2. Preencher metadados

A faixa superior compacta tem três campos:

- **Nome do caso** (obrigatório). Ex.: `BC-01 catenária suspensa`.
- **Critério de utilização**. Default `MVP_Preliminary`. Use `API_RP_2SK`
  para projetos formais. `UserDefined` libera os limites
  yellow/red/broken para você customizar.
- **Notas** (opcional, collapsible). Use para documentar o caso —
  premissas de projeto, datas, referências cruzadas.

### 2.3. Definir o segmento de linha

No card **Segmento de linha**:

1. Clique no seletor de catálogo no topo do card. Pesquise o tipo
   (ex.: `DiamondBlue`, `IWRCEIPS`, `R4Studless`). Ao escolher, os
   campos abaixo são preenchidos automaticamente em SI a partir do
   catálogo (522 entradas legacy_qmoor + suas customizadas).

2. Você pode editar manualmente se quiser:
   - **Comp.** (m): comprimento total da linha (não-esticado).
   - **Diâmetro** (m): nominal, só para metadados / relatório.
   - **Categoria**: Wire, Studded, Studless ou Poliéster — afeta
     defaults de atrito.
   - **Peso submerso** (N/m ou kgf/m): peso por metro com flutuação.
   - **Peso seco** (N/m ou kgf/m): metadado.
   - **EA** (N ou te): rigidez axial. **Atenção**: em sistema Metric
     o app espera `te` (tonelada-força). Em SI, espera `N`.
   - **MBL** (N ou te): Minimum Breaking Load.
   - **Módulo** (Pa): aparente, metadado.

> **Cuidado com unidades**: o seletor `Metric / SI` no canto superior
> direito controla todos os campos de força do app. Em Metric os
> chips dos inputs mostram `te` e `kgf/m`; em SI mostram `N` e `N/m`.
> O estado interno é sempre SI; só o display muda.

### 2.4. Definir as condições

No card **Condições**:

- **Lâmina d'água** (m): profundidade do seabed a partir da superfície.
- **Prof. fairlead** (m): profundidade do ponto de fixação no vessel
  abaixo da superfície. `0` = fairlead na superfície (caso clássico).
  Igual à lâmina = linha horizontal no fundo (caso laid line).
- **Modo**: `Tension` (você fornece T_fl, app calcula X) ou `Range`
  (você fornece X, app calcula T_fl).
- **T_fl (fairlead)** ou **X total**: o input do modo escolhido.
- **μ (atrito)**: coeficiente de Coulomb do seabed. Wire ~0,3,
  corrente ~0,7, poliéster ~0,25.

### 2.5. Visualizar antes de salvar

À medida que você preenche, o gráfico abaixo mostra o **preview ao
vivo** da catenária. Os 4 cards no rodapé trazem T_fl, geometria,
forças e status do solver. Não precisa salvar para testar combinações.

### 2.6. Salvar e calcular

- **Salvar**: persiste o caso sem rodar o solver (pode rodar depois).
- **Salvar e calcular**: persiste e cria a primeira execução. Você é
  redirecionado para a página de detalhe.

---

## 3. Lendo os resultados

A página de detalhe (`/cases/{id}`) tem 4 abas:

### 3.1. Visão geral

- **Gráfico 2D** com fairlead à esquerda (em x = 0) e âncora à direita.
  Eixo Y é elevação relativa à superfície do mar. Faixa cinza inferior
  é o seabed. Hover mostra coordenadas + tração local.
- **Análise de sensibilidade** (logo abaixo do gráfico): 3 sliders para
  T_fl, comprimento e μ, com ±50 % do baseline. Mover o slider dispara
  preview ao vivo no gráfico e nos cards. **Aplicar como nova execução**
  persiste os novos valores como Run #N+1; **Resetar** volta ao baseline.
- **6 cards categorizados**:
  - **Tração no fairlead**: valor primário + utilização (T_fl/MBL) +
    barra de gauge colorida.
  - **Geometria**: X, lâmina, profundidade do fairlead, drop, touchdown.
  - **Comprimentos**: L, L_esticado, L_suspenso, L_apoiado, ΔL, strain.
  - **Forças**: H, T_fl, T_anchor, V_fl, V_anchor, ΔT (atrito).
  - **Ângulos**: nos dois extremos, em graus, vs horizontal e vertical.
    O ângulo na âncora (departure angle) é crítico para
    dimensionamento de cravação.
  - **Convergência**: status do solver, iterações, mensagem.

### 3.2. Resultados detalhados

6 tabelas key-value com todos os números em alta precisão:
Forças, Geometria, Ângulos, Critério de utilização, Material e
segmento, Diagnóstico do solver. Use esta aba para conferir
manualmente ou copiar valores para um relatório externo.

### 3.3. Pontos discretizados

Tabela com 5.000 pontos ao longo da linha (limite default — pode ser
reduzido em `SolverConfig.n_plot_points` para benchmarks). Colunas:

| col | significado |
|---|---|
| `s (m)` | comprimento de arco a partir do fairlead |
| `x (m)` | posição horizontal (frame surface-relative) |
| `y (m)` | elevação (negativa = abaixo da superfície) |
| `prof. (m)` | profundidade absoluta = `−y` |
| `\|T\|` | módulo da tração local |
| `T_h`, `T_v` | componentes horizontal e vertical |
| `θ (°)` | ângulo da tangente vs horizontal |
| `estado` | `suspenso` (azul) ou `apoiado` (laranja) |

Render limitado a 200 linhas inicialmente (DOM com 5.000 trava o
navegador). Use o botão **CSV completo** para baixar todos os pontos
com cabeçalhos em SI.

### 3.4. Histórico

Cards de Run com numeração sequencial (`Run #ID`), badge **atual** no
mais recente, status, alert level e delta vs run anterior em cada
métrica (T_fl, X, utilização, iterações). Clicar em uma run faz os
gráficos e tabelas das outras abas refletirem aquela versão.

O backend mantém as 10 execuções mais recentes por caso.

---

## 4. Importar e exportar

### 4.1. Exportar

Na página de detalhe, menu `⋮` → **Exportar**:

- **`.moor` (métrico ou imperial)**: JSON compatível com a Seção 5.2
  do MVP v2 PDF do QMoor. Permite trocar casos com colegas.
- **JSON**: input + última execução em SI puro.
- **PDF**: relatório técnico com gráfico, métricas e tabelas. Só
  disponível depois da primeira execução.

Atalho rápido: botão `</> JSON` no header da página → modal com sub-abas
Input | Resultado e botão Copiar.

### 4.2. Importar

Página `/import-export`:

- **Cole JSON** no campo: o parser aceita o formato completo do QMoor
  0.8.x (`mooringLines[0]` ou `mooringLine`), tanto `inputParam`
  capitalizado quanto minúsculo, e unidades brasileiras (`te`, `kgf/m`).
- Se o `.moor` falhar, a mensagem indica exatamente qual campo está
  inválido (ex.: "v1 espera 1 segmento; recebeu 3").

---

## 5. Atalhos de teclado

| Atalho | Ação |
|---|---|
| `Cmd+K` (`Ctrl+K`) | Abrir paleta de comandos (busca global) |
| `?` | Mostrar diálogo de ajuda |
| `Cmd+B` (`Ctrl+B`) | Alternar sidebar |
| `g c` | Ir para Casos |
| `g a` | Ir para Catálogo |
| `g i` | Ir para Importar/Exportar |
| `g s` | Ir para Configurações |
| `Esc` | Fechar diálogos / paleta |

A paleta `Cmd+K` busca por nome em casos, tipos de linha, e oferece
ações rápidas (novo caso, alternar tema, alternar Metric/SI, abrir
ajuda). Use `↑↓` para navegar e `↵` para ativar.

---

## 6. FAQ

### 6.1. Por que meu caso retorna "T_fl insuficiente"?

`T_fl ≤ w·h` significa que a tração no fairlead é menor que o peso
da coluna d'água suspensa entre fairlead e seabed. Aumente T_fl,
reduza a lâmina ou troque por um cabo mais leve. O app calcula
`w·h` na mensagem de erro.

### 6.2. Por que aparece "strain final 11,8 % é fisicamente implausível"?

Quase sempre é input em unidade errada. Wire e correntes operacionais
têm strain < 1 %. Se chegou em 5 %+, provavelmente `EA` está em `te`
mas o app interpretou como `N` (10.000× menor que o real), ou `w` está
em `kgf/m` e foi lido como `N/m` (10× menor). Confira o seletor
Metric/SI no topo e os chips dos campos.

### 6.3. O que significa "Run #16 atual"?

`#16` é o id sequencial dessa execução no banco. **atual** marca a
última run; é a versão mostrada por default nas outras abas. Você pode
clicar em qualquer outra run para inspecioná-la.

### 6.4. Posso ter casos com fairlead afundado (semi-sub mooring)?

Sim, desde a F3. Defina `Prof. fairlead > 0`. O drop efetivo passa a
ser `lâmina − prof. fairlead`. Caso o drop fique zero (fairlead no
mesmo nível do seabed), o solver ativa o módulo `laid_line` (linha
horizontal com atrito puro, sem catenária).

### 6.5. Por que o gráfico do detalhe é igual ao da edição?

Porque o solver é o mesmo. A diferença é que na edição o gráfico é um
preview ao vivo (não persistido); na detalhe ele exibe a execução
salva. Use a Análise de sensibilidade na detalhe para fazer
ajustes pontuais sem alterar o caso.

### 6.6. Como sei que o solver convergiu?

Badges **Convergiu** + **OK/Yellow/Red** no topo do detalhe e dentro
do card "Convergência" (status, iterações, mensagem). Status possíveis:
`converged`, `ill_conditioned` (convergiu mas linha quase taut, alta
sensibilidade), `max_iterations`, `invalid_case`, `numerical_error`.

### 6.7. O que é "preview ao vivo" no detalhe?

Quando você mexe os sliders de Análise de sensibilidade, o gráfico
e cards mostram o resultado dos novos valores **sem salvar** no caso.
Um badge azul **preview ao vivo** sinaliza isso. Clique **Aplicar
como nova execução** para persistir, ou **Resetar** para voltar.

### 6.8. Como adiciono um cabo customizado ao catálogo?

Na página `/catalog`, botão **Novo tipo de linha**. As entradas com
`data_source = legacy_qmoor` (522 originais) são imutáveis; as
`user_input` podem ser editadas e removidas livremente.

### 6.9. Onde ficam os logs do solver?

`backend/data/logs/ancoplat.log` (rotação de 1 MB × 5 arquivos). Cada
execução grava uma linha:
`case_id=N status=converged alert=ok iterations=14 elapsed_ms=42.3`

### 6.10. Posso rodar a análise sem internet?

Sim, completamente. Tudo roda em `localhost`. A única exceção são os
fontes (Inter, JetBrains Mono) que vêm do `@fontsource` empacotado
junto com o frontend.

---

## 7. Disclaimer técnico

**Os resultados apresentados são estimativas de análise estática
simplificada e não substituem análise de engenharia realizada com
ferramenta validada, dados certificados, premissas aprovadas e
revisão por responsável técnico habilitado.**

O solver implementa catenária elástica 2D, corpo único homogêneo,
seabed plano com atrito de Coulomb. Não cobre:

- Ondas / corrente / vento (análise dinâmica).
- Linha multi-segmento (planejado para v2.1).
- Bóias intermediárias / clumps / horizontais (planejado para v2+).
- Análise de fadiga ULS/ALS/FLS (DNV formal).

Para projetos certificados use ferramentas validadas como OrcaFlex,
Flexcom, MoorPy ou similar.
