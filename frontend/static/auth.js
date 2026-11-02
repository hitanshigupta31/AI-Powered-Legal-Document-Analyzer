/* ============================================================
   CLAUSEGUARD — AUTHENTICATION
   Uses the existing FastAPI authentication API and session cookie.
============================================================ */
(() => {
    "use strict";

    const errorPanel = document.getElementById("authError");
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");
    const loginButton = document.getElementById("loginButton");
    const registerButton = document.getElementById("registerButton");

    function showMessage(message, success = false) {
        if (!errorPanel) return;
        errorPanel.textContent = message;
        errorPanel.classList.toggle("success", success);
        errorPanel.classList.remove("hidden");
        errorPanel.setAttribute("role", success ? "status" : "alert");
    }

    function clearMessage() {
        if (!errorPanel) return;
        errorPanel.textContent = "";
        errorPanel.classList.remove("success");
        errorPanel.classList.add("hidden");
    }

    async function parseResponse(response) {
        let data = {};
        try {
            data = await response.json();
        } catch (_) {
            data = {};
        }

        if (!response.ok) {
            const detail = data.detail || data.message ||
                `Request failed (${response.status}).`;
            throw new Error(Array.isArray(detail)
                ? detail.map(item => item.msg || String(item)).join(" ")
                : String(detail));
        }

        return data;
    }

    function setBusy(button, busy, busyText) {
        if (!button) return;
        if (!button.dataset.originalHtml) {
            button.dataset.originalHtml = button.innerHTML;
        }
        button.disabled = busy;
        button.setAttribute("aria-busy", busy ? "true" : "false");
        button.innerHTML = busy
            ? `${busyText}<span aria-hidden="true">…</span>`
            : button.dataset.originalHtml;
    }

    if (loginForm) {
        loginForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            clearMessage();

            const email = String(loginForm.elements.email?.value || "").trim();
            const password = String(loginForm.elements.password?.value || "");

            if (!email || !password) {
                showMessage("Enter your email and password.");
                return;
            }

            setBusy(loginButton, true, "Signing in");

            try {
                const response = await fetch("/api/auth/login", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ email, password })
                });

                const loginData = await parseResponse(response);

                // Confirm that the browser accepted the session cookie before
                // navigating. This avoids silently landing on the public page
                // when the login response succeeded but the session is absent.
                const sessionResponse = await fetch("/api/auth/me", {
                    method: "GET",
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: { "Accept": "application/json" }
                });

                if (!sessionResponse.ok) {
                    throw new Error(
                        "Your credentials were accepted, but the session was not detected. " +
                        "Refresh the page and sign in again."
                    );
                }

                const sessionData = await sessionResponse.json();
                if (!sessionData.authenticated || !sessionData.user) {
                    throw new Error("Sign-in could not establish a valid session. Please try again.");
                }

                // Route to the authenticated workspace explicitly. The public
                // landing page now lives at "/", so never use "/" after login.
                window.location.replace("/app");
            } catch (error) {
                showMessage(error.message || "Unable to sign in. Please try again.");
                setBusy(loginButton, false, "Signing in");
            }
        });

        const query = new URLSearchParams(window.location.search);
        if (query.get("registered") === "1") {
            showMessage("Your account has been created. Sign in to continue.", true);
        }
    }

    if (registerForm) {
        registerForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            clearMessage();

            const name = String(registerForm.elements.name?.value || "").trim();
            const email = String(registerForm.elements.email?.value || "").trim();
            const password = String(registerForm.elements.password?.value || "");

            if (name.length < 2) {
                showMessage("Enter your name (at least two characters). ");
                return;
            }

            if (!email || !password) {
                showMessage("Complete all fields to create your account.");
                return;
            }

            if (password.length < 8) {
                showMessage("Use a password with at least eight characters.");
                return;
            }

            setBusy(registerButton, true, "Creating account");

            try {
                const response = await fetch("/api/auth/register", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ name, email, password })
                });

                await parseResponse(response);
                window.location.assign("/login?registered=1");
            } catch (error) {
                showMessage(error.message || "Unable to create the account. Please try again.");
                setBusy(registerButton, false, "Creating account");
            }
        });
    }
})();
