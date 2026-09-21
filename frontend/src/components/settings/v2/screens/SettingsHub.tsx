/**
 * SettingsHub — searchable browse view of all hub groups.
 *
 * Deliberately does NOT trigger a device fetch when it mounts.  Groups
 * only load their fields when the user opens them.  This is the "on
 * demand" half of the fetch strategy.
 */
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { DeviceProfile, Section } from "../profiles/types";
import { GroupCard, ScreenHeader } from "../primitives";

function countLabel(section: Section): string {
  if (section.kind === "schedule") {
    return `${section.windowCount} window${section.windowCount === 1 ? "" : "s"}`;
  }
  return `${section.fields.length} setting${section.fields.length === 1 ? "" : "s"}`;
}

function matchesQuery(section: Section, query: string): boolean {
  if (section.title.toLowerCase().includes(query)) return true;
  if (section.kind === "schedule") {
    return section.windowFields.some((f) => f.label.toLowerCase().includes(query));
  }
  return section.fields.some((f) => f.label.toLowerCase().includes(query));
}

export function SettingsHub({
  profile,
  isSectionDirty,
  onOpenGroup,
  onBack,
}: {
  profile: DeviceProfile;
  isSectionDirty: (sectionId: string) => boolean;
  onOpenGroup: (id: string) => void;
  onBack: () => void;
}) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();

  const groups = useMemo(() => {
    const all = profile.hubGroupIds
      .map((id) => ({ id, section: profile.sections[id] }))
      .filter((g) => !!g.section);
    if (!q) return all;
    return all.filter((g) => matchesQuery(g.section as Section, q));
  }, [profile, q]);

  return (
    <div className="min-h-screen pb-16">
      <ScreenHeader onBack={onBack} title="All settings" subtitle={profile.name} />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 flex flex-col gap-4">
        <div className="relative">
          <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search settings…"
            className="w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 pl-9 pr-3 py-3 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
          />
        </div>
        {groups.length === 0 ? (
          <p className="text-[13px] text-zinc-400 text-center py-10">
            No settings match "{query}".
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {groups.map(({ id, section }) => (
              <GroupCard
                key={id}
                icon={section!.icon}
                title={section!.title}
                description={section!.description}
                countLabel={countLabel(section!)}
                installer={section!.tier === "installer"}
                dirty={isSectionDirty(id)}
                onOpen={() => onOpenGroup(id)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
