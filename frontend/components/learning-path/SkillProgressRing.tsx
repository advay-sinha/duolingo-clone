/**
 * The circular progress ring around a path node.
 *
 * Drawn with two SVG circles and `stroke-dasharray`, exactly as the Stitch
 * markup does. The fraction comes from `lessons_completed / total_lessons` —
 * the API sends the two counts and the client renders the ratio, so there is no
 * stored percentage anywhere in the system (backend ADR-21).
 *
 * Rotated −90° so progress starts at the top rather than at three o'clock.
 */

interface Props {
  /** 0 to 1. */
  fraction: number;
  /** Outer diameter in pixels. */
  size: number;
  color: string;
  children: React.ReactNode;
}

const RADIUS = 42;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function SkillProgressRing({ fraction, size, color, children }: Props) {
  const clamped = Math.max(0, Math.min(1, fraction));
  const offset = CIRCUMFERENCE * (1 - clamped);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg
        viewBox="0 0 100 100"
        className="absolute inset-0 -rotate-90"
        aria-hidden="true"
      >
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="transparent"
          stroke="var(--color-border)"
          strokeWidth="8"
        />
        {clamped > 0 && (
          <circle
            cx="50"
            cy="50"
            r={RADIUS}
            fill="transparent"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            className="transition-[stroke-dashoffset] duration-700 ease-out"
          />
        )}
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        {children}
      </div>
    </div>
  );
}
