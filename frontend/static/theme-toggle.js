/* ClauseGuard appearance preference. This affects presentation only. */
(function () {
    "use strict";

    var STORAGE_KEY = "clauseguard.theme";
    var root = document.documentElement;

    function readTheme() {
        try {
            return window.localStorage.getItem(STORAGE_KEY) === "light" ? "light" : "dark";
        } catch (error) {
            return root.getAttribute("data-theme") === "light" ? "light" : "dark";
        }
    }

    function applyTheme(theme, persist) {
        var chosen = theme === "light" ? "light" : "dark";
        root.setAttribute("data-theme", chosen);

        if (persist) {
            try {
                window.localStorage.setItem(STORAGE_KEY, chosen);
            } catch (error) {
                // Theme still applies for this page if storage is unavailable.
            }
        }

        var metaTheme = document.querySelector('meta[name="theme-color"]');
        if (metaTheme) {
            metaTheme.setAttribute("content", chosen === "light" ? "#F4F1E9" : "#0A0B0B");
        }

        document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
            var label = button.querySelector(".theme-toggle-label");
            var icon = button.querySelector(".theme-toggle-icon");
            var nextLabel = chosen === "light" ? "Dark theme" : "Light theme";
            button.setAttribute("aria-pressed", chosen === "light" ? "true" : "false");
            button.setAttribute("aria-label", "Switch to " + nextLabel.toLowerCase());
            button.setAttribute("title", "Switch to " + nextLabel.toLowerCase());
            if (label) label.textContent = nextLabel;
            if (icon) icon.textContent = chosen === "light" ? "☾" : "☼";
        });
    }

    // Normalize the stored preference before binding controls.
    applyTheme(readTheme(), false);

    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
        button.addEventListener("click", function () {
            applyTheme(root.getAttribute("data-theme") === "light" ? "dark" : "light", true);
        });
    });

    // Keep a same-origin Watchtower iframe and the surrounding workspace in sync.
    window.addEventListener("storage", function (event) {
        if (event.key === STORAGE_KEY) {
            applyTheme(event.newValue === "light" ? "light" : "dark", false);
        }
    });
})();
