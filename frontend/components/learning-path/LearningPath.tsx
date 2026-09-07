"use client";

/**
 * The learning path: units, each with its winding column of skill nodes.
 *
 * The only stateful thing on this screen is *which skill card is open* — a
 * single `useState`. Everything else is server data passed down as props: the
 * page loads the path once and hands it over, so no `SkillNode` fetches
 * anything and there are no N+1 requests.
 *
 * The unlock rule lives entirely in the backend's `PathService`. This component
 * renders `skill.state` and never asks why.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";

import type { CoursePathResponse, SkillNode as SkillNodeData } from "@/lib/api/types";
import { isSkillPlayable, nodeOffset, selectNextLesson } from "@/lib/learn/path";

import { SkillCard } from "./SkillCard";
import { SkillNode } from "./SkillNode";
import { UnitBanner } from "./UnitBanner";

export function LearningPath({ path }: { path: CoursePathResponse }) {
  const router = useRouter();
  const [selected, setSelected] = useState<SkillNodeData | null>(null);

  function handleSelect(skill: SkillNodeData) {
    // Locked skills render disabled, so this is belt-and-braces: even a
    // synthetic click cannot open a lesson the server has not unlocked.
    if (!isSkillPlayable(skill)) return;
    setSelected(skill);
  }

  function handleStart() {
    if (!selected) return;
    const lesson = selectNextLesson(selected);
    if (!lesson) return;
    router.push(`/learn/lesson/${lesson.id}`);
  }

  if (path.units.length === 0) {
    return (
      <div className="card p-8 text-center">
        <p className="text-headline-sm text-text">This course has no units yet.</p>
        <p className="mt-1 text-body-md text-text-secondary">
          Seed the database to add course content.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-10">
      {path.units.map((unit) => (
        <section key={unit.id} aria-labelledby={`unit-${unit.id}`}>
          <div id={`unit-${unit.id}`}>
            <UnitBanner unit={unit} />
          </div>

          {unit.skills.length === 0 ? (
            <p className="mt-6 text-center text-body-md text-text-secondary">
              No skills in this unit yet.
            </p>
          ) : (
            <ul className="mt-8 flex flex-col items-center gap-8">
              {unit.skills.map((skill, index) => (
                <SkillNode
                  key={skill.id}
                  skill={skill}
                  offset={nodeOffset(index)}
                  onSelect={handleSelect}
                />
              ))}
            </ul>
          )}
        </section>
      ))}

      {selected && (
        <SkillCard
          skill={selected}
          lesson={selectNextLesson(selected)}
          onStart={handleStart}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
