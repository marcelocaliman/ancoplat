import { Pencil } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

export interface EditableCaseNameProps {
  /** Valor atual do nome (do form state). */
  value: string
  /** Callback ao confirmar edição (Enter ou blur). Recebe o novo valor. */
  onChange: (next: string) => void
  /** ID do caso (#18) — mostrado pequeno ao lado do nome. */
  caseId?: number | string
  /** Marca como inválido (e.g. nome vazio). */
  invalid?: boolean
  /** Mensagem de erro (tooltip). */
  errorMessage?: string
  /** Largura máxima do display (truncate). Default 280px. */
  maxWidth?: number
}

/**
 * Nome do caso editável inline no breadcrumb.
 *
 * Display: texto + ícone pencil pequeno à direita + "#18" em
 * text-muted ao lado.
 * Click ou Enter (focado): vira input editável.
 * Enter ou blur no input: salva.
 * Esc: cancela.
 */
export function EditableCaseName({
  value,
  onChange,
  caseId,
  invalid,
  errorMessage,
  maxWidth = 280,
}: EditableCaseNameProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const inputRef = useRef<HTMLInputElement | null>(null)

  // Sincroniza draft quando entra em modo edição (pega valor atual)
  useEffect(() => {
    if (editing) {
      setDraft(value)
      // autofocus + select all após render
      requestAnimationFrame(() => {
        inputRef.current?.focus()
        inputRef.current?.select()
      })
    }
  }, [editing, value])

  const commit = () => {
    const trimmed = draft.trim()
    if (trimmed && trimmed !== value) {
      onChange(trimmed)
    }
    setEditing(false)
  }

  const cancel = () => {
    setDraft(value)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1.5">
        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              commit()
            } else if (e.key === 'Escape') {
              e.preventDefault()
              cancel()
            }
          }}
          maxLength={120}
          aria-label="Nome do caso"
          className="h-7 rounded-md border border-input bg-background px-2 text-sm font-medium text-foreground outline-none ring-2 ring-ring"
          style={{ width: maxWidth }}
        />
        {caseId != null && (
          <span className="font-mono text-[11px] text-muted-foreground">
            #{caseId}
          </span>
        )}
      </div>
    )
  }

  const display = value || 'Sem nome'
  const isEmpty = !value
  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      title={errorMessage ?? 'Clique para editar o nome do caso'}
      aria-label="Editar nome do caso"
      className={cn(
        'group flex items-center gap-1.5 rounded-md px-1 py-0.5 text-sm transition-colors',
        'hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        (invalid || isEmpty) && 'text-warning',
        !invalid && !isEmpty && 'font-medium text-foreground',
      )}
    >
      <span
        className="truncate"
        style={{ maxWidth }}
      >
        {display}
      </span>
      <Pencil className="h-3 w-3 shrink-0 text-muted-foreground/60 transition-colors group-hover:text-foreground" />
      {caseId != null && (
        <span className="font-mono text-[11px] text-muted-foreground">
          #{caseId}
        </span>
      )}
    </button>
  )
}
