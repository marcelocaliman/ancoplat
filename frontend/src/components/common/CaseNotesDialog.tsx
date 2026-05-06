import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

export interface CaseNotesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Notas atuais do form state. */
  value: string
  /** Callback ao salvar — aplica via setValue('description', ...). */
  onSave: (next: string) => void
}

/**
 * Modal só para edição de Notas do caso (description).
 *
 * Abre via botão "📝 Notas" no topbar. Modal é não-bloqueante:
 * cancelar descarta mudanças, aplicar atualiza form state.
 *
 * Atalho Cmd+Enter (Ctrl+Enter no Win/Linux) também salva.
 */
export function CaseNotesDialog({
  open,
  onOpenChange,
  value,
  onSave,
}: CaseNotesDialogProps) {
  const [draft, setDraft] = useState(value)

  // Sincroniza draft quando abre o modal (pega valor atual)
  useEffect(() => {
    if (open) setDraft(value)
  }, [open, value])

  const handleSave = () => {
    onSave(draft)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="text-sm">Notas do caso</DialogTitle>
          <DialogDescription className="text-[11px]">
            Premissas de projeto, datas, referências cruzadas. Markdown
            básico aceito; renderiza como texto puro no Memorial PDF.
          </DialogDescription>
        </DialogHeader>

        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault()
              handleSave()
            }
          }}
          rows={8}
          placeholder="Notas sobre o caso, condições de projeto, premissas, datas…"
          className="resize-none font-sans text-[12px]"
          autoFocus
        />

        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={handleSave}
          >
            Aplicar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
