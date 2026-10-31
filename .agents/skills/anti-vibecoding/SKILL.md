---
name: anti-vibecoding
description: >-
  Comprehensive guide and design engineering standard to detect, eliminate, and prevent
  poor 'vibecoded' UI anti-patterns and AI-generated design slop. Enforces production-grade
  Apple/Linear/Vercel craftsmanship, typographic hierarchy, authentic materiality, responsive
  ergonomics, and real functional utility.
---

# Anti-Vibecoding: The Production Design Craft Standard

## 1. What is "Vibecoded" UI?

"Vibecoding" refers to the careless habit of prompting an AI to generate an interface and accepting the output based purely on aesthetic "vibes" rather than rigorous design engineering.

Poor vibecoded websites are instantly recognizable by their superficial gloss: they look flashy in a static thumbnail, but upon closer inspection, they are shallow, cluttered, ergonomically broken, and functionally hollow.

---

## 2. The 10 Hallmarks of Poor Vibecoded Websites (What to Eliminate)

### 1. Carditis ("Everything is a Card")
* **The Slop:** The screen is chopped up into 15 identical, boxed-in cards with uniform 1px gray borders and `rounded-2xl` corners.
* **Why it fails:** Zero macro whitespace. Content feels suffocated and monotonous because the developer wrapped every single section in a generic card container.
* **The Fix:** Use negative space and typographic rhythm to separate sections. Not everything needs a background or a border. Let content breathe.

### 2. Neon Cyberpunk Slop
* **The Slop:** Aggressive, uncalibrated `radial-gradient` blur blobs (neon purple, electric blue, radioactive cyan) floating randomly behind text, paired with neon border glows (`box-shadow: 0 0 25px #00ffff`).
* **Why it fails:** Screams amateur crypto/NFT landing page. It degrades text contrast and causes eye fatigue.
* **The Fix:** If using ambient light, use subtle, desaturated color bleed derived from real content (e.g. album art or brand primary) with low opacity ($\le 15\%$) and deep feathering.

### 3. The Fake Monospace Grift
* **The Slop:** Slapping random monospace metadata chips everywhere on a consumer app: `[SYS.ACTIVE]`, `CADENCE: 0x48A`, `TELEMETRY // STREAMING`.
* **Why it fails:** It's faux-technical camouflage used to disguise a lack of real features or actual design craft.
* **The Fix:** Monospace fonts belong *only* in true code snippets, exact timestamps, financial figures, or tabular numbers (`font-variant-numeric: tabular-nums`). Never use it as decorative wallpaper.

### 4. Gradient Text Overkill
* **The Slop:** Applying `bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent` to every single heading, subhead, and button.
* **Why it fails:** Dilutes hierarchy. If everything is an iridescent rainbow gradient, nothing stands out.
* **The Fix:** Use solid, high-contrast typography (`#FFFFFF` for primary, `#A1A1A6` for secondary). Reserve subtle gradient text for a single hero accent or high-impact milestone badge.

### 5. Typography Hierarchy Bankruptcy
* **The Slop:** Using a generic sans-serif without optical letter-spacing, line-height calibration, or weight discipline. Everything is either an overwhelming `text-3xl font-extrabold` or low-contrast `#666666` body copy that fails WCAG accessibility.
* **Why it fails:** Hard to scan, illegible on varied screens, and feels completely amateur.
* **The Fix:** 
  * Large headlines ($\ge 32\text{px}$): Tight letter-spacing (`-0.03em` to `-0.04em`).
  * Body copy ($14\text{px}-16\text{px}$): Normal tracking (`-0.01em` to `0`), line-height $1.5-1.6$.
  * Never drop below $4.5:1$ contrast ratio for readable body text.

### 6. Layout Instability & Viewport Cutoffs
* **The Slop:** Hardcoded `height: 100vh; overflow: hidden;` on body or containers, causing content to be cut off on smaller laptops or mobile viewports without any scroll fallback.
* **Why it fails:** Completely breaks on screens $< 1200\text{px}$, tablets, or when browser developer tools are open.
* **The Fix:** Always design for responsive fluidity. Use `min-height: 100vh`, allow smooth vertical scroll with custom slim scrollbars, and collapse sidebars into mobile docks on narrow viewports.

