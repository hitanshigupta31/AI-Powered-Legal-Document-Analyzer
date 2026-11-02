
/* ============================================================
   CLAUSEGUARD — WATCHTOWER API
   Same-origin requests, authenticated sessions and decisions.
============================================================ */

const WATCHTOWER_API_BASE = "";

async function watchtowerFetch(url, options = {}) {
    const response = await fetch(url, {
        credentials: "include",
        ...options,
        headers: {
            Accept: "application/json",
            ...(options.body
                ? { "Content-Type": "application/json" }
                : {}),
            ...(options.headers || {})
        }
    });

    let data = null;

    try {
        data = await response.json();
    } catch (_) {
        data = null;
    }

    if (response.status === 401 || response.status === 403) {
        window.location.href = "/login";
        throw new Error("Your session has expired. Please sign in again.");
    }

    if (!response.ok) {
        throw new Error(
            data?.detail ||
            data?.message ||
            `Watchtower request failed (${response.status}).`
        );
    }

    return data;
}

async function getContracts() {
    return watchtowerFetch(
        `${WATCHTOWER_API_BASE}/api/contracts`
    );
}

async function getWatchtower(contractId) {
    return watchtowerFetch(
        `${WATCHTOWER_API_BASE}/api/contracts/${encodeURIComponent(contractId)}/watchtower`
    );
}

async function getWatchtowerEvents(contractId) {
    return watchtowerFetch(
        `${WATCHTOWER_API_BASE}/api/contracts/${encodeURIComponent(contractId)}/watchtower/events`
    );
}

async function getWatchtowerAlerts(contractId, status = null) {
    let url =
        `${WATCHTOWER_API_BASE}/api/contracts/${encodeURIComponent(contractId)}/watchtower/alerts`;

    if (status) {
        url += `?status=${encodeURIComponent(status)}`;
    }

    return watchtowerFetch(url);
}

async function getWatchtowerEvaluations(contractId) {
    return watchtowerFetch(
        `${WATCHTOWER_API_BASE}/api/contracts/${encodeURIComponent(contractId)}/watchtower/evaluations`
    );
}

async function getWatchtowerDecisions(contractId, watchItemId = null) {
    let url =
        `${WATCHTOWER_API_BASE}/api/contracts/${encodeURIComponent(contractId)}/watchtower/decisions`;

    if (watchItemId !== null && watchItemId !== undefined) {
        url += `?watch_item_id=${encodeURIComponent(watchItemId)}`;
    }

    return watchtowerFetch(url);
}

async function recordWatchtowerDecision(
    contractId,
    watchItemId,
    decision
) {
    return watchtowerFetch(
        `${WATCHTOWER_API_BASE}/api/contracts/${encodeURIComponent(contractId)}/watchtower/decisions`,
        {
            method: "POST",
            body: JSON.stringify({
                watch_item_id: Number(watchItemId),
                decision
            })
        }
    );
}

async function getWatchtowerPreview(contractId) {
    return watchtowerFetch(
        `${WATCHTOWER_API_BASE}/api/contracts/${encodeURIComponent(contractId)}/watchtower/preview`
    );
}

async function activateWatchtower(contractId, watchItems = []) {
    return watchtowerFetch(
        `${WATCHTOWER_API_BASE}/api/contracts/${encodeURIComponent(contractId)}/watchtower/activate`,
        {
            method: "POST",
            body: JSON.stringify({
                watch_items: watchItems
            })
        }
    );
}

async function closeWatchtowerAlert(contractId, alertId) {
    return watchtowerFetch(
        `${WATCHTOWER_API_BASE}/api/contracts/${encodeURIComponent(contractId)}/watchtower/alerts/${encodeURIComponent(alertId)}/close`,
        {
            method: "POST"
        }
    );
}

window.WatchtowerAPI = {
    getContracts,
    getWatchtower,
    getWatchtowerEvents,
    getWatchtowerAlerts,
    getWatchtowerEvaluations,
    getWatchtowerDecisions,
    recordWatchtowerDecision,
    getWatchtowerPreview,
    activateWatchtower,
    closeWatchtowerAlert
};
