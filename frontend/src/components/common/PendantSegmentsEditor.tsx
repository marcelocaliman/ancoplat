import { Plus, Trash2 } from 'lucide-react'
import {
  Controller,
  useFieldArray,
  type Control,
  type Path,
} from 'react-hook-form'
import { LineTypePicker } from '@/components/common/LineTypePicker'
import type { LineTypeOutput } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { CaseFormValues } from '@/lib/caseSchema'

type T = CaseFormValues

export interface PendantSegmentsEditorProps {
  control: Control<T>
  /** Caminho até o LineAttachment, ex: "attachments.0". */
  attachmentPath: string
}

/**
 * Editor compacto de pendant multi-trecho (até 5 segmentos).
 *
 * Quando o pendant é uma única chain ou wire, basta usar os campos
 * pendant_line_type/pendant_diameter no AttachmentAdvancedDialog
 * (que ficam fora deste editor). Quando há composição (ex.: chain
 * pendant + wire pendant + chain pendant), use ESTE editor.
 *
 * Convenção de ordem: trecho 0 é o que conecta diretamente à linha
 * principal; trecho N-1 é o que se conecta ao corpo (boia/clump).
 *
 * Modelo: cada trecho usa LineTypePicker (catálogo) — ao selecionar,
 * autopreenche line_type, category, diameter, w (wet_weight),
 * dry_weight, EA e MBL.
 */
export function PendantSegmentsEditor({
  control,
  attachmentPath,
}: PendantSegmentsEditorProps) {
  const arr = useFieldArray<T>({
    control,
    name: `${attachmentPath}.pendant_segments` as never,
  })

  const handlePick = (index: number, lt: LineTypeOutput | null) => {
    if (lt == null) return
    // Autopreenche todos os campos do catálogo no trecho selecionado.
    // Length não vem do catálogo — usuário sempre digita.
    arr.update(index, {
      ...((arr.fields[index] as unknown) as object),
      line_type: lt.line_type,
      category: lt.category,
      diameter: lt.diameter,
      w: lt.wet_weight,
      dry_weight: lt.dry_weight,
      EA: lt.qmoor_ea ?? lt.gmoor_ea ?? null,
      MBL: lt.break_strength,
    } as never)
  }

  return (
    <div className="col-span-2 mt-2 rounded-md border border-border/60 p-2">
      <div className="mb-2 flex items-center justify-between">
        <Label className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Pendant multi-trecho
        </Label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-6 gap-1 text-[10px]"
          onClick={() =>
            arr.append({
              length: 1.0,
              line_type: null,
              category: null,
              diameter: null,
              w: null,
              dry_weight: null,
              EA: null,
              MBL: null,
              material_label: null,
            } as never)
          }
          disabled={arr.fields.length >= 5}
        >
          <Plus className="h-3 w-3" /> Trecho
        </Button>
      </div>
      {arr.fields.length === 0 ? (
        <p className="text-[10px] text-muted-foreground">
          Sem trechos. Use os campos abaixo para pendant simples (1
          trecho), ou adicione aqui para pendant composto (2+ trechos).
        </p>
      ) : (
        <div className="space-y-1.5">
          {arr.fields.map((f, i) => (
            <div
              key={f.id}
              className="grid grid-cols-[1fr,80px,28px] items-center gap-1.5"
            >
              <Controller
                control={control}
                name={
                  `${attachmentPath}.pendant_segments.${i}.line_type` as Path<T>
                }
                render={({ field: fieldType }) => (
                  <Controller
                    control={control}
                    name={
                      `${attachmentPath}.pendant_segments.${i}.diameter` as Path<T>
                    }
                    render={({ field: fieldDiam }) => (
                      <LineTypePicker
                        value={
                          fieldType.value
                            ? ({
                                id: -1,
                                line_type: String(fieldType.value),
                                category: 'Wire',
                                diameter:
                                  (fieldDiam.value as number | null) ?? 0,
                                break_strength: 0,
                                wet_weight: 0,
                                dry_weight: 0,
                                modulus: 0,
                                seabed_friction_cf: 0,
                                data_source: 'manual',
                              } as never)
                            : null
                        }
                        onChange={(lt) => handlePick(i, lt)}
                        className="h-7"
                      />
                    )}
                  />
                )}
              />
              <Controller
                control={control}
                name={
                  `${attachmentPath}.pendant_segments.${i}.length` as Path<T>
                }
                render={({ field }) => (
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    value={(field.value as number | null) ?? ''}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value)
                      field.onChange(Number.isFinite(v) ? v : null)
                    }}
                    placeholder="L (m)"
                    className="h-7 font-mono text-[11px]"
                  />
                )}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-danger"
                onClick={() => arr.remove(i)}
                aria-label={`Remover trecho ${i + 1}`}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          ))}
          <p className="text-[9px] text-muted-foreground">
            Ordem: trecho 0 = mais próximo da linha principal · último =
            mais próximo do corpo.
          </p>
        </div>
      )}
    </div>
  )
}
