# 🎨 Design Language — TeacherPilot

This document defines the visual language and design principles for the TeacherPilot app.
Anyone (human or AI) contributing UI changes **must** follow these rules to maintain consistency.

## Core Philosophy: "Quiet Premium"

The app should feel like a calm, professional workspace — never loud, never cluttered.
Think of it as a **whisper, not a shout**. The UI should reduce the teacher's cognitive load,
not add to it.

**Inspiration:** Linear, Raycast, Arc Browser, Notion (dark mode).

## Color Palette

| Role        | Token Family | Example Usage                       |
| :---------- | :----------- | :---------------------------------- |
| Backgrounds | `stone`      | `bg-stone-950`, `bg-stone-900`      |
| Text        | `stone`      | `text-stone-200`, `text-stone-500`  |
| Accents     | `amber`      | `text-amber-400`, `border-amber-500/20` |
| Borders     | `stone`      | `border-stone-700`, `border-stone-800`  |

- **Always use low opacity** for borders and accent backgrounds: `/10`, `/15`, `/20`, `/40`.
- **Never use full-saturation colors** (no `bg-red-500`, no `bg-blue-600`). Use muted, transparent variants.
- The app supports theme switching (Ocean, Forest) via CSS custom properties — always use semantic `stone` and `amber` tokens, never hardcode hex values.

## Typography

- Use the system font stack (no custom fonts loaded).
- **Sizes:** Mostly `text-xs` and `text-sm`. Headings use `text-xs` with `font-semibold tracking-widest uppercase`.
- **Color hierarchy:** Important text is `text-stone-200`. Secondary is `text-stone-500`. Tertiary/labels are `text-stone-600` or `text-stone-700`.

## Shapes & Borders

- **Everything is rounded:** Use `rounded-2xl` for cards, `rounded-full` for circular elements, `rounded-lg` for inputs.
- **Border width:** Always `border` (1px), never `border-2` except for the Marimba avatar ring.
- **Border colors:** Always low opacity — `border-stone-700`, `border-stone-800`, `border-amber-500/20`.

## Icons

> **⚠️ CRITICAL: Never use emojis as UI controls.**
>
> Emojis (⏹, 🗑️, ▶️, etc.) look different on every OS and break the visual harmony.
> The **only** emoji allowed is 🦊 for Marimba's avatar (it's a character, not a control).

- **Use inline SVGs** with `stroke="currentColor"` so they inherit the theme color.
- **Stroke width:** `strokeWidth="2"` for standard icons, `strokeWidth="2.5"` for small icons (< 16px).
- **Always use** `strokeLinecap="round"` and `strokeLinejoin="round"` for soft edges.
- Prefer simple, recognizable shapes (arrow, ×, check) over detailed pictograms.

## Animations & Micro-interactions

- **Breathing:** `scale(1) → scale(1.04)`, never more than `1.08`.
- **Transitions:** Always use `transition-all duration-300` for hover/state changes.
- **Active feedback:** `active:scale-95` on buttons for a satisfying "press" feel.
- **Opacity transitions:** Prefer fading elements in/out over showing/hiding abruptly.
- Keep animations **subtle** — the user should *feel* them, not *notice* them.

## Spacing & Layout

- Main content: `max-w-4xl mx-auto px-4 py-10`.
- Section gaps: `mb-8` between major sections.
- Card padding: `p-5` or `p-6`.
- Use `gap-2` or `gap-4` for flex/grid layouts.

## Interactive Elements

- **Buttons:** Should have `hover:` and `active:` states. Use `cursor-pointer` explicitly.
- **Disabled state:** Use `cursor-default` and reduce opacity.
- **Audio feedback:** Use Web Audio API synthesized tones, not audio files.
- **Discard/cancel actions:** Small, unobtrusive (e.g., a thin `×`), positioned close to the element they affect.

## Component Patterns

- **Cards:** `bg-stone-900 border border-stone-800 rounded-2xl p-5`
- **Chips/Tags:** `bg-stone-900 border border-stone-800 rounded-xl px-3 py-2`
- **Speech bubbles:** `bg-stone-800 border border-stone-700 rounded-2xl rounded-br-sm px-3.5 py-2.5 shadow-lg`
- **Section headers:** Dot indicator + uppercase tracking label:
  ```tsx
  <div className="w-1.5 h-1.5 rounded-full bg-amber-400" />
  <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
  ```
