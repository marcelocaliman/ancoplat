"""
Geração do relatório técnico em PDF (F2.7).

Usa reportlab (puro Python, sem headless Chrome). Layout minimalista
conforme Seção 8 do plano F2:
  1. Header: nome do caso, timestamp, versão do solver
  2. Disclaimer obrigatório (Seção 10 do Documento A v2.2)
  3. Tabela de inputs
  4. Gráfico de perfil 2D (matplotlib → PNG → embed)
  5. Tabela de resultados
  6. Status de convergência + mensagem

Gera bytes em memória; router decide como devolver.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

# matplotlib precisa de backend não-interativo antes de importar pyplot
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.api.db.models import CaseRecord, ExecutionRecord
from backend.api.routers.health import SOLVER_VERSION
from backend.api.schemas.cases import CaseInput
from backend.solver.types import SolverResult

# Disclaimer obrigatório — Seção 10 do Documento A v2.2
DISCLAIMER = (
    "Os resultados apresentados são estimativas de análise estática "
    "simplificada e não substituem análise de engenharia realizada com "
    "ferramenta validada, dados certificados, premissas aprovadas e revisão "
    "por responsável técnico habilitado."
)


def _profile_png(result: SolverResult) -> bytes:
    """Gera o perfil 2D da linha em PNG (bytes)."""
    fig, ax = plt.subplots(figsize=(7.0, 3.5), dpi=120)
    ax.plot(result.coords_x, result.coords_y, color="#1f77b4", linewidth=1.6)
    ax.axhline(0.0, color="#8b6914", linewidth=0.7, linestyle="--", alpha=0.6)
    ax.scatter([0.0], [0.0], color="#d62728", zorder=5, label="Âncora")
    ax.scatter(
        [result.total_horz_distance], [result.endpoint_depth],
        color="#2ca02c", zorder=5, label="Fairlead",
    )
    if result.dist_to_first_td is not None and result.dist_to_first_td > 0:
        ax.scatter(
            [result.dist_to_first_td], [0.0],
            color="#9467bd", zorder=5, label="Touchdown",
        )
    ax.set_xlabel("Distância horizontal (m)")
    ax.set_ylabel("Elevação (m)")
    ax.set_title("Perfil 2D da linha")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _inputs_table_data(case_input: CaseInput) -> list[list[str]]:
    seg = case_input.segments[0]
    bc = case_input.boundary
    sb = case_input.seabed
    rows = [
        ["Grandeza", "Valor"],
        ["Nome do caso", case_input.name],
        ["Descrição", case_input.description or "—"],
        ["Modo", bc.mode.value],
        ["Input value", f"{bc.input_value:.3f}"],
        ["Lâmina d'água (m)", f"{bc.h:.2f}"],
        ["Comprimento (m)", f"{seg.length:.2f}"],
        ["Peso submerso (N/m)", f"{seg.w:.2f}"],
        ["EA (N)", f"{seg.EA:.3e}"],
        ["MBL (N)", f"{seg.MBL:.3e}"],
        ["Categoria", seg.category or "—"],
        ["Tipo de linha", seg.line_type or "—"],
        ["μ atrito seabed", f"{sb.mu:.2f}"],
        ["Perfil de critério", case_input.criteria_profile.value],
    ]
    return rows


def _results_table_data(result: SolverResult) -> list[list[str]]:
    rows = [
        ["Grandeza", "Valor"],
        ["Status", result.status.value],
        ["Alert level", result.alert_level.value],
        ["Tração no fairlead (kN)", f"{result.fairlead_tension / 1000:.2f}"],
        ["Tração na âncora (kN)", f"{result.anchor_tension / 1000:.2f}"],
        ["H (horizontal) (kN)", f"{result.H / 1000:.2f}"],
        ["Distância horizontal total (m)", f"{result.total_horz_distance:.2f}"],
        ["Profundidade endpoint (m)", f"{result.endpoint_depth:.2f}"],
        ["Comprimento não-esticado (m)", f"{result.unstretched_length:.3f}"],
        ["Comprimento esticado (m)", f"{result.stretched_length:.3f}"],
        ["Alongamento (m)", f"{result.elongation:.4f}"],
        ["Comprimento suspenso (m)", f"{result.total_suspended_length:.3f}"],
        ["Comprimento apoiado (m)", f"{result.total_grounded_length:.3f}"],
        [
            "Distância até touchdown (m)",
            (f"{result.dist_to_first_td:.3f}" if result.dist_to_first_td else "—"),
        ],
        ["Utilização (T_fl/MBL)", f"{result.utilization:.4f}"],
        ["Iterações do solver", str(result.iterations_used)],
    ]
    return rows


def _base_table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#888888")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
    ])


def _alert_color(alert_level: str) -> colors.Color:
    return {
        "ok": colors.HexColor("#2d7a2d"),
        "yellow": colors.HexColor("#d1a200"),
        "red": colors.HexColor("#b33a3a"),
        "broken": colors.HexColor("#8b0000"),
    }.get(alert_level, colors.black)


def build_pdf(
    case_rec: CaseRecord, execution: Optional[ExecutionRecord]
) -> bytes:
    """
    Gera o PDF em memória e retorna os bytes.

    Se `execution` é None, produz um relatório só com os inputs e um
    aviso de que o caso ainda não foi resolvido.
    """
    case_input = CaseInput.model_validate_json(case_rec.input_json)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"QMoor — {case_input.name}",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="HeaderSmall", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#555555"),
    ))
    styles.add(ParagraphStyle(
        name="DisclaimerBox", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#606060"),
        borderPadding=6, borderColor=colors.HexColor("#cccccc"),
        borderWidth=0.5, leading=10,
    ))

    story = []

    # --- Header ---
    story.append(Paragraph(f"<b>QMoor Web — Relatório de análise</b>", styles["Title"]))
    story.append(Paragraph(
        f"Caso: <b>{case_input.name}</b> (id {case_rec.id})",
        styles["Heading3"],
    ))
    now = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M:%S %Z")
    story.append(Paragraph(
        f"Gerado em {now} — Solver versão {SOLVER_VERSION}",
        styles["HeaderSmall"],
    ))
    story.append(Spacer(1, 0.5 * cm))

    # --- Disclaimer ---
    story.append(Paragraph(f"<b>Disclaimer técnico</b>", styles["Heading4"]))
    story.append(Paragraph(DISCLAIMER, styles["DisclaimerBox"]))
    story.append(Spacer(1, 0.4 * cm))

    # --- Inputs ---
    story.append(Paragraph("<b>Entradas</b>", styles["Heading3"]))
    inputs_table = Table(_inputs_table_data(case_input), colWidths=[6 * cm, 8 * cm])
    inputs_table.setStyle(_base_table_style())
    story.append(inputs_table)
    story.append(Spacer(1, 0.5 * cm))

    if execution is None:
        # Sem resultado ainda
        story.append(Paragraph(
            "Nenhuma execução do solver disponível para este caso. "
            "Execute POST /cases/{id}/solve antes de gerar o relatório.",
            styles["Normal"],
        ))
        doc.build(story)
        return buf.getvalue()

    result = SolverResult.model_validate_json(execution.result_json)

    # --- Gráfico ---
    story.append(PageBreak())
    story.append(Paragraph("<b>Perfil da linha</b>", styles["Heading3"]))
    png_bytes = _profile_png(result)
    story.append(Image(io.BytesIO(png_bytes), width=17 * cm, height=8.5 * cm))
    story.append(Spacer(1, 0.4 * cm))

    # --- Resultados ---
    story.append(Paragraph("<b>Resultados</b>", styles["Heading3"]))
    results_table = Table(_results_table_data(result), colWidths=[7 * cm, 7 * cm])
    results_table.setStyle(_base_table_style())
    # Pinta linha do alert_level
    for i, row in enumerate(_results_table_data(result)):
        if row[0] == "Alert level":
            results_table.setStyle(TableStyle([
                ("TEXTCOLOR", (1, i), (1, i), _alert_color(result.alert_level.value)),
                ("FONTNAME", (1, i), (1, i), "Helvetica-Bold"),
            ]))
    story.append(results_table)
    story.append(Spacer(1, 0.4 * cm))

    # --- Convergência ---
    story.append(Paragraph(
        f"<b>Mensagem do solver:</b> {result.message or '—'}",
        styles["Normal"],
    ))

    doc.build(story)
    return buf.getvalue()


__all__ = ["build_pdf", "DISCLAIMER"]
