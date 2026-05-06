/**
 * Smoke do ImportedModelCard (Sprint 1 / v1.1.0).
 *
 * Verifica:
 *  - Render nulo quando todos os 3 blocos estão vazios.
 *  - Vessel block renderiza nome + campos populados.
 *  - Current block renderiza N layers e mostra Cd/ρ quando presentes.
 *  - Metadata block separa source_* (badges) de chaves operacionais.
 *  - Badge "QMoor 0.8.0" aparece quando metadata.source_format está set.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ImportedModelCard } from '@/components/common/ImportedModelCard'

describe('ImportedModelCard', () => {
  it('retorna null quando tudo vazio', () => {
    const { container } = render(<ImportedModelCard />)
    expect(container.firstChild).toBeNull()
  })

  it('renderiza vessel com nome e LOA', () => {
    render(
      <ImportedModelCard
        defaultExpanded
        vessel={{
          name: 'P-77',
          vessel_type: 'Semisubmersible',
          loa: 120.0,
          draft: 22.0,
          heading_deg: 45.0,
        }}
      />,
    )
    expect(screen.getByText(/P-77/)).toBeTruthy()
    expect(screen.getByText('120.0 m')).toBeTruthy()
    expect(screen.getByText('22.0 m')).toBeTruthy()
    expect(screen.getByText('45°')).toBeTruthy()
  })

  it('renderiza current profile com N layers + Cd/ρ', () => {
    render(
      <ImportedModelCard
        defaultExpanded
        currentProfile={{
          layers: [
            { depth: 0, speed: 1.5 },
            { depth: 100, speed: 0.8 },
            { depth: 300, speed: 0.1 },
          ],
          drag_coefficient: 1.2,
          water_density: 1025,
        }}
      />,
    )
    expect(screen.getByText(/3 layers/)).toBeTruthy()
    expect(screen.getByText('1.50')).toBeTruthy()
    expect(screen.getByText('0.10')).toBeTruthy()
    expect(screen.getByText(/Cd = 1\.2/)).toBeTruthy()
    expect(screen.getByText(/ρ = 1025/)).toBeTruthy()
  })

  it('renderiza metadata operacional', () => {
    render(
      <ImportedModelCard
        defaultExpanded
        metadata={{
          rig: 'P-77',
          location: 'Bacia de Santos',
          source_format: 'qmoor_0_8',
        }}
      />,
    )
    expect(screen.getByText('rig')).toBeTruthy()
    expect(screen.getByText('P-77')).toBeTruthy()
    expect(screen.getByText('Bacia de Santos')).toBeTruthy()
    // source_format não aparece como linha — vai pra badge
    expect(screen.getByText(/format: qmoor_0_8/)).toBeTruthy()
  })

  it('badge QMoor 0.8.0 aparece quando source_format=qmoor_0_8', () => {
    render(
      <ImportedModelCard
        metadata={{ source_format: 'qmoor_0_8', rig: 'P-77' }}
      />,
    )
    expect(screen.getByText('QMoor 0.8.0')).toBeTruthy()
  })

  it('lida com vessel só com nome (sem outros campos)', () => {
    render(
      <ImportedModelCard defaultExpanded vessel={{ name: 'Anonymous Hull' }} />,
    )
    expect(screen.getByText(/Anonymous Hull/)).toBeTruthy()
    expect(screen.getByText(/Apenas o nome registrado/)).toBeTruthy()
  })

  it('default colapsado: mostra summary inline mas oculta blocos', () => {
    render(
      <ImportedModelCard
        metadata={{ rig: 'P-77', source_format: 'qmoor_0_8' }}
        vessel={{ name: 'Test', loa: 100 }}
      />,
    )
    // Header sempre visível com badges + summary
    expect(screen.getByText('Modelo importado')).toBeTruthy()
    expect(screen.getByText('QMoor 0.8.0')).toBeTruthy()
    expect(screen.getByText(/clique para expandir/)).toBeTruthy()
    // Summary inline mostra rig + vessel (truncado a 3 itens)
    expect(screen.getByText(/Rig P-77/)).toBeTruthy()
    // Mas blocos detalhados NÃO devem estar renderizados
    expect(screen.queryByText('120.0 m')).toBeNull()
    expect(screen.queryByText(/Apenas o nome registrado/)).toBeNull()
  })
})
