/* ============================================================
   CLAUSEGUARD — PUBLIC LANDING MOTION
   Natural scroll reveals and a lightweight reading-progress spine.
   No framework or animation library required.
============================================================ */
(() => {
    "use strict";

    const root = document.documentElement;
    const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;

    if (reducedMotion) {
        document.querySelectorAll(".cg-reveal").forEach((node) => {
            node.classList.add("is-visible");
        });
        return;
    }

    root.classList.add("motion-ready");

    const revealNodes = Array.from(
        document.querySelectorAll(".cg-reveal")
    );

    revealNodes.forEach((node, index) => {
        const localIndex = node.parentElement
            ? Array.from(node.parentElement.children).indexOf(node)
            : index;

        node.style.setProperty(
            "--cg-delay",
            `${Math.min(Math.max(localIndex, 0), 4) * 65}ms`
        );
    });

    if ("IntersectionObserver" in window) {
        const revealObserver = new IntersectionObserver(
            (entries, observer) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) return;

                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                });
            },
            {
                threshold: 0.12,
                rootMargin: "0px 0px -42px 0px"
            }
        );

        revealNodes.forEach((node) => revealObserver.observe(node));
    } else {
        revealNodes.forEach((node) => node.classList.add("is-visible"));
    }

    const progress = document.getElementById("readingSpineProgress");
    const dot = document.getElementById("readingSpineDot");

    let scheduled = false;

    function updateProgress() {
        scheduled = false;

        if (!progress || !dot) return;

        const maxScroll = Math.max(
            document.documentElement.scrollHeight - window.innerHeight,
            1
        );

        const ratio = Math.min(
            Math.max(window.scrollY / maxScroll, 0),
            1
        );

        progress.style.height = `${ratio * 100}%`;

        dot.style.top = `calc(${ratio * 100}% - 3px)`;
    }

    function requestProgressUpdate() {
        if (scheduled) return;

        scheduled = true;

        window.requestAnimationFrame(updateProgress);
    }

    window.addEventListener(
        "scroll",
        requestProgressUpdate,
        { passive: true }
    );

    window.addEventListener(
        "resize",
        requestProgressUpdate
    );

    updateProgress();
})();