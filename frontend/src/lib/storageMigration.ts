/**
 * Migração transparente de chaves do localStorage do app legado
 * (`qmoor-*`) para os nomes novos (`ancoplat-*`).
 *
 * **IMPORTANTE**: este módulo executa a migração como SIDE-EFFECT no
 * import (`runMigration()` chamada no escopo top-level do módulo). Por
 * isso `main.tsx` deve importar este arquivo ANTES dos stores zustand
 * com persist — caso contrário o middleware lê o localStorage com a
 * chave nova vazia antes da migração popular.
 */
const MIGRATIONS: Array<[oldKey: string, newKey: string]> = [
  ['qmoor-theme', 'ancoplat-theme'],
  ['qmoor-units', 'ancoplat-units'],
  ['qmoor-ui', 'ancoplat-ui'],
]

function runMigration(): void {
  if (typeof window === 'undefined' || !window.localStorage) return
  for (const [oldKey, newKey] of MIGRATIONS) {
    try {
      const newVal = localStorage.getItem(newKey)
      const oldVal = localStorage.getItem(oldKey)
      if (oldVal && !newVal) {
        localStorage.setItem(newKey, oldVal)
      }
      if (oldVal) localStorage.removeItem(oldKey)
    } catch {
      // SecurityError em modo private/incognito — ignora
    }
  }
}

// Executa imediatamente no import. Idempotente — chaves antigas são
// removidas após copiar, então segunda execução não faz nada.
runMigration()
