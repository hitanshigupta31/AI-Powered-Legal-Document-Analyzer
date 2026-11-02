/* ============================================================
   CLAUSEGUARD — DASHBOARD UI MOTION
   Enhances existing views and dynamically generated findings.
   This script never changes API calls or contract data.
============================================================ */
(() => {
    "use strict";

    const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;

    if (reducedMotion) return;

    document.documentElement.classList.add("motion-ready");

    const selectors = [
        ".hero-copy",
        ".upload-card",
        ".how-it-works",
        ".workflow-step",
        ".results-heading",
        ".summary-strip",
        ".risk-section-head",
        ".risk-card",
        ".priority-section",
        ".priority-grid > *",
        ".group-header",
        ".clause-toolbar",
        ".clause-grid > *",
        ".detail-panel",
        ".chat-header",
        ".chat-starter"
    ].join(",");

    if (!("IntersectionObserver" in window)) return;

    const observed = new WeakSet();
    const observer = new IntersectionObserver(
        (entries, instance) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("is-visible");
                instance.unobserve(entry.target);
            });
        },
        { threshold: 0.1, rootMargin: "0px 0px -35px 0px" }
    );

    function prepare(root = document) {
        root.querySelectorAll(selectors).forEach((element) => {
            if (observed.has(element)) return;
            observed.add(element);
            element.classList.add("cg-reveal");
            const index = element.parentElement
                ? Array.from(element.parentElement.children).indexOf(element)
                : 0;
            element.style.setProperty(
                "--cg-delay",
                `${Math.min(Math.max(index, 0), 4) * 55}ms`
            );
            observer.observe(element);
        });
    }

    prepare();

    const content = document.querySelector(".page-content");
    if (content && "MutationObserver" in window) {
        const mutations = new MutationObserver(() => prepare(content));
        mutations.observe(content, { childList: true, subtree: true });
    }
})();
