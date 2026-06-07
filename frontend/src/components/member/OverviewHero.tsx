/**
 * OverviewHero — the cinematic, scroll-over-image hero for a member.
 *
 * The image is sticky (pinned to the top of the scroll container); the content
 * sheet below it rises up and *covers* the image as the coach scrolls — the
 * signature luxury "sheet over hero" motion. Member identity is set in large
 * editorial display type; key vitals read as quiet inline metrics.
 */

import type { MemberSummary } from "../../lib/api";
import { memberArt } from "../../lib/imagery";

interface Injuryish {
  region?: string | null;
  current_phase?: string | null;
}

interface Props {
  member: MemberSummary;
  adherencePct?: number | null;
  injury?: Injuryish | null;
}

const CHURN_TONE: Record<string, { dot: string; label: string }> = {
  low: { dot: "bg-emerald-500", label: "Low risk" },
  moderate: { dot: "bg-amber-500", label: "Moderate risk" },
  elevated: { dot: "bg-orange-500", label: "Elevated risk" },
  high: { dot: "bg-clay", label: "High risk" },
};

const PHASE_LABEL: Record<string, string> = {
  acute: "Acute",
  subacute: "Subacute",
  remodeling: "Remodeling",
  rta: "Return to activity",
};

export function OverviewHero({ member, adherencePct, injury }: Props) {
  const art = memberArt(member.member_id);
  const churn = CHURN_TONE[member.churn_risk_level] ?? {
    dot: "bg-ink-faint",
    label: member.churn_risk_level,
  };

  const phase =
    injury?.current_phase ? PHASE_LABEL[injury.current_phase] ?? injury.current_phase : null;
  const injuryText = injury?.region
    ? `${injury.region}${phase ? ` · ${phase}` : ""}`
    : member.active_injury ?? "No active injury";

  return (
    <section
      className="sticky top-0 z-0 h-[78vh] min-h-[460px] w-full overflow-hidden"
      style={{ background: art.gradient }}
    >
      {/* Photograph */}
      <img
        key={art.hero}
        src={art.hero}
        alt=""
        className="absolute inset-0 h-full w-full object-cover fade"
        onError={(e) => (e.currentTarget.style.display = "none")}
      />
      {/* Tonal scrim — top + bottom for legible type either end */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/15 to-black/45" />

      {/* Identity */}
      <div className="relative z-10 flex h-full flex-col justify-end px-8 pb-16 sm:px-12">
        <div className="rise">
          <div className="mb-4 flex items-center gap-2.5">
            <span className="eyebrow text-white/70">{art.tagline}</span>
            {member.workout_sent_today && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/90 px-2.5 py-0.5 text-[0.65rem] font-medium text-white">
                ✓ Sent today
              </span>
            )}
          </div>

          <h1 className="display text-white text-[clamp(2.75rem,7vw,5rem)] max-w-2xl">
            {member.name}
          </h1>

          {/* Inline vitals */}
          <div className="mt-8 flex flex-wrap items-end gap-x-10 gap-y-5">
            <Metric
              value={
                adherencePct != null ? `${Math.round(adherencePct)}%` : "—"
              }
              label="Adherence"
            />
            <Metric
              value={`${member.age}`}
              label={member.sex === "female" ? "yrs · F" : "yrs · M"}
            />
            <Metric value={injuryText} label="Status" wide />
            <div className="flex items-center gap-2 pb-1">
              <span className={`h-2 w-2 rounded-full ${churn.dot}`} />
              <span className="text-sm text-white/80">{churn.label}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Scroll cue */}
      <div className="absolute bottom-5 left-1/2 z-10 -translate-x-1/2 text-white/50">
        <div className="flex flex-col items-center gap-1.5">
          <span className="text-[0.6rem] tracking-[0.25em] uppercase">Scroll</span>
          <span className="block h-6 w-px animate-pulse bg-white/40" />
        </div>
      </div>
    </section>
  );
}

function Metric({
  value,
  label,
  wide,
}: {
  value: string;
  label: string;
  wide?: boolean;
}) {
  return (
    <div className={wide ? "max-w-[14rem]" : undefined}>
      <p className="font-display text-2xl font-light leading-none text-white">
        {value}
      </p>
      <p className="eyebrow mt-2 text-white/55">{label}</p>
    </div>
  );
}
