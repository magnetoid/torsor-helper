# Cloud Industry — Agency Website

A fully static marketing site for the Cloud Industry AI app development
agency. No build step, no framework — files live at the repo root, so it
deploys as-is to GitHub Pages, Netlify, Vercel, Cloudflare Pages or any
static host.

## Preview locally

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

## What's inside

| File | Purpose |
|---|---|
| `index.html` | All content & structure (single page) |
| `css/style.css` | Design system: dark identity, aurora gradients, grain, bento grid, CSS product mockups |
| `js/main.js` | Interactions & motion: GSAP scroll scenes, Lenis smooth scroll, constellation canvas, counters, custom cursor, 3D tilt, magnetic buttons, FAQ accordion |

## Motion stack

GSAP ScrollTrigger and Lenis load from CDN and are **feature-detected** —
`js/main.js` falls back to its own IntersectionObserver reveals and native
scrolling if the CDNs are unreachable, and all motion is disabled under
`prefers-reduced-motion`. With GSAP active the site gains:

- char-by-char kinetic hero headline (3D rise-in)
- smooth inertia scrolling (Lenis) with anchor-link integration
- scroll-scrubbed parallax on the aurora orbs and case-study mockups
- scroll-velocity skew on the marquee
- staggered cascade entrances for bento / process / testimonial grids
- clip-wipe section titles, zoom-in CTA card, gradient scroll progress bar
- an interactive particle-constellation canvas behind the hero
  (custom, ~60 lines, pauses offscreen)

## Design decisions (based on 2026 trend research)

- **Dark mode as identity** — near-black base with an animated aurora gradient
  and film-grain overlay, not just an inverted light theme.
- **Active bento grid** — service tiles reveal extra detail chips and a
  cursor-tracking spotlight on hover.
- **Serif-italic kinetic accents** — `Instrument Serif` italics inside
  `Space Grotesk` display type; hero lines animate in with masked rise-up.
- **Case-study-first selling** — each product gets a CSS-drawn live "mockup"
  (dashboard, order list, chat + thought graph, agent terminal) instead of
  stock screenshots, plus concrete outcome bullets.
- **Performance & accessibility** — zero images, all visuals drawn in
  CSS/SVG/canvas; GSAP + Lenis are the only libraries and the site works
  without them; system fallback fonts, full `prefers-reduced-motion`
  support, semantic HTML.

## Before you launch — replace the placeholders

1. **Contact email** — search `index.html` for `hello@cloudindustry.example`
   and set your real address (appears in the CTA section).
2. **Testimonials** — the three quotes in `#testimonials` are illustrative
   placeholders. Replace them with real client quotes (with permission) or
   remove the section.
3. **Social links** — footer "Elsewhere" links point to `#`.
4. **Portfolio copy** — product descriptions for ClearCount.ai, WooPulse,
   Alethia.me and Morpheus OS were written from public positioning; adjust any
   feature claims/metrics to match the real products exactly.
5. **Domain & OG tags** — add your canonical URL and an `og:image`
   (1200×630) once the domain is connected.

## Customizing the look

All design tokens live at the top of `css/style.css` in `:root` — brand
colors (`--accent-1/2/3`), fonts, radius. Changing the three accent colors
re-themes the entire site (gradients, charts, chips, cursor) automatically.
