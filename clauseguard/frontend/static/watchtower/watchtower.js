
/* ============================================================
   CLAUSEGUARD — WATCHTOWER
   Fixed clause navigation + visible rule panel integration.
   Uses existing FastAPI endpoints only.
============================================================ */

(function () {
    "use strict";

    const state = {
        contractId: null,
        watchtower: null,
        items: [],
        events: [],
        alerts: [],
        evaluations: [],
        selectedItem: null,
        selectedEvaluation: null,
        selectedAlert: null,
        confirmingAlertId: null,
        closingAlertId: null,
        previousFocus: null,
        toastTimer: null
    };

    const $ = (selector, root = document) =>
        root.querySelector(selector);

    const $$ = (selector, root = document) =>
        [...root.querySelectorAll(selector)];

    const safeText = (value, fallback = "—") => {
        if (value === null || value === undefined ||
            String(value).trim() === "") {
            return fallback;
        }
        return String(value).trim();
    };

    const upper = (value, fallback = "—") =>
        safeText(value, fallback).replace(/[_-]+/g, " ").toUpperCase();

    const padClause = value => {
        const result = safeText(value, "");
        return !result ? "—" : /^\d$/.test(result) ? `0${result}` : result;
    };

    const escapeHtml = value => String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

    function listFrom(response, key) {
        if (Array.isArray(response)) return response;
        if (Array.isArray(response?.[key])) return response[key];
        if (Array.isArray(response?.data?.[key])) return response.data[key];
        return [];
    }

    function timestamp(value) {
        if (!value) return null;
        const result = new Date(value).getTime();
        return Number.isFinite(result) ? result : null;
    }

    function formatDate(value) {
        if (!value) return "—";

        const raw = String(value).trim();
        const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);

        const date = dateOnly
            ? new Date(+dateOnly[1], +dateOnly[2] - 1, +dateOnly[3])
            : new Date(raw);

        if (Number.isNaN(date.getTime())) return raw;

        return new Intl.DateTimeFormat("en-GB", {
            day: "2-digit",
            month: "short",
            year: "numeric"
        }).format(date).toUpperCase();
    }

    function matchesItem(record, itemId) {
        return record?.watch_item_id != null &&
            String(record.watch_item_id) === String(itemId);
    }


    /* ========================================================
       CONTRACT ID
    ======================================================== */

    async function resolveContractId() {
        const params = new URLSearchParams(location.search);
        const fromUrl = params.get("contract_id");

        if (fromUrl) return fromUrl;

        for (const key of [
            "watchtower.contract_id",
            "contract_id",
            "currentContractId",
            "selectedContractId"
        ]) {
            const saved = localStorage.getItem(key);
            if (saved) return saved;
        }

        const response = await WatchtowerAPI.getContracts();
        const contracts = listFrom(response, "contracts");

        if (!contracts.length || contracts[0].id == null) {
            throw new Error("No contract was returned by the backend.");
        }

        const id = String(contracts[0].id);
        localStorage.setItem("watchtower.contract_id", id);
        return id;
    }


    /* ========================================================
       DATA LOADING
    ======================================================== */

    async function optionalRead(label, request, fallback) {
        try {
            return await request();
        } catch (error) {
            console.warn(`[Watchtower] ${label} unavailable:`, error.message);
            return fallback;
        }
    }

    async function loadWatchtower() {
        showError("");

        try {
            state.contractId = await resolveContractId();

            const core = await WatchtowerAPI.getWatchtower(
                state.contractId
            );

            if (core?.success === false) {
                throw new Error(core.message || "Watchtower request failed.");
            }

            state.watchtower = core?.watchtower || null;
            state.items = listFrom(core, "items");

            const [eventsResponse, alertsResponse, evaluationsResponse] =
                await Promise.all([
                    optionalRead(
                        "Events",
                        () => WatchtowerAPI.getWatchtowerEvents(
                            state.contractId
                        ),
                        { events: [] }
                    ),
                    optionalRead(
                        "Alerts",
                        () => WatchtowerAPI.getWatchtowerAlerts(
                            state.contractId
                        ),
                        null
                    ),
                    optionalRead(
                        "Evaluations",
                        () => WatchtowerAPI.getWatchtowerEvaluations(
                            state.contractId
                        ),
                        { evaluations: [] }
                    )
                ]);

            state.events = listFrom(eventsResponse, "events");
            state.alerts = alertsResponse
                ? listFrom(alertsResponse, "alerts")
                : [];
            state.evaluations = listFrom(
                evaluationsResponse,
                "evaluations"
            );

            updateContractMeta();
            chooseInitialItem();
            renderAll();

            if (!alertsResponse) {
                showToast(
                    "Alert data could not be refreshed. Other Watchtower data is available.",
                    "warning"
                );
            }

            console.info("Watchtower loaded", {
                contractId: state.contractId,
                items: state.items.length,
                events: state.events.length,
                alerts: state.alerts.length,
                evaluations: state.evaluations.length
            });

        } catch (error) {
            console.error("[Watchtower] Loading failed:", error);
            showError(error.message || "Unable to load Watchtower data.");
        }
    }


    /* ========================================================
       ALERT PRIORITY
    ======================================================== */

    function openAlertsSorted() {
        return state.alerts
            .filter(alert =>
                String(alert.status || "").toLowerCase() === "open"
            )
            .slice()
            .sort((a, b) => {
                const aDue = timestamp(a.due_at);
                const bDue = timestamp(b.due_at);

                if (aDue !== null && bDue !== null) {
                    return aDue - bDue;
                }
                if (aDue !== null) return -1;
                if (bDue !== null) return 1;

                return (timestamp(b.created_at) || 0) -
                    (timestamp(a.created_at) || 0);
            });
    }

    function itemForAlert(alert) {
        return state.items.find(item =>
            String(item.id) === String(alert?.watch_item_id)
        ) || null;
    }

    function alertForItem(itemId) {
        const matches = state.alerts.filter(
            alert => matchesItem(alert, itemId)
        );

        return matches.find(
            alert => String(alert.status).toLowerCase() === "open"
        ) || matches[0] || null;
    }

    function evaluationForItem(itemId) {
        const matches = state.evaluations.filter(
            evaluation => matchesItem(evaluation, itemId)
        );

        matches.sort((a, b) =>
            (timestamp(b.evaluated_at) || 0) -
            (timestamp(a.evaluated_at) || 0)
        );

        return matches.find(evaluation =>
            ["triggered", "deviation"].includes(
                String(evaluation.result).toLowerCase()
            )
        ) || matches[0] || null;
    }


    /* ========================================================
       INITIAL SELECTION
    ======================================================== */

    function chooseInitialItem() {
        if (!state.items.length) {
            state.selectedItem = null;
            state.selectedEvaluation = null;
            state.selectedAlert = null;
            return;
        }

        const firstAlert = openAlertsSorted()[0];
        let item = firstAlert ? itemForAlert(firstAlert) : null;

        if (!item) {
            const evaluation = state.evaluations.find(candidate =>
                ["triggered", "deviation"].includes(
                    String(candidate.result).toLowerCase()
                )
            );

            if (evaluation) {
                item = state.items.find(candidate =>
                    String(candidate.id) ===
                    String(evaluation.watch_item_id)
                );
            }
        }

        if (!item) {
            item = state.items.find(candidate =>
                String(candidate.item_type).toLowerCase() === "renewal"
            );
        }

        selectItem((item || state.items[0]).id, false);
    }


    /* ========================================================
       EVENTS: ONLY USE REAL ITEM ASSOCIATIONS
    ======================================================== */

    function eventForItem(itemId) {
        const evaluation = evaluationForItem(itemId);

        if (evaluation) {
            return {
                event_type: evaluation.event_type,
                event_date: evaluation.event_date,
                description: evaluation.event_description
            };
        }

        const event = state.events.find(
            candidate => matchesItem(candidate, itemId)
        );

        if (event) return event;

        const alert = alertForItem(itemId);

        if (alert) {
            return {
                event_type: alert.alert_type || alert.title,
                event_date: alert.created_at,
                description: alert.message
            };
        }

        return null;
    }

    function eventType(event) {
        return event?.event_type ||
            event?.event_name ||
            event?.type ||
            event?.title ||
            "NO MATCHED EVENT";
    }

    function eventDate(event) {
        return event?.event_date ||
            event?.occurred_at ||
            event?.created_at ||
            event?.timestamp ||
            event?.date ||
            null;
    }

    function eventDescription(event) {
        return event?.description ||
            event?.event_description ||
            "No additional event description was returned.";
    }


    /* ========================================================
       SELECT CLAUSE
    ======================================================== */

    function selectItem(itemId, animate = true) {
        const item = state.items.find(candidate =>
            String(candidate.id) === String(itemId)
        );

        if (!item) {
            showToast("The requested monitored clause was not found.", "warning");
            return false;
        }

        state.selectedItem = item;
        state.selectedEvaluation = evaluationForItem(item.id);
        state.selectedAlert = alertForItem(item.id);

        renderAll();

        if (animate) animateSelection();

        return true;
    }

    /*
     * FIX: View Clause must do more than change the highlighted
     * clause. It scrolls to the map and focuses the actual row.
     */
    function viewClause(itemId) {
        const selected = selectItem(itemId, true);
        if (!selected) return;

        requestAnimationFrame(() => {
            const map = $("#contractMap");
            const row = $$("#clauseList .clause-row").find(
                candidate =>
                    String(candidate.dataset.watchItemId) === String(itemId)
            );

            if (map) {
                map.classList.add("is-visible");
            }

            const target = row || map;

            if (!target) return;

            const reducedMotion = window.matchMedia(
                "(prefers-reduced-motion: reduce)"
            ).matches;

            target.scrollIntoView({
                behavior: reducedMotion ? "auto" : "smooth",
                block: row ? "center" : "start"
            });

            if (row) {
                row.classList.remove("view-target");
                void row.offsetWidth;
                row.classList.add("view-target");
                row.focus({ preventScroll: true });
            }
        });
    }


    /* ========================================================
       RULES AND DEADLINES
    ======================================================== */

    function ruleValueFor(item) {
        const rule = item?.rule || {};

        const values = [
            rule.notice_period,
            rule.cure_period,
            rule.cadence,
            rule.amount,
            rule.percentage,
            rule.rate,
            rule.duration,
            rule.event
        ];

        const found = values.find(value =>
            value !== null &&
            value !== undefined &&
            String(value).trim() !== ""
        );

        return found === undefined ? "—" : upper(found);
    }

    function ruleDescriptionFor(item) {
        const descriptions = {
            renewal: "Written notice required before automatic renewal.",
            payment: "Recurring payment obligation.",
            payment_consequence: "Contractual late-payment consequence.",
            cure_period: "Cure or notice protection.",
            term_deadline: "Contract term deadline.",
            threshold: "Contractual threshold."
        };

        return safeText(
            item?.description,
            descriptions[String(item?.item_type || "").toLowerCase()] ||
            "Monitored contractual provision."
        );
    }

    function deadlineFor(item) {
        const alert = state.selectedAlert;
        const evaluation = state.selectedEvaluation;
        const rule = item?.rule || {};

        return alert?.due_at ||
            alert?.deadline ||
            evaluation?.due_at ||
            evaluation?.deadline ||
            rule?.deadline ||
            item?.due_at ||
            item?.deadline ||
            null;
    }

    function statusFor(item) {
        const alert = alertForItem(item.id);
        const evaluation = evaluationForItem(item.id);

        if (String(alert?.status).toLowerCase() === "open") {
            return { label: "ATTENTION", className: "attention" };
        }

        const result = String(evaluation?.result || "").toLowerCase();

        if (result === "deviation") {
            return { label: "ATTENTION", className: "attention" };
        }
        if (result === "triggered") {
            return { label: "RELEVANT", className: "relevant" };
        }
        if (result === "observed") {
            return { label: "OBSERVED", className: "observed" };
        }

        return {
            label: String(item?.status).toLowerCase() === "active"
                ? "MONITORED"
                : upper(item?.status, "UNKNOWN"),
            className: "monitored"
        };
    }

    function resultFor(item) {
        const evaluation = state.selectedEvaluation;

        return evaluation?.result
            ? upper(evaluation.result)
            : state.selectedAlert?.alert_type
                ? upper(state.selectedAlert.alert_type)
                : statusFor(item).label;
    }

    function evidenceFor(item) {
        const evaluationEvidence =
            state.selectedEvaluation?.evidence || {};
        const itemEvidence = item?.evidence || {};

        return evaluationEvidence.matched_text ||
            evaluationEvidence.text ||
            itemEvidence.matched_text ||
            itemEvidence.text ||
            item?.requirement_text ||
            "";
    }


    /* ========================================================
       CONTRACT META
    ======================================================== */

    function updateContractMeta() {
        const meta = $("#contractMeta");
        const label = $("#mapContractLabel");

        if (meta) {
            meta.innerHTML = `
                <span>CONTRACT ${escapeHtml(state.contractId)}</span>
                <span>·</span>
                <span>${state.items.length} MONITORED PROVISIONS</span>
                <span>·</span>
                <span>LIVE BACKEND DATA</span>
            `;
        }

        if (label) {
            label.textContent = `CONTRACT ${state.contractId}`;
        }
    }


    /* ========================================================
       RENDER
    ======================================================== */

    function renderAll() {
        renderContractState();
        renderPriorityAlert();
        renderClauseList();
        renderSignalMap();

        requestAnimationFrame(drawSignalConnections);
    }

    function renderContractState() {
        const tower = state.watchtower;
        const openCount = openAlertsSorted().length;
        const serverOpenCount = Number(tower?.open_alert_count);

        const count = state.alerts.length
            ? openCount
            : (Number.isFinite(serverOpenCount) ? serverOpenCount : 0);

        $("#monitoredCount").textContent =
            String(tower?.item_count ?? state.items.length).padStart(2, "0");

        $("#activeCount").textContent =
            String(state.items.filter(item =>
                String(item.status).toLowerCase() === "active"
            ).length).padStart(2, "0");

        $("#eventCount").textContent =
            String(tower?.event_count ?? state.events.length).padStart(2, "0");

        const indicator = $("#stateIndicator");
        const description = $("#stateDescription");
        const summary = $("#stateSummary");

        if (indicator) {
            indicator.innerHTML = `
                <span class="state-live-dot"></span>
                ${count > 0 ? "ATTENTION REQUIRED" : "MONITORING ACTIVE"}
            `;
        }

        if (description) {
            description.textContent = count > 0
                ? `${count} open alert${count === 1 ? "" : "s"} require attention.`
                : "Watchtower is monitoring the configured contractual provisions.";
        }

        if (summary) {
            summary.textContent = state.events.length
                ? `${state.events.length} recorded event${state.events.length === 1 ? "" : "s"} returned by the backend.`
                : "No recorded events were returned by the backend.";
        }
    }


    /* ========================================================
       PRIORITY ALERT
    ======================================================== */

    function ensurePriorityAlertPanel() {
        let panel = $("#priorityAlertPanel");
        if (panel) return panel;

        const map = $("#contractMap");
        const label = $(".map-label", map);

        if (!map || !label) return null;

        panel = document.createElement("section");
        panel.id = "priorityAlertPanel";
        panel.className = "priority-alert-panel";
        panel.setAttribute("aria-live", "polite");
        panel.setAttribute("aria-label", "Priority Watchtower alert");

        label.insertAdjacentElement("afterend", panel);

        return panel;
    }

    function renderPriorityAlert() {
        const panel = ensurePriorityAlertPanel();
        if (!panel) return;

        const alerts = openAlertsSorted();

        if (!alerts.length) {
            panel.hidden = true;
            panel.replaceChildren();
            state.confirmingAlertId = null;
            state.closingAlertId = null;
            return;
        }

        const alert = alerts[0];
        const item = itemForAlert(alert);
        const alertId = String(alert.id);
        const isConfirming = state.confirmingAlertId === alertId;
        const isClosing = state.closingAlertId === alertId;

        const dueText = alert.due_at
            ? `DUE ${formatDate(alert.due_at)}`
            : "NO DEADLINE RECORDED";

        panel.hidden = false;
        panel.innerHTML = `
            <div class="priority-alert-topline">
                <span class="priority-alert-indicator">
                    <span class="priority-alert-dot"></span>
                    ATTENTION REQUIRED
                </span>
                <span class="priority-alert-count">
                    ${alerts.length > 1
                        ? `${alerts.length - 1} MORE OPEN ALERT${alerts.length > 2 ? "S" : ""}`
                        : "HIGHEST PRIORITY OPEN ALERT"}
                </span>
            </div>

            <div class="priority-alert-content">
                <div class="priority-alert-main">
                    <div class="priority-alert-meta">
                        <span>${escapeHtml(dueText)}</span>
                        <span>·</span>
                        <span>CLAUSE ${escapeHtml(padClause(item?.clause_id))}</span>
                    </div>
                    <h3>${escapeHtml(safeText(alert.title, item?.title || "Watchtower alert"))}</h3>
                    <p>${escapeHtml(safeText(alert.message, "A monitored provision requires attention."))}</p>
                </div>

                <div class="priority-alert-actions">
                    ${item ? `
                        <button type="button"
                            class="priority-action priority-action-secondary"
                            data-alert-view="${escapeHtml(item.id)}">
                            VIEW CLAUSE <span aria-hidden="true">↗</span>
                        </button>
                    ` : ""}

                    ${isConfirming ? `
                        <div class="alert-confirmation">
                            <p>
                                Close this alert record? This does not confirm
                                that the underlying issue has been resolved.
                            </p>
                            <div class="alert-confirmation-actions">
                                <button type="button"
                                    class="priority-action priority-action-danger"
                                    data-alert-confirm="${escapeHtml(alertId)}"
                                    ${isClosing ? "disabled" : ""}>
                                    ${isClosing ? "CLOSING…" : "CONFIRM CLOSE"}
                                </button>
                                <button type="button"
                                    class="priority-action priority-action-secondary"
                                    data-alert-cancel
                                    ${isClosing ? "disabled" : ""}>
                                    KEEP OPEN
                                </button>
                            </div>
                        </div>
                    ` : `
                        <button type="button"
                            class="priority-action priority-action-primary"
                            data-alert-close="${escapeHtml(alertId)}">
                            CLOSE ALERT <span aria-hidden="true">×</span>
                        </button>
                    `}
                </div>
            </div>

            <div class="priority-alert-footnote">
                Closing an alert changes its Watchtower status only.
            </div>
        `;
    }


    /* ========================================================
       CLAUSE ROWS
    ======================================================== */

    function renderClauseList() {
        const container = $("#clauseList");
        if (!container) return;

        container.replaceChildren();

        if (!state.items.length) {
            const empty = document.createElement("div");
            empty.className = "clause-placeholder";
            empty.textContent =
                "No monitored provisions were returned for this contract.";
            container.appendChild(empty);

            $("#clauseHeaderCount").textContent = "00";
            $("#remainingClauses").innerHTML =
                "<span>NO MONITORED PROVISIONS</span><strong>00 TOTAL</strong>";
            return;
        }

        state.items.forEach(item => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "clause-row";
            button.dataset.watchItemId = String(item.id);

            const selected =
                String(item.id) === String(state.selectedItem?.id);

            button.classList.toggle("active", selected);
            button.setAttribute("aria-pressed", String(selected));

            const status = statusFor(item);

            button.innerHTML = `
                <span class="clause-number">
                    ${escapeHtml(padClause(item.clause_id))}
                </span>
                <span class="clause-information">
                    <strong>${escapeHtml(safeText(
                        item.title,
                        item.clause_title || "Monitored provision"
                    ))}</strong>
                    <small>${escapeHtml(safeText(
                        item.description,
                        "Monitored contractual provision"
                    ))}</small>
                </span>
                <span class="clause-status ${status.className}">
                    ${escapeHtml(status.label)}
                </span>
            `;

            container.appendChild(button);
        });

        $("#clauseHeaderCount").textContent =
            String(state.items.length).padStart(2, "0");

        $("#remainingClauses").innerHTML = `
            <span>ALL MONITORED PROVISIONS SHOWN</span>
            <strong>${String(state.items.length).padStart(2, "0")} TOTAL</strong>
        `;
    }


    /* ========================================================
       EVENT / RULE / DEADLINE MAP
    ======================================================== */

    function renderSignalMap() {
        const item = state.selectedItem;

        if (!item) {
            $("#eventTitle").textContent = "NO MONITORS";
            $("#eventDate").textContent = "—";
            $("#eventDescription").textContent = "No monitored provision is available.";
            $("#ruleValue").textContent = "—";
            $("#ruleDescription").textContent = "No contractual rule available.";
            $("#deadlineValue").textContent = "—";
            $("#deadlineSource").textContent = "No deadline available.";
            return;
        }

        const event = eventForItem(item.id);
        const deadline = deadlineFor(item);

        $("#eventTitle").textContent =
            upper(event ? eventType(event) : "NO MATCHED EVENT");

        $("#eventDate").textContent =
            event && eventDate(event)
                ? formatDate(eventDate(event))
                : "NO EVENT DATE RECORDED";

        $("#eventDescription").textContent = event
            ? eventDescription(event)
            : "No event was directly associated with this provision in the evaluation records.";

        $("#ruleValue").textContent = ruleValueFor(item);
        $("#ruleDescription").textContent = ruleDescriptionFor(item);

        $("#deadlineValue").textContent =
            deadline ? formatDate(deadline) : "—";

        $("#deadlineSource").textContent = deadline
            ? `ASSOCIATED WITH CLAUSE ${padClause(item.clause_id)}`
            : "NO DEADLINE RETURNED BY THE BACKEND";

        $("#deadlineLabel").textContent =
            state.selectedAlert?.due_at
                ? "ACTION REQUIRED BY"
                : "CONTRACTUAL DEADLINE";
    }


    /* ========================================================
       SIGNAL CONNECTIONS
    ======================================================== */

    function ensureSignalSvg(layout) {
        let svg = $(".signal-flow-svg", layout);
        if (svg) return svg;

        svg = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "svg"
        );

        svg.classList.add("signal-flow-svg");
        svg.setAttribute("aria-hidden", "true");
        svg.setAttribute("preserveAspectRatio", "none");

        // Insert the decorative SVG without relying on child order
        // for the visibility of any map column.
        layout.prepend(svg);

        return svg;
    }

    function pathBetween(start, end) {
        const dx = end.x - start.x;
        const dy = end.y - start.y;

        if (Math.abs(dx) >= Math.abs(dy)) {
            const bend = Math.max(18, Math.abs(dx) * 0.42);
            const direction = dx >= 0 ? 1 : -1;

            return `M ${start.x} ${start.y}
                C ${start.x + bend * direction} ${start.y},
                  ${end.x - bend * direction} ${end.y},
                  ${end.x} ${end.y}`;
        }

        const bend = Math.max(18, Math.abs(dy) * 0.38);
        const direction = dy >= 0 ? 1 : -1;

        return `M ${start.x} ${start.y}
            C ${start.x} ${start.y + bend * direction},
              ${end.x} ${end.y - bend * direction},
              ${end.x} ${end.y}`;
    }

    function addSignalPath(svg, d) {
        const ns = "http://www.w3.org/2000/svg";

        const base = document.createElementNS(ns, "path");
        base.setAttribute("d", d);
        base.setAttribute("class", "signal-flow-line");
        svg.appendChild(base);

        const pulse = document.createElementNS(ns, "path");
        pulse.setAttribute("d", d);
        pulse.setAttribute("class", "signal-flow-pulse");
        svg.appendChild(pulse);
    }

    function drawSignalConnections() {
        const layout = $(".map-layout");
        const item = state.selectedItem;

        if (!layout || !item) return;

        const svg = ensureSignalSvg(layout);
        const layoutRect = layout.getBoundingClientRect();

        if (!layout.clientWidth || !layout.clientHeight) return;

        svg.setAttribute(
            "viewBox",
            `0 0 ${layout.clientWidth} ${layout.clientHeight}`
        );
        svg.replaceChildren();

        const eventCard = $(".event-card");
        const row = $$("#clauseList .clause-row").find(
            candidate =>
                String(candidate.dataset.watchItemId) === String(item.id)
        );
        const ruleCard = $(".rule-card");

        if (!eventCard || !row || !ruleCard) return;

        const eventRect = eventCard.getBoundingClientRect();
        const rowRect = row.getBoundingClientRect();
        const ruleRect = ruleCard.getBoundingClientRect();

        const local = (x, y) => ({
            x: x - layoutRect.left,
            y: y - layoutRect.top
        });

        if (eventForItem(item.id)) {
            addSignalPath(
                svg,
                pathBetween(
                    local(eventRect.right + 3, eventRect.top + eventRect.height / 2),
                    local(rowRect.left - 3, rowRect.top + rowRect.height / 2)
                )
            );
        }

        addSignalPath(
            svg,
            pathBetween(
                local(rowRect.right + 3, rowRect.top + rowRect.height / 2),
                local(ruleRect.left - 3, ruleRect.top + ruleRect.height / 2)
            )
        );
    }


    /* ========================================================
       CLOSE ALERT
    ======================================================== */

    async function closeAlert(alertId) {
        const alert = state.alerts.find(
            candidate => String(candidate.id) === String(alertId)
        );

        if (!alert || String(alert.status).toLowerCase() !== "open") {
            showToast("This alert is no longer open.", "warning");
            return;
        }

        state.closingAlertId = String(alertId);
        renderPriorityAlert();

        try {
            const result = await WatchtowerAPI.closeWatchtowerAlert(
                state.contractId,
                alertId
            );

            if (result?.success === false) {
                throw new Error(
                    result.message || "The backend did not close the alert."
                );
            }

            // Only close locally after the backend request succeeds.
            state.alerts = state.alerts.map(candidate =>
                String(candidate.id) === String(alertId)
                    ? { ...candidate, status: "closed" }
                    : candidate
            );

            state.confirmingAlertId = null;
            state.closingAlertId = null;

            const [alertsResult, coreResult] = await Promise.allSettled([
                WatchtowerAPI.getWatchtowerAlerts(state.contractId),
                WatchtowerAPI.getWatchtower(state.contractId)
            ]);

            if (alertsResult.status === "fulfilled") {
                state.alerts = listFrom(alertsResult.value, "alerts");
            }

            if (coreResult.status === "fulfilled") {
                state.watchtower = coreResult.value?.watchtower || state.watchtower;

                if (Array.isArray(coreResult.value?.items)) {
                    state.items = coreResult.value.items;
                }
            }

            if (state.selectedItem) {
                state.selectedItem = state.items.find(candidate =>
                    String(candidate.id) === String(state.selectedItem.id)
                ) || state.selectedItem;

                state.selectedEvaluation =
                    evaluationForItem(state.selectedItem.id);

                state.selectedAlert =
                    alertForItem(state.selectedItem.id);
            }

            updateContractMeta();
            renderAll();

            showToast(
                "Alert record closed. This does not confirm that the underlying issue has been resolved.",
                "success"
            );

        } catch (error) {
            state.closingAlertId = null;
            renderPriorityAlert();

            showToast(
                `Could not close alert: ${error.message}`,
                "error"
            );

            console.error("[Watchtower] Close alert failed:", error);
        }
    }


    /* ========================================================
       CONTRACT SOURCE MODAL
    ======================================================== */

    function openEvidenceModal() {
        const item = state.selectedItem;
        const modal = $("#evidenceModal");

        if (!item || !modal) {
            showToast("Select a clause first.", "warning");
            return;
        }

        const event = eventForItem(item.id);

        state.previousFocus = document.activeElement;

        $("#modalEyebrow").textContent = "CONTRACT SOURCE";
        $("#modalTitle").textContent =
            `Clause ${padClause(item.clause_id)} · ${safeText(
                item.title,
                item.clause_title || "Monitored provision"
            )}`;

        $("#modalLead").textContent =
            "Contract language associated with this monitored provision.";

        $("#modalEvidence").textContent =
            evidenceFor(item) ||
            "The backend did not return source text for this provision.";

        $("#modalEvent").textContent =
            upper(event ? eventType(event) : "NO MATCHED EVENT");

        $("#modalClause").textContent = padClause(item.clause_id);
        $("#modalResult").textContent = resultFor(item);

        modal.classList.add("open");
        modal.setAttribute("aria-hidden", "false");
        document.body.classList.add("modal-open");

        $(".modal-close", modal)?.focus();
    }

    function closeEvidenceModal() {
        const modal = $("#evidenceModal");
        if (!modal) return;

        modal.classList.remove("open");
        modal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("modal-open");

        state.previousFocus?.focus?.();
    }


    /* ========================================================
       TOASTS AND ERRORS
    ======================================================== */

    function showToast(message, type = "info") {
        let toast = $("#watchtowerToast");

        if (!toast) {
            toast = document.createElement("div");
            toast.id = "watchtowerToast";
            toast.className = "watchtower-toast";
            toast.setAttribute("role", "status");
            toast.setAttribute("aria-live", "polite");
            document.body.appendChild(toast);
        }

        toast.className = `watchtower-toast toast-${type}`;
        toast.textContent = message;
        toast.classList.add("is-visible");

        if (state.toastTimer) clearTimeout(state.toastTimer);

        state.toastTimer = setTimeout(() => {
            toast.classList.remove("is-visible");
        }, 5000);
    }

    function showError(message) {
        const banner = $("#watchtowerBackendError");
        const content = $("#watchtowerErrorMessage");

        if (!banner || !content) return;

        if (!message) {
            banner.hidden = true;
            content.textContent = "";
            return;
        }

        content.textContent = message;
        banner.hidden = false;
    }


    /* ========================================================
       ANIMATIONS
    ======================================================== */

    function setupScrollReveal() {
        const sections = $$(".reveal");

        if (!("IntersectionObserver" in window)) {
            sections.forEach(section =>
                section.classList.add("is-visible")
            );
            return;
        }

        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            });
        }, {
            threshold: 0.12,
            rootMargin: "0px 0px -45px 0px"
        });

        sections.forEach(section => observer.observe(section));

        const intro = $("#intro");

        if (intro && intro.getBoundingClientRect().top < innerHeight) {
            intro.classList.add("is-visible");
        }
    }

    function animateSelection() {
        const area = $(".clause-area");

        if (!area) return;

        area.classList.remove("selection-pulse");
        void area.offsetWidth;
        area.classList.add("selection-pulse");

        requestAnimationFrame(drawSignalConnections);
    }


    /* ========================================================
       INTERACTIONS
    ======================================================== */

    function setupInteractions() {
        document.addEventListener("click", event => {
            const sourceButton = event.target.closest("#evidenceButton");

            if (sourceButton) {
                event.preventDefault();
                openEvidenceModal();
                return;
            }

            const closeModalButton =
                event.target.closest("[data-close-modal]");

            if (closeModalButton) {
                event.preventDefault();
                closeEvidenceModal();
                return;
            }

            const clauseButton =
                event.target.closest("[data-watch-item-id]");

            if (clauseButton && !clauseButton.disabled) {
                event.preventDefault();
                selectItem(clauseButton.dataset.watchItemId);
                return;
            }

            const viewButton =
                event.target.closest("[data-alert-view]");

            if (viewButton) {
                event.preventDefault();
                viewClause(viewButton.dataset.alertView);
                return;
            }

            const closeButton =
                event.target.closest("[data-alert-close]");

            if (closeButton) {
                event.preventDefault();
                state.confirmingAlertId =
                    String(closeButton.dataset.alertClose);
                renderPriorityAlert();
                return;
            }

            const confirmButton =
                event.target.closest("[data-alert-confirm]");

            if (confirmButton) {
                event.preventDefault();
                closeAlert(confirmButton.dataset.alertConfirm);
                return;
            }

            const cancelButton =
                event.target.closest("[data-alert-cancel]");

            if (cancelButton) {
                event.preventDefault();
                state.confirmingAlertId = null;
                renderPriorityAlert();
            }
        });

        document.addEventListener("keydown", event => {
            if (event.key === "Escape") {
                closeEvidenceModal();

                if (state.confirmingAlertId !== null) {
                    state.confirmingAlertId = null;
                    renderPriorityAlert();
                }
            }
        });

        window.addEventListener("resize", () =>
            requestAnimationFrame(drawSignalConnections)
        );
    }


    /* ========================================================
       INITIALIZE
    ======================================================== */

    async function init() {
        setupInteractions();
        setupScrollReveal();
        await loadWatchtower();
    }

    window.addEventListener("message", event => {
        if (event.source !== window.parent ||
            event.origin !== window.location.origin ||
            event.data?.type !== "clauseguard:watchtower-refresh") {
            return;
        }
        loadWatchtower();
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    } else {
        init();
    }

})();
