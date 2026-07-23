---
name: YASŌ — Night Anime Archive
description: Japanese ink-wash aesthetic anime streaming archive
colors:
  ink: "#0a0908"
  night: "#0e1526"
  night-deep: "#070b16"
  night-soft: "#182238"
  washi: "#ece1c8"
  washi-dim: "#ddcfab"
  shu: "#b7392a"
  shu-bright: "#d34a34"
  gold: "#c4a05c"
  sakura: "#f0c3cf"
typography:
  display:
    fontFamily: "Shippori Mincho, serif"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "Zen Kaku Gothic New, sans-serif"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "JetBrains Mono, monospace"
    fontWeight: 400
    letterSpacing: "0.08em"
rounded:
  sm: "2px"
  md: "4px"
  lg: "8px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "32px"
  xl: "64px"
---

# Design System: YASŌ — Night Anime Archive

## 1. Overview

**Creative North Star: "The Ink Wash Archive"**

YASŌ's design system channels the meditative restraint of Japanese sumi-e painting. Every element should feel brush-stroked — deliberate, imperfect, alive. The interface recedes into the background, letting anime art breathe. Density is low; whitespace is generous; motion is gentle like falling petals.

This system explicitly rejects the cluttered grids of generic anime sites (Crunchyroll, Funimation), the corporate polish of mainstream streaming (Netflix, Disney+), and the visual noise of ad-heavy platforms. YASŌ is a sanctuary, not a marketplace.

