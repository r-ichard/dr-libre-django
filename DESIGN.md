# Design

Hand-written CSS in `static/css/`: `tokens.css` (custom properties), `base.css` (type, layout shell), `components.css`. No framework, no inline style or script (content security policy). Every component is shown in every state at `/style` when `DEBUG` is on.

## Tokens

- **Colour:** page `#f6f5f1`, surface `#fff`, ink `#1c2b33`, muted ink `#475a64`, primary teal `#0b5c63`, danger `#a32020`, focus `#1a4fd6`. Notice kinds each have a colour and a wash. Text is always ink or an AA-checked pair on its surface.
- **Type:** system sans. Scale 0.875, 1, 1.125, 1.25, 1.5, 2 rem. Body line 1.55, measure 68ch, tabular numerals.
- **Spacing:** 0.25, 0.5, 0.75, 1, 1.5, 2, 3 rem (`--space-1` to `--space-7`).
- **Radius:** 4px controls, 8px containers. **Tap target:** 2.75rem minimum.
- **Focus ring:** 3px solid focus colour, 2px offset, on every `:focus-visible`.

## Components and states

Status is never colour alone: icon, word and colour together.

- **Button** (`primary`, `secondary`, `danger`): default, hover, focus, disabled.
- **Field** (label, hint, error), **select**, **checkbox**: default, hint, invalid (error text, `aria-invalid`, `aria-describedby`), focus.
- **Error summary:** links to each invalid field; first invalid field carries `data-autofocus`.
- **Notice** (information, success, warning, error): icon plus a lead word.
- **Card**, **table** (caption, `th scope`, scrolls inside its wrapper), **pagination** (disabled ends), **status badge**, **empty state**, **loading state**.
