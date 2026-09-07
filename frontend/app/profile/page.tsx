/**
 * `/profile` — the learner's identity, lifetime statistics and achievements.
 *
 * A Server Component, like the other shell screens. Two requests issued in
 * parallel: the composed profile and the achievement list. Every figure is
 * server-computed — the page does not total anything itself.
 */

import Link from "next/link";

import { AchievementCard } from "@/components/profile/AchievementCard";
import { DuoMascot } from "@/components/lesson/DuoMascot";
import { AppShell } from "@/components/shell/AppShell";
import { DailyGoal } from "@/components/shell/StatsBar";
import { LogoutButton } from "@/components/auth/LogoutButton";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { getAuthenticatedUser } from "@/lib/api/auth";
import { forwardedAuth, redirectIfUnauthenticated } from "@/lib/api/server";
import { getAchievements, getLearnerProfile } from "@/lib/api/users";
import type { AchievementListResponse, LearnerProfile } from "@/lib/api/types";

export const metadata = { title: "Profile · Duolingo Clone" };

export const dynamic = "force-dynamic";

async function load(): Promise<
  | {
      ok: true;
      profile: LearnerProfile;
      achievements: AchievementListResponse | null;
      email: string | null;
    }
  | { ok: false; message: string }
> {
  // Issued together: neither depends on the other, so awaiting them in sequence
  // only added a round trip. Achievements are a section, not the page — losing
  // them must not take the whole profile down, which is why this is
  // `allSettled` and not `all`.
  const auth = await forwardedAuth();
  // The email comes from `/auth/me` rather than being added to the profile
  // response. `UserSummary` is used in places that describe a learner in a list;
  // widening it would put an address one edit away from a screen it does not
  // belong on. Asking the endpoint whose entire job is "describe the caller to
  // themselves" keeps that boundary where it is.
  const [profile, achievements, account] = await Promise.allSettled([
    getLearnerProfile(auth),
    getAchievements(auth),
    getAuthenticatedUser(auth),
  ]);

  if (profile.status === "rejected") {
    const error: unknown = profile.reason;
    redirectIfUnauthenticated(error);
    return {
      ok: false,
      message:
        error instanceof Error ? error.message : "The API could not be reached.",
    };
  }

  return {
    ok: true,
    profile: profile.value,
    achievements: achievements.status === "fulfilled" ? achievements.value : null,
    email: account.status === "fulfilled" ? account.value.user.email : null,
  };
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div className="card flex flex-col gap-1 p-4">
      <span className={`text-headline-lg tabular-nums ${tone}`}>{value}</span>
      <span className="text-label-md uppercase text-text-secondary">{label}</span>
    </div>
  );
}

export default async function ProfilePage() {
  const result = await load();

  if (!result.ok) {
    return (
      <AppShell>
        <div className="mx-auto max-w-md py-16 text-center">
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-border/60">
            <span className="text-4xl" aria-hidden="true">
              ⚠️
            </span>
          </div>
          <h1 className="mt-4 text-headline-lg text-text">
            Could not load your profile
          </h1>
          <p className="mt-1 text-body-md text-text-secondary">{result.message}</p>
          <Link href="/profile" className="tactile btn-primary mt-5 inline-block">
            Try again
          </Link>
        </div>
      </AppShell>
    );
  }

  const { profile, achievements, email } = result;
  const { user, stats } = profile;

  return (
    <AppShell stats={stats}>
      <div className="mx-auto flex w-full max-w-path flex-col gap-8">
        {/* --- identity ------------------------------------------------- */}
        <header className="card flex items-center gap-4 p-5">
          <DuoMascot className="h-16 w-16 shrink-0" />
          <div className="min-w-0">
            <h1 className="text-headline-xl text-text">{user.display_name}</h1>
            <p className="text-body-md text-text-secondary">@{user.username}</p>
          </div>
        </header>

        <DailyGoal stats={stats} />

        {/* Settings live here rather than in a separate screen: two controls
            do not justify a settings system. */}
        <ThemeToggle />

        <section
          aria-labelledby="account-heading"
          className="card flex flex-col gap-3 p-4"
        >
          <h2 id="account-heading" className="text-headline-sm text-text">
            Account
          </h2>
          {/* The learner's own email, shown only here. It is deliberately absent
              from every response that describes one learner to another — see the
              leaderboard schema. */}
          {email && (
            <p className="text-body-sm text-text-secondary">{email}</p>
          )}
          <LogoutButton displayName={user.display_name} />
        </section>

        {/* --- lifetime statistics -------------------------------------- */}
        <section aria-labelledby="stats-heading" className="flex flex-col gap-3">
          <h2 id="stats-heading" className="text-headline-lg text-text">
            Statistics
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <StatCard
              label="Total XP"
              value={stats.total_xp.toLocaleString()}
              tone="text-gold-depth"
            />
            <StatCard
              label="Day streak"
              value={String(stats.current_streak)}
              tone="text-orange-depth"
            />
            <StatCard
              label="Longest streak"
              value={String(stats.longest_streak)}
              tone="text-orange-depth"
            />
            <StatCard
              label="Lessons done"
              value={String(profile.lessons_completed)}
              tone="text-green-depth"
            />
            <StatCard
              label="Crowns"
              value={String(profile.total_crowns)}
              tone="text-gold-depth"
            />
            <StatCard
              label="Perfect lessons"
              value={String(profile.perfect_lessons)}
              tone="text-blue-depth"
            />
            <StatCard
              label="Skills complete"
              value={String(profile.skills_completed)}
              tone="text-green-depth"
            />
            <StatCard
              label="Hearts"
              value={`${stats.hearts} / ${stats.max_hearts}`}
              tone="text-red"
            />
            <StatCard
              label="Gems"
              value={stats.gems.toLocaleString()}
              tone="text-blue-depth"
            />
          </div>
        </section>

        {/* --- achievements --------------------------------------------- */}
        <section aria-labelledby="achievements-heading" className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between gap-3">
            <h2 id="achievements-heading" className="text-headline-lg text-text">
              Achievements
            </h2>
            {achievements && (
              <span className="text-body-sm tabular-nums text-text-secondary">
                {achievements.unlocked_count} of {achievements.total_count}
              </span>
            )}
          </div>

          {achievements === null ? (
            <p className="card p-5 text-body-md text-text-secondary">
              Achievements could not be loaded right now.
            </p>
          ) : achievements.achievements.length === 0 ? (
            <p className="card p-5 text-body-md text-text-secondary">
              No achievements have been set up yet.
            </p>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2">
              {achievements.achievements.map((item) => (
                <AchievementCard key={item.id} item={item} />
              ))}
            </ul>
          )}
        </section>
      </div>
    </AppShell>
  );
}
