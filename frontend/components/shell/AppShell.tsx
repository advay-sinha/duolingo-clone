/**
 * The application chrome: sidebar, header, bottom navigation, content well.
 *
 * **A component, not a Next.js layout — and that is deliberate.** The lesson
 * player lives at `/learn/lesson/[lessonId]`, nested *under* `/learn`. An
 * `app/learn/layout.tsx` would therefore wrap the lesson player too, and Stitch
 * is explicit that the lesson is a chrome-free focus mode. Making the shell a
 * component means each screen opts in by rendering it, and the lesson simply
 * does not — no route groups, no conditional rendering, no `usePathname` checks.
 *
 * A Server Component: it holds no state and reads no browser API. Only the two
 * navigation pieces are client components, because they need the current path.
 */

import type { UserStats } from "@/lib/api/types";

import { MobileBottomNav } from "./MobileBottomNav";
import { Sidebar } from "./Sidebar";
import { StatsBar } from "./StatsBar";

interface Props {
  /** Omitted when stats could not be loaded; the header simply renders empty. */
  stats?: UserStats | null;
  children: React.ReactNode;
}

export function AppShell({ stats, children }: Props) {
  return (
    <div className="min-h-dvh">
      <Sidebar />

      {/* Offset by the sidebar on desktop; full width below it. */}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 border-b-2 border-border bg-surface/95 backdrop-blur">
          <div className="mx-auto flex h-16 max-w-content items-center justify-between gap-4 px-4">
            {/* The wordmark only appears where the sidebar is hidden, so it is
                never shown twice. */}
            <span className="text-headline-md lowercase text-green lg:hidden">
              duolingo
            </span>
            <div className="ml-auto">{stats && <StatsBar stats={stats} />}</div>
          </div>
        </header>

        {/* Bottom padding clears the mobile tab bar. */}
        <main className="mx-auto w-full max-w-content px-4 pb-24 pt-6 lg:pb-12">
          {children}
        </main>
      </div>

      <MobileBottomNav />
    </div>
  );
}
