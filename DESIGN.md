---
name: Disrupting Alpha
description: A premium, dark-mode financial terminal aesthetic.
colors:
  primary: "#10b981"
  primary-container: "#065f46"
  background: "#0b0f19"
  surface: "#111827"
  surface-highlight: "#1f2937"
  text: "#f9fafb"
  text-muted: "#9ca3af"
  border: "#374151"
  up: "#10b981"
  down: "#ef4444"
typography:
  h1:
    fontFamily: Inter, sans-serif
    fontSize: 2.25rem
    fontWeight: 700
  h2:
    fontFamily: Inter, sans-serif
    fontSize: 1.5rem
    fontWeight: 600
  body-md:
    fontFamily: Inter, sans-serif
    fontSize: 1rem
  label:
    fontFamily: Inter, sans-serif
    fontSize: 0.875rem
    fontWeight: 500
rounded:
  sm: 4px
  md: 8px
  lg: 12px
spacing:
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "{spacing.sm}"
---

## Overview

The "Disrupting Alpha" UI is an advanced, premium trading terminal. It avoids bright, distracting themes in favor of a sleek, dark glass-like aesthetic (deep slates and blacks) broken only by distinct neon-accented market data (emerald greens and ruby reds).

## Colors

The core color palette relies heavily on deep space backgrounds to make data pop.

- **Background (#0b0f19):** Deep space blue/black for the root application background.
- **Surface (#111827):** Elevated containers, charts, and cards.
- **Primary (#10b981):** Emerald green, used for the main calls to action and active states.
- **Text (#f9fafb):** High-contrast off-white for critical readable values.

## Typography

The interface uses `Inter` exclusively to maintain strict tabular alignment for financial data.

## Layout

Use generous padding inside surface cards (`{spacing.lg}`) but tight spacing between related statistical elements to maintain a dense, data-rich feel.
