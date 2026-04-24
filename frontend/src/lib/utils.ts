import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Helper padrão shadcn: combina clsx + tailwind-merge.
 * Permite `cn('p-2', isActive && 'bg-primary', className)` com override correto.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/** Formata número como tração em kN (valor em N). */
export function fmtForceKN(valueN: number, digits = 2): string {
  return `${(valueN / 1000).toLocaleString('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} kN`
}

/** Formata distância em m (valor em m). */
export function fmtMeters(value: number, digits = 2): string {
  return `${value.toLocaleString('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} m`
}

/** Formata número livre com separador pt-BR. */
export function fmtNumber(value: number, digits = 2): string {
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/** Percentual: 0.397 → "39.7%" */
export function fmtPercent(value: number, digits = 1): string {
  return `${(value * 100).toLocaleString('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}%`
}
