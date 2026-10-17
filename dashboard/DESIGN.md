---
name: PyMC Marketing MCP teaser
description: An editorial public introduction to evidence-led marketing decisions.
colors:
  paper: "#fff"
  warm: "#faf9f6"
  ink: "#0a0a0a"
  muted: "#595954"
  line: "#deded8"
  coral: "#ff6a2c"
  coral-hover: "#f55a19"
  focus: "#a33206"
  soft: "#fff0e6"
typography:
  display:
    fontFamily: '"Outfit", sans-serif'
    fontSize: "clamp(42px, 5.85vw, 84px)"
    fontWeight: 800
    lineHeight: 1.03
    letterSpacing: "-0.025em"
  headline:
    fontFamily: '"Outfit", sans-serif'
    fontSize: "clamp(32px, 3.5vw, 48px)"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "-0.025em"
  body:
    fontFamily: '"Inter", sans-serif'
    fontSize: "16px"
    lineHeight: 1.65
  label:
    fontFamily: '"Inter", sans-serif'
    fontSize: "14px"
    fontWeight: 600
  code:
    fontFamily: '"JetBrains Mono", monospace'
    fontSize: "12px"
    lineHeight: 1.9
rounded:
  tab: "8px"
  code: "12px"
  brief: "16px"
  pill: "999px"
spacing:
  compact: "8px"
  related: "16px"
  body: "24px"
  actions: "28px"
  section: "clamp(72px, 8vw, 112px)"
components:
  button-primary:
    backgroundColor: "{colors.coral}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "13px 25px"
  button-primary-hover:
    backgroundColor: "{colors.coral-hover}"
  role-tab-selected:
    backgroundColor: "{colors.soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tab}"
    padding: "12px 16px"
  decision-brief:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.brief}"
  code-panel:
    backgroundColor: "{colors.warm}"
    rounded: "{rounded.code}"
    padding: "10px 22px 22px"
---

# Teaser design system

## Overview

**Creative North Star: "The analytical brief"**

The user's Prepilot reference establishes a white canvas, heavy headlines, coral actions, and clear whitespace. PyMC Marketing MCP keeps its own wordmark and presents the work with restrained editorial detail.

The implemented authority is `src/teaser.css`, scoped to `.teaser-site`. This system covers the public teaser and its surrounding shell; authenticated navigation, forms, keys, usage, and admin retain the existing `src/index.css` baseline.

**Key Characteristics:**
- Large, tightly set headings with quiet supporting text.
- Flat warm panels, fine dividers, and sparse coral emphasis.
- Readable prompts and commands with visible interaction feedback.

## Colors

Coral marks the primary action and headline underline. The darker focus accent carries small accent text and keyboard outlines. Paper and warm alternate by content role; ink and muted establish hierarchy, line separates content, and soft identifies the selected role. Frontmatter preserves the source CSS values.

## Typography

Outfit carries headings, Inter carries body text and controls, and JetBrains Mono carries commands and configuration. `src/fonts.css` self-hosts Latin variable WOFF2 files from pinned `@fontsource-variable` packages with `font-display: swap`; do not depend on a remote stylesheet for these faces.

Hero description is 18px with a 690px maximum measure; body copy uses the body role. Small labels and notes range from 10–14px. On narrow screens, hero type uses `clamp(42px, 8.2vw, 62px)`, then 40px at 370px and below. Headings balance their lines.

## Layout

Content is capped at 1184px with 48px side gutters. At 1050px and below gutters become 32px; at 759px they become 20px, then 16px at 370px. Section spacing is fluid. Editorial pairs use two columns; the desktop role layout uses a 250px rail and flexible panel. At 759px these stack, role tabs wrap horizontally, and navigation opens through a menu button. Role input/output details stack at 370px.

The sticky header is 84px high, or 72px on narrow screens; anchor targets reserve 104px. Controls have at least 44px target height. Commands wrap within their containers.

## Elevation & Depth

Surfaces are flat without shadows or gradients. Warm fills and fine borders separate the analytical brief, evidence section, prompts, and setup blocks. Motion is limited to 150–160ms control transitions, a one-pixel primary-action hover lift, and disclosure-chevron rotation. Reduced motion removes transitions, animation, and smooth scrolling.

## Shapes

Primary actions are pills; analytical briefs have broad corners, prompt/code panels medium corners, and desktop role tabs smaller corners. Mobile role tabs become outlined pills. Dividers provide structure without turning each paragraph into a card.

## Components

- **Primary action:** coral with dark ink; hover deepens the fill and lifts it one pixel, active returns it. The header uses a compact variant. Text links darken to the focus accent and underline on hover.
- **Role tabs:** React Aria owns keyboard behavior and selection. Selected state uses a soft fill and visible arrow on desktop. The question, inputs, output, and prompt update together; the selection carries through setup.
- **Copy blocks:** actual code uses mono; conversational prompts use Inter. Copy progress and outcome are announced. Failure focuses selectable text and offers manual-copy instructions.
- **Disclosures:** React Aria owns expanded state; fine bottom borders separate rows and chevrons rotate on expansion.
- **Navigation and focus:** native links navigate and buttons act. Visible focus uses a 2px dark-accent outline with 5px offset. Forced colors supplies system-visible selected tabs and action borders.

## Do's and Don'ts

- **Do** preserve the public namespace and authenticated application boundary.
- **Do** use the self-hosted typefaces and visible keyboard focus.
- **Do** keep commands readable and content visible before interaction.
- **Don't** add decorative charts, gradients, tickers, or continuous motion.
- **Don't** replace the product wordmark with Prepilot's wave or mascot.