**Key Characteristics:**
- **Dark as default** — Night-deep backgrounds (#070b16) with cream text (#ece1c8)
- **Vermillion accents** — Shu red (#b7392a) for emphasis, never for decoration
- **Brush-stroke typography** — Shippori Mincho for display, Zen Kaku for body
- **Gentle motion** — Ease-out transitions, falling sakura petals, subtle parallax
- **Textural grain** — Film grain overlay for analog warmth

## 2. Colors

The palette is ink-wash restrained: deep darks, warm creams, and vermillion as the sole accent.

### Primary
- **Ink Black** (#0a0908): Deepest void, used for text shadows and absolute contrast
- **Night Deep** (#070b16): Primary background, the midnight canvas
- **Night** (#0e1526): Secondary backgrounds, cards, elevated surfaces

### Secondary
- **Shu Vermillion** (#b7392a): The signature accent — links, active states, highlights, the brand heartbeat
- **Shu Bright** (#d34a34): Hover state for vermillion, slightly lifted energy

### Neutral
- **Washi Cream** (#ece1c8): Primary text, the paper-white against ink
- **Washi Dim** (#ddcfab): Secondary text, labels, muted information
- **Night Soft** (#182238): Borders, subtle backgrounds, depth layers

### Named Rules
**The Vermillion Rarity Rule.** Shu red appears on ≤10% of any given screen. Its scarcity is its power — when it appears, it means something.

**The Grain Rule.** A subtle film grain overlay (4% opacity, mix-blend-mode: overlay) adds analog warmth to all surfaces. Never remove it; it's the texture of aged paper.

## 3. Typography

**Display Font:** Shippori Mincho (with serif fallback)
**Body Font:** Zen Kaku Gothic New (with sans-serif fallback)
**Label/Mono Font:** JetBrains Mono (with monospace fallback)

**Character:** The pairing creates a quiet confidence — Shippori's calligraphic brushstrokes evoke traditional Japanese aesthetics, while Zen Kaku's clean geometry ensures modern readability. The mono font adds technical precision for labels and metadata.

### Hierarchy
- **Display** (700, clamp(1.6rem, 3vw, 2.4rem), 1.2): Section titles, hero headlines — where the brush rests
- **Headline** (700, 1.6rem, 1.2): Card titles, important labels — confident strokes
- **Title** (500, 1rem, 1.4): Subheadings, navigation — clear but not loud
- **Body** (400, 0.82rem, 1.6): Paragraph text, descriptions — maximum 65ch line length
- **Label** (400, 0.68rem, 0.08em tracking, uppercase): Metadata, timestamps, technical info — whispered precision

### Named Rules
**The Calligraphic Rest Rule.** Display text uses Shippori Mincho at weight 700 — the brush's heaviest stroke. Never use lighter weights for display; the contrast is the hierarchy.

**The Whisper Rule.** Labels and metadata use JetBrains Mono at 0.68rem with wide letter-spacing. They should feel like pencil annotations on a painting — present but not competing.

## 4. Elevation

YASŌ uses tonal layering, not shadows. Depth is conveyed through background color shifts: Night Deep → Night → Night Soft. Shadows appear only as ambient glows (the moon's radial gradient) or structural separations (borders at 14% opacity).

### Shadow Vocabulary
- **Ambient Glow** (`box-shadow: 0 0 80px 16px rgba(196,160,92,0.3)`): The moon element's ethereal presence
- **Header Shadow** (`box-shadow: 0 1px 20px rgba(0,0,0,0.3)`): Appears only on scroll, marking depth
- **Search Dropdown** (`box-shadow: 0 8px 32px rgba(0,0,0,0.4)`): Elevated surface for overlays

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest. Shadows appear only as response to state (hover, scroll elevation, focus) or as atmospheric elements (the moon).

**The Border Breath Rule.** When shadows aren't present, 1px borders at `rgba(236,225,200,0.14)` create subtle separation — like ink lines on washi paper.

## 5. Components

### Buttons
- **Shape:** Slightly rounded (2px radius) — the brush's terminal flick
- **Primary:** Shu background (#b7392a), washi text (#ece1c8), padding 6px 16px
- **Hover / Focus:** Brighten to Shu Bright (#d34a34), opacity transition 0.2s ease
- **Ghost/Secondary:** Transparent background, washi-dim text, border on hover

### Cards / Containers
- **Corner Style:** Gently rounded (4px radius) — like folded paper edges
- **Background:** Night (#0e1526) for cards, Night Deep (#070b16) for main canvas
- **Shadow Strategy:** Tonal layering, no box-shadows on cards
- **Border:** 1px solid rgba(236,225,200,0.14) when separation needed
- **Internal Padding:** 16px-32px depending on density

### Navigation
- **Style:** Fixed header with backdrop-filter blur (16px), Night Deep background at 80% opacity
- **Typography:** Zen Kaku at 0.72rem, letter-spacing 0.08em, uppercase labels
- **Default:** Washi-dim text (#ddcfab)
- **Hover / Active:** Washi text (#ece1c8), underline animation (1px, width transition)
- **Mobile:** Slide-in drawer from right, full-height, same backdrop treatment

### Search Input
- **Style:** Transparent background, bottom border only (1px solid rgba(236,225,200,0.14))
- **Focus:** Border shifts to Gold (#c4a05c), width expands from 200px to 240px
- **Placeholder:** Washi at 35% opacity — visible but not competing

### NSFW Toggle
- **Style:** Custom slider with Night Soft background, washi-dim thumb
- **Active:** Shu background (#b7392a), washi thumb — the vermillion accent shines

## 6. Do's and Don'ts

### Do:
- **Do** use Shippori Mincho for all display text — it's the calligraphic soul of YASŌ
- **Do** keep vermillion (Shu) rare — it appears on ≤10% of any screen, never for decoration
- **Do** maintain the grain overlay at 4% opacity — it's the texture of aged paper
- **Do** use ease-out transitions (cubic-bezier(0.4, 0, 0.2, 1)) for all state changes
- **Do** support prefers-reduced-motion — disable all animations for users who request it
- **Do** use tonal layering for depth — Night Deep → Night → Night Soft, not shadows
- **Do** keep body text at maximum 65ch line length — the ink needs room to breathe

### Don't:
- **Don't** use generic anime site aesthetics — no cluttered grids, algorithmic recommendations, bright colors
- **Don't** use mainstream streaming polish — no corporate UI, homogenized layouts, zero personality
- **Don't** use ad-heavy patterns — no visual noise, pop-ups, distracting banners
- **Don't** use gradient text (background-clip: text) — decorative, never meaningful
- **Don't** use glassmorphism as default — blurs are rare and purposeful, not decorative
- **Don't** use side-stripe borders (border-left > 1px as accent) — never intentional
- **Don't** use identical card grids — same-sized cards with icon + heading + text is lazy
- **Don't** use numbered section markers (01 / 02 / 03) as default scaffolding — they're AI grammar
- **Don't** use tiny uppercase tracked eyebrows above every section — it's the 2023-era kicker trope
