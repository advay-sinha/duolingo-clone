/**
 * The learner's headline counters: streak, gems, hearts, XP.
 *
 * Purely presentational — it takes a `UserStats` object and renders it. **No
 * value here is computed.** Hearts are not derived from lesson activity, the
 * streak is not inferred from dates, and XP is not summed from anything: all
 * four come straight from `GET /users/me/stats`, which reads the `user_stats`
 * row the backend owns.
 */

import type { UserStats } from "@/lib/api/types";

function Counter({
  label,
  value,
  color,
  children,
}: {
  label: string;
  value: string;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="flex items-center gap-1.5"
      // The glyph is decorative; this sentence is what a screen reader gets.
      aria-label={`${value} ${label}`}
    >
      <span className={color} aria-hidden="true">
        {children}
      </span>
      <span className={`text-headline-sm tabular-nums ${color}`}>{value}</span>
    </div>
  );
}

export function StatsBar({ stats }: { stats: UserStats }) {
  return (
    <div className="flex items-center gap-4 sm:gap-6">
      <Counter label="day streak" value={String(stats.current_streak)} color="text-orange">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
          <path d="M13 2c.5 3.5-1.5 5-3 6.5S7 12 7 14a5 5 0 0 0 10 0c0-2.5-1.5-4-2.5-5.5C13.4 6.9 13 4.4 13 2zm-1 12a2.5 2.5 0 0 0 0 5 2.5 2.5 0 0 0 0-5z" />
        </svg>
      </Counter>

      <Counter label="gems" value={String(stats.gems)} color="text-blue">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
          <path d="M6 3h12l3 6-9 12L3 9l3-6zm1.2 2L5.4 8.5h13.2L16.8 5H7.2z" />
        </svg>
      </Counter>

      <Counter
        label={`of ${stats.max_hearts} hearts`}
        value={String(stats.hearts)}
        color="text-red"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 21s-7.5-4.7-9.3-9A5.2 5.2 0 0 1 12 6.5 5.2 5.2 0 0 1 21.3 12c-1.8 4.3-9.3 9-9.3 9z" />
        </svg>
      </Counter>

      <Counter
        label="total XP"
        value={String(stats.total_xp)}
        color="text-gold-depth"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
          <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8z" />
        </svg>
      </Counter>
    </div>
  );
}

/**
 * Daily-goal progress toward `daily_goal`.
 *
 * Shown separately from the counters because it is a *goal*, not a tally. The
 * ratio is computed for the bar's width only — both numbers come from the API,
 * and the server owns when `daily_xp` resets.
 */
export function DailyGoal({ stats }: { stats: UserStats }) {
  const percent =
    stats.daily_goal > 0
      ? Math.min(100, Math.round((stats.daily_xp / stats.daily_goal) * 100))
      : 0;
  const met = stats.daily_xp >= stats.daily_goal;

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-label-md uppercase text-text-secondary">
          Daily goal
        </span>
        <span className="text-body-sm tabular-nums text-text-secondary">
          {stats.daily_xp} / {stats.daily_goal} XP
        </span>
      </div>
      <div
        className="mt-2 h-3 overflow-hidden rounded-full bg-border"
        role="progressbar"
        aria-valuenow={stats.daily_xp}
        aria-valuemin={0}
        aria-valuemax={stats.daily_goal}
        aria-label="Daily XP goal"
      >
        <div
          className={`h-full rounded-full transition-[width] duration-700 ${met ? "bg-gold" : "bg-green"}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      {met && (
        <p className="mt-2 text-body-sm text-gold-depth">Goal reached today.</p>
      )}
    </div>
  );
}
