/**
 * LoginScreen — the studio's front door (Option B · Sticky Cinematic).
 *
 * Desktop: a looping fitness clip stays *fixed* on the left while warm canvas
 * "sheets" rise and parallax over it as the coach scrolls; the sign-in column
 * on the right stays pinned the whole way down. Honours prefers-reduced-motion
 * (falls back to the poster still) and collapses to a clean centred sign-in on
 * mobile. Mock auth: any non-empty email + password is accepted by the stub.
 */

import {
  useState,
  useEffect,
  useRef,
  type FormEvent,
  type ReactNode,
} from "react";
import { useAuth } from "../../state/auth";

const HERO_IMAGE = "/atlas-hero.jpg";

export function LoginScreen() {
  const { login, isLoading, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const reduceMotion = usePrefersReducedMotion();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await login(email, password);
  };

  return (
    <div className="relative min-h-screen w-full bg-[#0c0b08] lg:grid lg:grid-cols-[1.15fr_minmax(380px,1fr)]">
      {/* ── LEFT · cinematic scroller (desktop only) ─────────────────────── */}
      <div className="relative hidden bg-[#0c0b08] lg:block">
        {/* Sticky stage: the hero pins while the sheets below scroll over it.
            A slow Ken-Burns push-in gives the still subtle life; disabled when
            the visitor prefers reduced motion. */}
        <div className="sticky top-0 h-screen overflow-hidden">
          <img
            src={HERO_IMAGE}
            alt=""
            className={`absolute inset-0 h-full w-full object-cover object-[58%_center] [filter:saturate(1.04)_contrast(1.02)] ${
              reduceMotion ? "" : "animate-ken-burns"
            }`}
          />

          {/* Tonal scrim for legible type */}
          <div className="absolute inset-0 bg-gradient-to-b from-black/45 via-black/10 to-black/60" />

          {/* Brand mark */}
          <div className="absolute left-[7%] top-10 z-10 flex items-center gap-3">
            <div className="h-2.5 w-2.5 rounded-full bg-clay" />
            <span className="text-[0.8rem] font-medium uppercase tracking-[0.32em] text-white/90">
              Atlas
            </span>
          </div>

          {/* Editorial headline */}
          <div className="absolute bottom-[13%] left-[7%] z-10 max-w-md rise">
            <p className="eyebrow mb-4 text-white/70">Knowledge-graph coaching</p>
            <h1 className="display text-[clamp(2.75rem,5.4vw,4.75rem)] leading-[0.98] text-white">
              Train the
              <br />
              <span className="font-[400] italic">whole</span> athlete.
            </h1>
            <p className="mt-5 max-w-sm text-[0.95rem] leading-relaxed text-white/75">
              Sessions reasoned from a movement &amp; clinical graph — safe,
              personal, explainable.
            </p>
          </div>

          {/* Scroll cue */}
          <div className="absolute bottom-[6%] left-[7%] z-10 flex items-center gap-2.5 text-[0.7rem] uppercase tracking-[0.18em] text-white/65">
            <span className="relative inline-block h-7 w-[18px] rounded-[11px] border border-white/45">
              <span className="absolute left-1/2 top-1.5 h-1.5 w-[3px] -translate-x-1/2 animate-scroll-dot rounded-full bg-white" />
            </span>
            Scroll
          </div>
        </div>

        {/* Sheet track — sits above the sticky video and scrolls over it */}
        <div className="relative z-[4]">
          {/* Spacer lets the hero breathe before the first sheet arrives */}
          <div className="h-screen" />

          <Sheet first>
            <p className="eyebrow text-clay">01 · Safety first</p>
            <h2 className="display mt-2 text-[clamp(1.9rem,3.4vw,2.9rem)] leading-tight text-ink">
              The plan is built only from what's safe.
            </h2>
            <p className="mt-3 text-base leading-relaxed text-ink-soft">
              A deterministic filter walks each athlete's injuries through the
              clinical graph and removes contraindicated movements{" "}
              <em>before</em> the model sees the pool. No unsafe exercise can be
              recommended — by construction.
            </p>
          </Sheet>

          <Sheet>
            <p className="eyebrow text-clay">02 · Explainable</p>
            <h2 className="display mt-2 text-[clamp(1.9rem,3.4vw,2.9rem)] leading-tight text-ink">
              Stimulus you can read at a glance.
            </h2>
            <p className="mt-3 text-base leading-relaxed text-ink-soft">
              Every session ships with strength, conditioning and mobility
              gauges, a decision trace timed by phase, and provenance back to
              the source nodes.
            </p>
            <div className="mt-7 flex flex-wrap gap-9">
              <Stat n="17" l="safe exercises" />
              <Stat n="54" l="filtered out" />
              <Stat n="~5s" l="to generate" />
            </div>
          </Sheet>

          <Sheet last>
            <p className="eyebrow text-clay">03 · Your copilot</p>
            <h2 className="display mt-2 text-[clamp(1.9rem,3.4vw,2.9rem)] leading-tight text-ink">
              A coach beside the coach.
            </h2>
            <p className="mt-3 text-base leading-relaxed text-ink-soft">
              Grounded in each member's graph, brief and inbox.
            </p>
          </Sheet>
        </div>
      </div>

      {/* ── RIGHT · pinned sign-in ───────────────────────────────────────── */}
      <div className="relative z-10 bg-canvas">
        <main className="sticky top-0 flex min-h-screen flex-col justify-center px-8 py-16 sm:px-16 lg:h-screen lg:border-l lg:border-line lg:px-20">
          <div className="mx-auto w-full max-w-sm rise">
            {/* Mobile brand */}
            <div className="mb-12 flex items-center gap-3 lg:hidden">
              <div className="h-2.5 w-2.5 rounded-full bg-clay" />
              <span className="text-[0.8rem] font-medium uppercase tracking-[0.32em] text-ink">
                Atlas
              </span>
            </div>

            <p className="eyebrow mb-4">Coach access</p>
            <h2 className="display mb-2 text-4xl text-ink">Welcome back.</h2>
            <p className="mb-10 text-sm text-ink-soft">Sign in to your studio.</p>

            <form onSubmit={handleSubmit} className="space-y-7">
              <Field
                id="email"
                label="Email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={setEmail}
                placeholder="coach@atlas.studio"
              />
              <Field
                id="password"
                label="Password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={setPassword}
                placeholder="••••••••"
              />

              {error && <p className="text-sm text-clay">{error}</p>}

              <button
                type="submit"
                disabled={isLoading}
                className="group relative w-full overflow-hidden rounded-full bg-ink px-6 py-3.5 text-sm font-medium text-canvas transition-all hover:bg-clay disabled:opacity-60"
              >
                <span className="relative z-10">
                  {isLoading ? "Entering…" : "Enter studio"}
                </span>
              </button>
            </form>

            <p className="mt-10 text-xs text-ink-faint">
              Demo access — any email and password will sign you in.
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}

/* ── Cinematic sheet ──────────────────────────────────────────────────────
 * A warm canvas card that reveals (fade + rise) as it scrolls into view.    */
function Sheet({
  children,
  first = false,
  last = false,
}: {
  children: ReactNode;
  first?: boolean;
  last?: boolean;
}) {
  const [ref, inView] = useInView<HTMLDivElement>();
  return (
    <section
      className={[
        "mx-auto max-w-xl bg-canvas px-14 py-16 shadow-[0_-30px_80px_rgba(0,0,0,0.35)]",
        first ? "rounded-t-[22px]" : "-mt-px",
        last ? "pb-32" : "",
      ].join(" ")}
    >
      <div
        ref={ref}
        className={`transition-all duration-700 ease-out ${
          inView ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
        }`}
      >
        {children}
      </div>
    </section>
  );
}

function Stat({ n, l }: { n: string; l: string }) {
  return (
    <div>
      <div className="display text-[2.5rem] leading-none text-ink">{n}</div>
      <div className="mt-1 text-xs text-ink-faint">{l}</div>
    </div>
  );
}

/* Minimal underlined input — no boxes, just a hairline that warms on focus. */
function Field({
  id,
  label,
  type,
  value,
  onChange,
  placeholder,
  autoComplete,
}: {
  id: string;
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: string;
}) {
  return (
    <div className="group">
      <label
        htmlFor={id}
        className="eyebrow mb-2 block text-ink-soft transition-colors group-focus-within:text-clay"
      >
        {label}
      </label>
      <input
        id={id}
        type={type}
        autoComplete={autoComplete}
        required
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full border-0 border-b border-line bg-transparent px-0 py-2 text-base text-ink placeholder-ink-faint/60 transition-colors focus:border-ink focus:outline-none focus:ring-0"
      />
    </div>
  );
}

/* ── hooks ───────────────────────────────────────────────────────────────── */

function useInView<T extends Element>(): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          io.disconnect();
        }
      },
      { threshold: 0.3 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return [ref, inView];
}

function usePrefersReducedMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduce(mq.matches);
    const on = () => setReduce(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduce;
}
