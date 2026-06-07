/**
 * imagery.ts — curated full-bleed photography for the studio aesthetic.
 *
 * Each member maps to a hero image that matches their training identity.
 * URLs are stable Unsplash photo IDs; consumers should pair them with an
 * onError gradient fallback (see `heroGradient`) so a missing image degrades
 * to an elegant warm gradient rather than a broken tile.
 */

const U = (id: string, w = 1600) =>
  `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=${w}&q=80`;

export interface MemberArt {
  /** Full-bleed hero behind the member's name */
  hero: string;
  /** Tighter crop for cards / avatars */
  portrait: string;
  /** Two-word identity tag shown as an eyebrow over the hero */
  tagline: string;
  /** Warm gradient used as a load placeholder + onError fallback */
  gradient: string;
}

const FALLBACK: MemberArt = {
  hero: U("1517836357463-d25dfeac3438"),
  portrait: U("1517836357463-d25dfeac3438", 600),
  tagline: "In Training",
  gradient: "linear-gradient(135deg, #b4502e 0%, #555f4a 100%)",
};

const ART: Record<string, MemberArt> = {
  // Jordan Rivera — recovering left knee, home gym, rebuilding capacity.
  mbr_01HX9JORDAN: {
    hero: U("1546483875-ad9014c88eba"), // dawn runner / measured effort
    portrait: U("1546483875-ad9014c88eba", 600),
    tagline: "Rebuilding Strength",
    gradient: "linear-gradient(135deg, #8a6d3b 0%, #2c2a22 100%)",
  },
  // Mico — former gymnast, HYROX, calisthenics, founder, lumbar mobility work.
  mbr_MICO: {
    hero: U("1534438327276-14e5300c3a48"), // raw strength / control
    portrait: U("1534438327276-14e5300c3a48", 600),
    tagline: "Hybrid Athlete",
    gradient: "linear-gradient(135deg, #b4502e 0%, #18160f 100%)",
  },
};

export function memberArt(memberId: string | null | undefined): MemberArt {
  if (!memberId) return FALLBACK;
  return ART[memberId] ?? FALLBACK;
}

/** Cinematic image for the sign-in screen. */
export const LOGIN_HERO = U("1517838277536-f5f99be501cd", 2000); // athlete, low key
export const LOGIN_GRADIENT =
  "linear-gradient(135deg, #18160f 0%, #3a2a1f 55%, #b4502e 130%)";
