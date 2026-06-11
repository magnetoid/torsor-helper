/* Cloud Industry — interactions & motion
   Motion stack: GSAP ScrollTrigger + Lenis (CDN), feature-detected.
   Everything degrades gracefully without them and respects
   prefers-reduced-motion. */

(() => {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(pointer: fine)").matches;
  const hasGSAP = typeof window.gsap !== "undefined" && typeof window.ScrollTrigger !== "undefined";
  const hasLenis = typeof window.Lenis !== "undefined";
  const useGSAP = hasGSAP && !reduceMotion;

  if (useGSAP) {
    gsap.registerPlugin(ScrollTrigger);
    document.documentElement.classList.add("gsap-on");
  }

  /* ── Lenis smooth scrolling ──────────────────────────── */
  if (hasLenis && !reduceMotion) {
    const lenis = new Lenis({ lerp: 0.12, wheelMultiplier: 1.05 });
    if (useGSAP) {
      lenis.on("scroll", ScrollTrigger.update);
      gsap.ticker.add((t) => lenis.raf(t * 1000));
      gsap.ticker.lagSmoothing(0);
    } else {
      const raf = (t) => { lenis.raf(t); requestAnimationFrame(raf); };
      requestAnimationFrame(raf);
    }
    // keep anchor links working through Lenis
    document.querySelectorAll('a[href^="#"]').forEach((a) => {
      a.addEventListener("click", (e) => {
        const target = document.querySelector(a.getAttribute("href"));
        if (target) { e.preventDefault(); lenis.scrollTo(target, { offset: -70 }); }
      });
    });
  }

  /* ── theme toggle ────────────────────────────────────── */
  const rootEl = document.documentElement;
  const themeButtons = document.querySelectorAll(".theme-toggle");
  const applyTheme = (t) => {
    rootEl.dataset.theme = t;
    themeButtons.forEach((b) => { b.textContent = t === "light" ? "☀" : "☾"; });
  };
  applyTheme(rootEl.dataset.theme || "dark");
  themeButtons.forEach((b) =>
    b.addEventListener("click", () => {
      const next = rootEl.dataset.theme === "light" ? "dark" : "light";
      applyTheme(next);
      try { localStorage.setItem("theme", next); } catch (_) { /* private mode */ }
    })
  );

  /* ── nav scroll state ────────────────────────────────── */
  const nav = document.querySelector(".nav");
  const onScroll = () => nav.classList.toggle("is-scrolled", window.scrollY > 24);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  /* ── mobile menu ─────────────────────────────────────── */
  const burger = document.querySelector(".nav__burger");
  const menu = document.querySelector(".mobile-menu");
  const closeMenu = () => {
    menu.classList.remove("is-open");
    burger.setAttribute("aria-expanded", "false");
    menu.setAttribute("aria-hidden", "true");
  };
  burger.addEventListener("click", () => {
    const open = menu.classList.toggle("is-open");
    burger.setAttribute("aria-expanded", String(open));
    menu.setAttribute("aria-hidden", String(!open));
  });
  menu.querySelectorAll("a").forEach((a) => a.addEventListener("click", closeMenu));

  /* ── hero: char-split kinetic headline ───────────────── */
  if (useGSAP) {
    const wrapChars = (text) =>
      [...text].map((ch) => (ch === " " ? " " : `<span class="char">${ch}</span>`)).join("");
    document.querySelectorAll(".hero__line > span").forEach((line) => {
      line.style.transform = "none";
      line.style.animation = "none";
      let html = "";
      line.childNodes.forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE) {
          html += wrapChars(node.textContent);
        } else if (node.nodeType === Node.ELEMENT_NODE) {
          const el = node.cloneNode(false);
          el.innerHTML = wrapChars(node.textContent);
          html += el.outerHTML;
        }
      });
      line.innerHTML = html;
    });
    gsap.from(".hero__title .char", {
      yPercent: 120,
      rotateX: -60,
      opacity: 0,
      duration: 0.9,
      ease: "power4.out",
      stagger: 0.022,
      delay: 0.1,
      clearProps: "transform,opacity",
    });
    gsap.from(".hero__badge, .hero__sub, .hero__cta, .hero__stats", {
      y: 30, opacity: 0, duration: 1, ease: "power3.out", stagger: 0.1, delay: 0.5,
    });
  }

  /* ── scroll reveals ──────────────────────────────────── */
  const revealEls = document.querySelectorAll(".reveal");
  if (useGSAP) {
    // hero children are animated by the intro timeline above;
    // grid children are animated as cascades below
    const cascades = [".bento", ".process", ".quotes"];
    revealEls.forEach((el) => {
      if (el.closest(".hero")) return;
      if (cascades.some((sel) => el.matches(`${sel} > *`) || el.matches(sel))) return;
      gsap.from(el, {
        y: 48, opacity: 0, duration: 1, ease: "power3.out", clearProps: "transform,opacity",
        scrollTrigger: { trigger: el, start: "top 88%", once: true },
      });
    });
  } else if (reduceMotion || !("IntersectionObserver" in window)) {
    revealEls.forEach((el) => el.classList.add("is-visible"));
  } else {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach((el) => io.observe(el));
  }

  /* ── scroll-driven scenes (GSAP only) ────────────────── */
  if (useGSAP) {
    // top progress bar
    gsap.to(".progress-bar", {
      scaleX: 1, ease: "none",
      scrollTrigger: { trigger: document.body, start: "top top", end: "bottom bottom", scrub: 0.4 },
    });

    // aurora orbs drift with scroll (depth parallax)
    gsap.to(".aurora__orb--1", { yPercent: 28, ease: "none",
      scrollTrigger: { trigger: document.body, start: "top top", end: "bottom bottom", scrub: 1.2 } });
    gsap.to(".aurora__orb--2", { yPercent: -22, ease: "none",
      scrollTrigger: { trigger: document.body, start: "top top", end: "bottom bottom", scrub: 1.6 } });

    // case study visuals float against their text columns
    document.querySelectorAll(".case__visual").forEach((vis) => {
      gsap.fromTo(vis, { y: 56 }, {
        y: -56, ease: "none",
        scrollTrigger: { trigger: vis.closest(".case"), start: "top bottom", end: "bottom top", scrub: 1 },
      });
    });

    // case numbers slide in
    document.querySelectorAll(".case__num").forEach((num) => {
      gsap.from(num, {
        x: -40, opacity: 0, duration: 0.8, ease: "power3.out",
        scrollTrigger: { trigger: num, start: "top 90%", once: true },
      });
    });

    // marquee reacts to scroll velocity
    const track = document.querySelector(".marquee__track");
    if (track) {
      const skew = gsap.quickTo(track, "skewX", { duration: 0.4, ease: "power2.out" });
      ScrollTrigger.create({
        trigger: document.body, start: "top top", end: "bottom bottom",
        onUpdate: (self) => skew(gsap.utils.clamp(-10, 10, self.getVelocity() / 280)),
      });
    }

    // bento / process / quote cards cascade in as groups
    [".bento", ".process", ".quotes"].forEach((sel) => {
      const wrap = document.querySelector(sel);
      if (!wrap) return;
      gsap.from(wrap.children, {
        y: 56, opacity: 0, duration: 0.9, ease: "power3.out", stagger: 0.09,
        clearProps: "transform,opacity",
        scrollTrigger: { trigger: wrap, start: "top 85%", once: true },
      });
    });

    // CTA card zooms gently into place
    gsap.from(".cta__card", {
      scale: 0.92, opacity: 0, duration: 1.1, ease: "power3.out", clearProps: "transform,opacity",
      scrollTrigger: { trigger: ".cta", start: "top 75%", once: true },
    });

    // section titles get a soft clip-wipe
    document.querySelectorAll(".section__title").forEach((title) => {
      gsap.from(title, {
        clipPath: "inset(0 0 100% 0)", y: 24, duration: 1, ease: "power3.out",
        clearProps: "clipPath,transform",
        scrollTrigger: { trigger: title, start: "top 88%", once: true },
      });
    });
  }

  /* ── hero constellation canvas ───────────────────────── */
  const canvas = document.querySelector(".constellation");
  if (canvas && !reduceMotion) {
    const ctx = canvas.getContext("2d");
    let w, h, points = [];
    const mouse = { x: -9999, y: -9999 };
    const DENSITY = 1 / 16000, LINK = 130, SPEED = 0.22;

    const resize = () => {
      const rect = canvas.parentElement.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width; h = rect.height;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const target = Math.min(90, Math.round(w * h * DENSITY));
      points = Array.from({ length: target }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * SPEED, vy: (Math.random() - 0.5) * SPEED,
        r: Math.random() * 1.4 + 0.6,
      }));
    };
    resize();
    window.addEventListener("resize", resize, { passive: true });
    canvas.parentElement.addEventListener("mousemove", (e) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left; mouse.y = e.clientY - rect.top;
    }, { passive: true });
    canvas.parentElement.addEventListener("mouseleave", () => { mouse.x = -9999; mouse.y = -9999; });

    let visible = true;
    new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }).observe(canvas);

    const tick = () => {
      requestAnimationFrame(tick);
      if (!visible) return;
      ctx.clearRect(0, 0, w, h);
      for (const p of points) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
        // gentle pull toward the cursor
        const dxm = mouse.x - p.x, dym = mouse.y - p.y;
        if (Math.hypot(dxm, dym) < 180) { p.x += dxm * 0.0035; p.y += dym * 0.0035; }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = rootEl.dataset.theme === "light"
          ? "rgba(86, 96, 220, 0.5)" : "rgba(160, 170, 255, 0.55)";
        ctx.fill();
      }
      for (let i = 0; i < points.length; i++) {
        for (let j = i + 1; j < points.length; j++) {
          const a = points[i], b = points[j];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < LINK) {
            ctx.beginPath();
            ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = rootEl.dataset.theme === "light"
              ? `rgba(86, 96, 220, ${(1 - d / LINK) * 0.14})`
              : `rgba(122, 124, 255, ${(1 - d / LINK) * 0.16})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }
    };
    tick();
  }

  /* ── animated counters ───────────────────────────────── */
  const counters = document.querySelectorAll("[data-count]");
  const runCounter = (el) => {
    const target = parseFloat(el.dataset.count);
    const prefix = el.dataset.prefix || "";
    const suffix = el.dataset.suffix || "";
    if (reduceMotion) {
      el.textContent = prefix + target + suffix;
      return;
    }
    const dur = 1400;
    const t0 = performance.now();
    const tickC = (t) => {
      const p = Math.min((t - t0) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = prefix + Math.round(target * eased) + suffix;
      if (p < 1) requestAnimationFrame(tickC);
    };
    requestAnimationFrame(tickC);
  };
  if ("IntersectionObserver" in window) {
    const cio = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            runCounter(entry.target);
            cio.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.6 }
    );
    counters.forEach((el) => cio.observe(el));
  } else {
    counters.forEach(runCounter);
  }

  /* ── custom cursor ───────────────────────────────────── */
  if (finePointer && !reduceMotion) {
    const dot = document.querySelector(".cursor__dot");
    const ring = document.querySelector(".cursor__ring");
    let mx = -100, my = -100, rx = -100, ry = -100;
    window.addEventListener("mousemove", (e) => { mx = e.clientX; my = e.clientY; }, { passive: true });
    const loop = () => {
      rx += (mx - rx) * 0.16;
      ry += (my - ry) * 0.16;
      dot.style.transform = `translate(${mx}px, ${my}px)`;
      ring.style.transform = `translate(${rx}px, ${ry}px)`;
      requestAnimationFrame(loop);
    };
    loop();
    document.querySelectorAll("a, button, summary, .bento__card").forEach((el) => {
      el.addEventListener("mouseenter", () => document.body.classList.add("cursor-hover"));
      el.addEventListener("mouseleave", () => document.body.classList.remove("cursor-hover"));
    });
  }

  /* ── 3D tilt on cards / visuals ──────────────────────── */
  if (finePointer && !reduceMotion) {
    document.querySelectorAll("[data-tilt]").forEach((card) => {
      const strength = 5;
      card.addEventListener("mousemove", (e) => {
        const r = card.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width - 0.5;
        const py = (e.clientY - r.top) / r.height - 0.5;
        card.style.setProperty("--tiltX", `${(-py * strength).toFixed(2)}deg`);
        card.style.setProperty("--tiltY", `${(px * strength).toFixed(2)}deg`);
        card.classList.add("is-tilting");
        card.style.setProperty("--mx", `${e.clientX - r.left}px`);
        card.style.setProperty("--my", `${e.clientY - r.top}px`);
      });
      card.addEventListener("mouseleave", () => card.classList.remove("is-tilting"));
    });
  } else {
    // still feed the spotlight position for hover-capable coarse pointers
    document.querySelectorAll(".bento__card").forEach((card) => {
      card.addEventListener("pointermove", (e) => {
        const r = card.getBoundingClientRect();
        card.style.setProperty("--mx", `${e.clientX - r.left}px`);
        card.style.setProperty("--my", `${e.clientY - r.top}px`);
      });
    });
  }

  /* ── magnetic buttons ────────────────────────────────── */
  if (finePointer && !reduceMotion) {
    document.querySelectorAll("[data-magnetic]").forEach((el) => {
      el.addEventListener("mousemove", (e) => {
        const r = el.getBoundingClientRect();
        const x = (e.clientX - r.left - r.width / 2) * 0.22;
        const y = (e.clientY - r.top - r.height / 2) * 0.22;
        el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
      });
      el.addEventListener("mouseleave", () => { el.style.transform = ""; });
    });
  }

  /* ── single-open FAQ accordion ───────────────────────── */
  const faqItems = document.querySelectorAll(".faq__item");
  faqItems.forEach((item) => {
    item.addEventListener("toggle", () => {
      if (item.open) faqItems.forEach((other) => { if (other !== item) other.open = false; });
    });
  });
})();
