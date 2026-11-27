# DESIGN.md — DK Bond Tracker (paste into Stitch → Project → DESIGN.md)

> Stitch CLI cannot write project DESIGN.md (project = create-only), so this draft is for one paste into the Stitch web editor. It becomes the hard-constraint context on every generation. Source of truth for the element library: `app_components.html` §Element Library.

```yaml
name: DK Bond Tracker
version: 2026-11-27
device: DESKTOP review boards / MOBILE frames (412dp compact-only MVP)

# ── THEME: PRIMARY = Nordic Mist (light) — implementation base ──
colors:
  primary: '#28595B'          # accent (Nordic)
  background: '#F8FAFC'
  surface: '#EFF2F5'
  border: '#CFD7E2'
  text-primary: '#18212C'
  text-secondary: '#525F70'
  success: '#2B6144'
  warning: '#8A5300'
  error: '#9C3B44'

# ── THEME VARIANTS (same structure, swap tokens only) ──
themes:
  harbor-navy:      # DARK
    { background: '#101824', surface: '#1F2D42', border: '#2E405C', text-primary: '#E7EEF8', text-secondary: '#8AAEDB', primary: '#8AAEDB', error: '#D98488', success: '#7BB892', warning: '#D4A55D' }
  warm-ledger:      # LIGHT
    { background: '#F4F0E8', surface: '#FBF9F4', border: '#D8D0C2', text-primary: '#1F2421', text-secondary: '#595E59', primary: '#264362', error: '#9E3B33', success: '#2B6144', warning: '#8A5300' }
  deep-fjord:       # DARK
    { background: '#0F1A1C', surface: '#162528', border: '#2D4449', text-primary: '#DCE7E7', text-secondary: '#8FA6A8', primary: '#75B5B8', error: '#D68582', success: '#7BB892', warning: '#C9A96A' }

typography:
  headline: { family: Inter, weights: [600, 700], sizes: [24, 18, 16] }
  body:     { family: Inter, weight: 400, size: 14 }
  label:    { family: Inter, weight: 600, size: 11, transform: uppercase, tracking: wide }
  numeric:  { family: 'JetBrains Mono', tabular-nums: true }   # ₹ amounts

rounded: { card: 12, input: 12, button: 12, pill: 999 }
spacing: [4, 8, 12, 16, 24, 32]

currency: INR ₹   # ONLY currency in this product — never $ / € / £
```

## Component patterns (global element definitions)

Every generation MUST build these elements exactly as specified; never re-invent:

1. **Top App Bar (shared)** — back arrow (detail) · title · sync / bell / theme / avatar icons (order fixed) · theme chip.
2. **Bottom Nav (shared)** — Dashboard · Portfolio · Watchlist · Goals · More; active tab accent + label.
3. **GOALS / FORM segmented tabs (goals page)** — buttons `GOALS (n)` / `FORM (n)`; present top of frames 01–04, sticky above content.
4. **Stat cell / strip (shared)** — cells: `MONTHS` (never TARGET), `SAVED`, `ON TRACK`; tabular numerals.
5. **Goal card (goals)** — name · dates · **Saved ₹ amount** · **months signal (exactly one)** · status pill · Check-in + Details buttons. **NEVER show target amount or percent-of-target.**
   - months signal: on plan → `X/Y months ✓` (success); any miss → `N months missed` (error) — **negative takes precedence and stays until resolved**.
6. **Rhythm row (goals)** — month · invested `✓ ₹35,000 invested` · **returns `+₹1,820 returns`** (returns show even when MISSED). Pill: Due Soon / MISSED / done.
7. **Check-in form (goals, inline in detail)** — Amount · Date · Note (Optional) · `Record check-in` + `Save draft`. Local-first: no network-error state.
8. **Buttons (shared)** — primary (filled, accent), secondary (outline), ghost; label = verb phrase ≤4 words (`Save goal`, `Record check-in`, `Archive goal`); press = scale-down ~6% / 150ms.
9. **Text input (shared)** — label above (no asterisks; optional marked `(optional)`), helper/error below with icon+text (never colour alone), 52px touch-safe.
10. **Overflow menu (shared)** — trigger `⋮`; items only what's allowed per page (goals: `Edit goal`, `Archive goal` — **no Remove ever**).
11. **Banner (shared)** — info / warning (icon + headline + body); warning example: `2 months missed — pace adjustment active`.
12. **Empty state (shared)** — icon · headline (`No goals yet`) · body · CTA button.
13. **Status pill (shared)** — 4-tier: Behind / Due Soon / On Track / Completed — colour + TEXT always paired.
14. **Progress rail (shared)** — thin bar, no numbers/labels of target on it.

## Locked rules (hard constraints)

- **No target amounts on any reading surface** (cards, detail, stats) — Create Form is the only place a Target input exists.
- **Progress = months, one signal** (see goal card).
- **Rhythm always shows invested AND returns.**
- **No Remove/deletion UI on goals** — menus are Edit · Archive only; goals end via Achieved or Archived.
- **₹ INR only.**
- **Compact-only MVP** (phone412dp); tablet/desktop reflow = post-MVP.
- Loading: skeleton for lists, never a spinner where a skeleton works.
- Labels fixed: `Save goal` · `Record check-in` · `Save draft` · `Archive goal` · `Edit goal` (one name per concept).
