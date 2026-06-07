/**
 * LoginScreen — the studio's front door.
 *
 * A cinematic full-bleed image anchors the left; a quiet, editorial sign-in
 * sits on a warm cream panel to the right. Mock auth: any non-empty email +
 * password is accepted by the backend stub.
 */

import { useState, type FormEvent } from "react";
import { useAuth } from "../../state/auth";
import { LOGIN_HERO, LOGIN_GRADIENT } from "../../lib/imagery";

export function LoginScreen() {
  const { login, isLoading, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await login(email, password);
  };

  return (
    <div className="min-h-screen w-full bg-canvas lg:grid lg:grid-cols-[1.15fr_1fr]">
      {/* ── Cinematic panel ──────────────────────────────────────────────── */}
      <aside
        className="relative hidden lg:block overflow-hidden"
        style={{ background: LOGIN_GRADIENT }}
      >
        <img
          src={LOGIN_HERO}
          alt=""
          className="absolute inset-0 h-full w-full object-cover opacity-80 fade"
          onError={(e) => (e.currentTarget.style.display = "none")}
        />
        {/* Tonal scrim for legible type */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-black/30" />

        {/* Brand mark */}
        <div className="relative z-10 flex items-center gap-3 px-12 pt-12">
          <div className="h-2.5 w-2.5 rounded-full bg-clay" />
          <span className="text-[0.8rem] font-medium tracking-[0.32em] text-white/90 uppercase">
            Atlas
          </span>
        </div>

        {/* Editorial headline */}
        <div className="absolute bottom-0 left-0 z-10 p-12 rise">
          <p className="eyebrow text-white/70 mb-5">Performance Studio</p>
          <h1 className="display text-white text-[3.75rem] leading-[0.95] max-w-md">
            Coaching,
            <br />
            <span className="italic font-[400]">intelligently</span> composed.
          </h1>
          <p className="mt-6 max-w-sm text-[0.95rem] leading-relaxed text-white/70">
            Every session reasoned from the body up — graph-grounded, safe by
            construction.
          </p>
        </div>
      </aside>

      {/* ── Sign-in panel ────────────────────────────────────────────────── */}
      <main className="flex min-h-screen flex-col justify-center px-8 py-16 sm:px-16 lg:px-20">
        <div className="mx-auto w-full max-w-sm rise">
          {/* Mobile brand */}
          <div className="mb-12 flex items-center gap-3 lg:mb-16">
            <div className="h-2.5 w-2.5 rounded-full bg-clay" />
            <span className="text-[0.8rem] font-medium tracking-[0.32em] text-ink uppercase">
              Atlas
            </span>
          </div>

          <p className="eyebrow mb-4">Coach Access</p>
          <h2 className="display text-ink text-4xl mb-2">Welcome back.</h2>
          <p className="text-sm text-ink-soft mb-10">
            Sign in to your studio.
          </p>

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

            {error && (
              <p className="text-sm text-clay">{error}</p>
            )}

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
