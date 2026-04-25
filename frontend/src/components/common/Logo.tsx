import { cn } from '@/lib/utils'

/**
 * Wordmark AncoPlat + ícone SVG de curva de catenária estilizada.
 * `compact` = mostra apenas o ícone (para sidebar colapsada).
 */
export function Logo({
  compact = false,
  className,
}: {
  compact?: boolean
  className?: string
}) {
  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 text-primary',
        className,
      )}
      aria-label="AncoPlat"
    >
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        className="shrink-0"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <line
          x1="2"
          y1="18"
          x2="22"
          y2="18"
          stroke="currentColor"
          strokeWidth="1"
          strokeDasharray="2 2"
          opacity="0.5"
        />
        <path
          d="M2 17 Q 9 18, 15 12 T 22 4"
          stroke="currentColor"
          strokeWidth="1.75"
          fill="none"
          strokeLinecap="round"
        />
        <circle cx="2" cy="17" r="1.6" fill="currentColor" />
        <circle cx="22" cy="4" r="1.6" fill="currentColor" />
      </svg>
      {!compact && (
        <span className="inline-flex items-baseline whitespace-nowrap text-base leading-none tracking-tight">
          <span className="font-bold">Anco</span>
          <span className="font-light opacity-90">Plat</span>
        </span>
      )}
    </div>
  )
}
