/* ClauseGuard — theme switcher (dark default, light optional).
   Sets <html data-theme="dark|light">, remembers the choice, and keeps
   the Watchtower iframe in sync. Does not touch any application logic. */
(function () {
    "use strict";

    var KEY = "cg-theme";
    var root = document.documentElement;
    var COLORS = { dark: "#0A0B0B", light: "#F6F3EA" };

    var SUN = '<svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
    var MOON = '<svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';

    function readStored() {
        try {
            var v = window.localStorage.getItem(KEY);
            return v === "light" || v === "dark" ? v : null;
        } catch (e) { return null; }
    }

    function writeStored(theme) {
        try { window.localStorage.setItem(KEY, theme); } catch (e) { /* storage unavailable */ }
    }

    function current() {
        return root.getAttribute("data-theme") === "light" ? "light" : "dark";
    }

    function syncToggles(theme) {
        var next = theme === "light" ? "dark" : "light";
        var buttons = document.querySelectorAll("[data-theme-toggle]");
        for (var i = 0; i < buttons.length; i++) {
            var b = buttons[i];
            if (!b.getAttribute("data-theme-ready")) {
                b.innerHTML = SUN + MOON;
                b.setAttribute("data-theme-ready", "1");
            }
            b.setAttribute("aria-label", "Switch to " + next + " theme");
            b.setAttribute("title", "Switch to " + next + " theme");
        }
    }

    function apply(theme) {
        root.setAttribute("data-theme", theme);
        var metas = document.querySelectorAll('meta[name="theme-color"]');
        for (var i = 0; i < metas.length; i++) metas[i].setAttribute("content", COLORS[theme]);
        syncToggles(theme);
    }

    function broadcast(theme) {
        var frames = document.querySelectorAll("iframe");
        for (var i = 0; i < frames.length; i++) {
            try { frames[i].contentWindow.postMessage({ type: "cg-theme", theme: theme }, window.location.origin); } catch (e) { /* ignore */ }
        }
    }

    // Apply as early as possible (script is loaded in <head>) to avoid a flash.
    apply(readStored() || "dark");

    document.addEventListener("DOMContentLoaded", function () {
        syncToggles(current());
    });

    document.addEventListener("click", function (event) {
        var target = event.target;
        var btn = target && target.closest ? target.closest("[data-theme-toggle]") : null;
        if (!btn) return;
        var next = current() === "light" ? "dark" : "light";
        apply(next);
        writeStored(next);
        broadcast(next);
    });

    // Keep other tabs and the Watchtower iframe in sync.
    window.addEventListener("storage", function (event) {
        if (event.key === KEY && (event.newValue === "light" || event.newValue === "dark")) {
            apply(event.newValue);
        }
    });

    window.addEventListener("message", function (event) {
        if (event.origin !== window.location.origin) return;
        var d = event.data;
        if (d && d.type === "cg-theme" && (d.theme === "light" || d.theme === "dark")) apply(d.theme);
    });
})();