### 7. Hyperactive Micro-Interactions
* **The Slop:** Bouncy, laggy `transform: scale(1.05)` or `translateY(-6px)` applied with `transition: all 0.3s` to every card, image, and text block on the page.
* **Why it fails:** Triggering layout thrashing on non-interactive elements creates a jittery, cheap user experience.
* **The Fix:** Only interactive elements (buttons, links, selectable rows) should respond to hover. Keep transforms subtle (`translateY(-1px)` or `scale(1.01)`), and animate only `opacity` and `transform` via GPU acceleration.

### 8. Decorative Emptiness (Dead-End UI)
* **The Slop:** Fake buttons that do nothing, charts showing identical placeholder waves, and forms with zero validation or live API connectivity.
* **Why it fails:** It's a movie prop, not functional software.
* **The Fix:** Every button must perform a real action (e.g. trigger OAuth, upload files, copy link, switch views). Provide explicit empty states, loading indicators, and informative fallback data when disconnected.

### 9. Raw HTML & Unskinned Controls
* **The Slop:** Modern dark-mode cards with blinding white default browser dropdowns, raw unstyled file inputs, or default chunky scrollbars.
* **Why it fails:** Instantly betrays that the developer didn't bother to customize standard browser controls.
* **The Fix:** Skin all inputs, selects, custom file dropzones, and scrollbars to match the application's dark glass aesthetic.

### 10. Design System Chaos
* **The Slop:** Mixing `rounded-full`, `rounded-3xl`, and `rounded-none` haphazardly in the same view. Random padding: `p-3`, `p-7`, `p-11`.
* **Why it fails:** The eye detects mathematical disharmony instantly.
* **The Fix:** Stick to a 4px/8px spatial grid: margins and padding strictly in multiples of 4 ($8\text{px}, 12\text{px}, 16\text{px}, 24\text{px}, 32\text{px}, 48\text{px}$). Corner radii locked to a strict system (Outer container: $20\text{px}-24\text{px}$, Inner tile: $12\text{px}-14\text{px}$, Button/Pill: $8\text{px}-10\text{px}$).

---

## 3. The Production Craft Engineering Standards

### Surface Depth Architecture
Do not use a single flat gray for everything. Build depth through a 4-tier layer system:
1. **Canvas (Base):** Deep black `#000000` or obsidian `#07080a`.
2. **Sidebar & Frosted Panels:** `rgba(18, 18, 22, 0.8)` with `backdrop-filter: blur(40px) saturate(200%)`.
3. **Elevated Tiles / Cards:** `rgba(28, 28, 34, 0.65)` with a hairline top specular border (`border-top: 1px solid rgba(255, 255, 255, 0.12)`).
4. **Active Targets / Overlays:** High-contrast accents (e.g. Apple Music Red `#FA2D48`, Linear Purple `#5E6AD2`) reserved strictly for user actions.

### Data Ergonomics
* Numbers in tables and meters must always use `font-variant-numeric: tabular-nums` to prevent layout jitter during live updates.
* Timestamps and durations must format with zero-padding (e.g. `3:04`, not `3:4`).
* Always provide both **Live OAuth integration** and **Offline File / Demo ingestion** so the tool works for any user immediately.

---

## 4. Pre-Flight Quality Gate (Run Before Shipping)

Before declaring any frontend complete, audit against this checklist:
- [ ] Is there macro whitespace and breathing room, or is everything crammed into uniform gray cards?
- [ ] Are all non-interactive elements free of hover transforms?
- [ ] Does the page scroll naturally without horizontal scrollbar leaks?
- [ ] Are inputs, scrollbars, and file upload zones custom-styled?
- [ ] Are letter-spacings on large headlines tightened (`-0.03em`)?
- [ ] Do all buttons trigger real actions, modals, or API flows?
- [ ] Is contrast compliant for all body text ($\ge 4.5:1$)?
- [ ] Does the layout adapt cleanly from 375px mobile to 4K displays?
