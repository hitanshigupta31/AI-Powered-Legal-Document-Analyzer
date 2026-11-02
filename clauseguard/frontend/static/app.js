/* ============================================================
   CLAUSEGUARD — FRONTEND LOGIC
============================================================ */


/* ============================================================
   APPLICATION STATE
========================================================== */

let currentData = null;

let currentClauses = [];

let activeRisk = null;

let activeClauseId = null;

let currentUser = null;

// Chat state
let currentContractId = null;
let chatMessages = [];
let isChatLoading = false;


/* ============================================================
   DOM REFERENCES
============================================================ */

const els = {

    errorBanner:
        document.getElementById(
            "errorBanner"
        ),

    uploadView:
        document.getElementById(
            "uploadView"
        ),

    processingView:
        document.getElementById(
            "processingView"
        ),

    overviewView:
        document.getElementById(
            "overviewView"
        ),

    groupView:
        document.getElementById(
            "groupView"
        ),

    askContractView:
        document.getElementById(
            "askContractView"
        ),

    breadcrumbPage:
        document.getElementById(
            "breadcrumbPage"
        ),

    fileInput:
        document.getElementById(
            "fileInput"
        ),

    dropzone:
        document.getElementById(
            "dropzone"
        ),

    dropTitle:
        document.getElementById(
            "dropTitle"
        ),

    dropSubtitle:
        document.getElementById(
            "dropSubtitle"
        ),

    selectedFile:
        document.getElementById(
            "selectedFile"
        ),

    analyzeFileBtn:
        document.getElementById(
            "analyzeFileBtn"
        ),

    progressBar:
        document.getElementById(
            "progressBar"
        ),

    processingTitle:
        document.getElementById(
            "processingTitle"
        ),

    processingSubtitle:
        document.getElementById(
            "processingSubtitle"
        ),

    overallScore:
        document.getElementById(
            "overallScore"
        ),

    totalClauses:
        document.getElementById(
            "totalClauses"
        ),

    attentionCount:
        document.getElementById(
            "attentionCount"
        ),

    lowCount:
        document.getElementById(
            "lowCount"
        ),

    mediumCount:
        document.getElementById(
            "mediumCount"
        ),

    highCount:
        document.getElementById(
            "highCount"
        ),

    priorityGrid:
        document.getElementById(
            "priorityGrid"
        ),

    documentMeta:
        document.getElementById(
            "documentMeta"
        ),

    groupEyebrow:
        document.getElementById(
            "groupEyebrow"
        ),

    groupTitle:
        document.getElementById(
            "groupTitle"
        ),

    groupSubtitle:
        document.getElementById(
            "groupSubtitle"
        ),

    groupCountLabel:
        document.getElementById(
            "groupCountLabel"
        ),

    clauseGrid:
        document.getElementById(
            "clauseGrid"
        ),

    detailPanel:
        document.getElementById(
            "detailPanel"
        ),

    profileInitials:
        document.getElementById(
            "profileInitials"
        ),

    profileName:
        document.getElementById(
            "profileName"
        ),

    profileEmail:
        document.getElementById(
            "profileEmail"
        ),

    logoutButton:
        document.getElementById(
            "logoutButton"
        ),

    // Chat elements
    chatMessages:
        document.getElementById(
            "chatMessages"
        ),

    chatStarter:
        document.getElementById(
            "chatStarter"
        ),

    chatInput:
        document.getElementById(
            "chatInput"
        ),

    chatSendBtn:
        document.getElementById(
            "chatSendBtn"
        ),

    clearChatBtn:
        document.getElementById(
            "clearChatBtn"
        ),

    chatContextLabel:
        document.getElementById(
            "chatContextLabel"
        ),

    chatContractName:
        document.getElementById(
            "chatContractName"
        ),

    chatContextStatus:
        document.getElementById(
            "chatContextStatus"
        ),

    starterButtons:
        document.querySelectorAll(
            ".starter-btn"
        )
};


/* ============================================================
   AUTHENTICATED USER
============================================================ */

async function loadCurrentUser() {

    try {

        const response =
            await fetch(
                "/api/auth/me"
            );


        if (
            response.status === 401 ||
            response.status === 403
        ) {

            window.location.href =
                "/login";

            return false;

        }


        if (!response.ok) {

            throw new Error(
                "Unable to load account."
            );

        }


        const data =
            await response.json();


        currentUser =
            data.user;


        updateUserProfile();


        return true;


    } catch (error) {

        console.error(
            "USER LOAD ERROR:",
            error
        );


        window.location.href =
            "/login";


        return false;

    }

}


/* ============================================================
   USER PROFILE
============================================================ */

function updateUserProfile() {

    if (!currentUser) {

        return;

    }


    const name =
        currentUser.name ||
        "User";


    const email =
        currentUser.email ||
        "Personal workspace";


    if (els.profileName) {

        els.profileName.textContent =
            name;

    }


    if (els.profileEmail) {

        els.profileEmail.textContent =
            email;

    }


    if (els.profileInitials) {

        const parts =
            name
                .trim()
                .split(/\s+/)
                .filter(Boolean);


        let initials =
            "US";


        if (
            parts.length >= 2
        ) {

            initials =
                (
                    parts[0][0] +
                    parts[1][0]
                ).toUpperCase();


        } else if (
            parts.length === 1
        ) {

            initials =
                parts[0]
                    .slice(
                        0,
                        2
                    )
                    .toUpperCase();

        }


        els.profileInitials.textContent =
            initials;

    }

}


/* ============================================================
   LOGOUT
============================================================ */

async function logoutUser() {

    if (els.logoutButton) {

        els.logoutButton.disabled =
            true;

        els.logoutButton.textContent =
            "Logging out…";

    }


    try {

        await fetch(
            "/api/auth/logout",
            {
                method:
                    "POST"
            }
        );


    } catch (error) {

        console.error(
            "LOGOUT ERROR:",
            error
        );


    } finally {

        window.location.href =
            "/login";

    }

}


/* ============================================================
   ERROR HANDLING
============================================================ */

function showError(
    message
) {

    if (!els.errorBanner) {

        return;

    }


    els.errorBanner.textContent =
        message;


    els.errorBanner.classList.remove(
        "hidden"
    );

}


function clearError() {

    if (!els.errorBanner) {

        return;

    }


    els.errorBanner.textContent =
        "";


    els.errorBanner.classList.add(
        "hidden"
    );

}


/* ============================================================
   HTML ESCAPING
============================================================ */

function escapeHtml(
    value
) {

    return String(
        value ?? ""
    )
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );

}


/* ============================================================
   GENERAL HELPERS
============================================================ */

function clauseTitle(
    clause
) {

    if (clause.title) {

        return clause.title;

    }


    if (clause.clause_type) {

        return clause.clause_type;

    }


    return (
        `Clause ${
            clause.clause_id ?? ""
        }`
    );

}


function riskClass(
    level
) {

    return String(
        level || "LOW"
    ).toLowerCase();

}


function normalizeClauses(
    data
) {

    return Array.isArray(
        data?.clauses
    )
        ? data.clauses
        : [];

}


/* ============================================================
   SUMMARY
============================================================ */

function calculateSummary(
    clauses
) {

    const counts = {

        HIGH: 0,

        MEDIUM: 0,

        LOW: 0

    };


    clauses.forEach(
        (
            clause
        ) => {

            const level =
                String(
                    clause.risk_level ||
                    "LOW"
                ).toUpperCase();


            if (
                counts[level] !==
                undefined
            ) {

                counts[level] += 1;

            } else {

                counts.LOW += 1;

            }

        }
    );


    const attention =
        counts.HIGH +
        counts.MEDIUM;


    const scores =
        clauses
            .map(
                (
                    clause
                ) =>
                    Number(
                        clause.risk_score
                    )
            )
            .filter(
                Number.isFinite
            );


    const average =
        scores.length

            ? Math.round(
                scores.reduce(
                    (
                        total,
                        score
                    ) =>
                        total + score,
                    0
                )
                /
                scores.length
            )

            : 0;


    return {

        ...counts,

        attention,

        average

    };

}


/* ============================================================
   VIEW MANAGEMENT
============================================================ */

function showView(view) {
    const viewIds = [
        "uploadView",
        "processingView",
        "overviewView",
        "groupView",
        "askContractView",
        "watchtowerView",
        "analysisHistoryView"
    ];

    viewIds.forEach((viewId) => {
        const element = document.getElementById(viewId);

        if (element) {
            element.classList.add("hidden");
        }
    });

    const targetView =
        typeof view === "string"
            ? document.getElementById(view)
            : view;

    if (!targetView) {
        console.error("showView: target view not found:", view);
        return;
    }

    targetView.classList.remove("hidden");
}


function setBreadcrumb(
    text
) {

    if (
        els.breadcrumbPage
    ) {

        els.breadcrumbPage.textContent =
            text;

    }

}


/* ============================================================
   UPLOAD
============================================================ */

function resetUploadState() {

    if (
        els.fileInput
    ) {

        els.fileInput.value =
            "";

    }


    if (
        els.analyzeFileBtn
    ) {

        els.analyzeFileBtn.disabled =
            true;

    }


    if (
        els.dropTitle
    ) {

        els.dropTitle.textContent =
            "Drop your contract here";

    }


    if (
        els.dropSubtitle
    ) {

        els.dropSubtitle.textContent =
            "or click to choose a PDF or DOCX";

    }


    if (
        els.selectedFile
    ) {

        els.selectedFile.textContent =
            "";

        els.selectedFile.classList.add(
            "hidden"
        );

    }

}


function openUploadView() {

    clearError();

    resetUploadState();


    showView(
        els.uploadView
    );


    setBreadcrumb(
        "Contract review"
    );

    setNavActive("overviewNav");

    window.scrollTo(
        {
            top:
                0,

            behavior:
                "smooth"
        }
    );

}


function updateSelectedFile(
    file
) {

    if (!file) {

        resetUploadState();

        return;

    }


    if (
        els.dropTitle
    ) {

        els.dropTitle.textContent =
            "Contract selected";

    }


    if (
        els.dropSubtitle
    ) {

        els.dropSubtitle.textContent =
            "Ready to analyze";

    }


    if (
        els.selectedFile
    ) {

        els.selectedFile.textContent =
            file.name ||
            "Selected document";


        els.selectedFile.classList.remove(
            "hidden"
        );

    }


    if (
        els.analyzeFileBtn
    ) {

        els.analyzeFileBtn.disabled =
            false;

    }

}


/* ============================================================
   PROCESSING ANIMATION
============================================================ */

function runProcessingAnimation(
    fileName
) {

    showView(
        els.processingView
    );


    setBreadcrumb(
        "Analyzing"
    );


    if (
        els.processingTitle
    ) {

        els.processingTitle.textContent =
            `Reviewing ${fileName}`;

    }


    if (
        els.processingSubtitle
    ) {

        els.processingSubtitle.textContent =
            "Extracting text, organizing clauses and checking risk signals.";

    }


    if (
        els.progressBar
    ) {

        els.progressBar.style.width =
            "8%";

    }


    [
        "step1",
        "step2",
        "step3"

    ].forEach(
        (
            id
        ) => {

            const step =
                document.getElementById(
                    id
                );


            if (step) {

                step.classList.remove(
                    "active"
                );

            }

        }
    );


    const firstStep =
        document.getElementById(
            "step1"
        );


    if (firstStep) {

        firstStep.classList.add(
            "active"
        );

    }


    const stages = [

        {
            width:
                "34%",

            id:
                "step1"
        },

        {
            width:
                "68%",

            id:
                "step2"
        },

        {
            width:
                "92%",

            id:
                "step3"
        }

    ];


    stages.forEach(
        (
            stage,
            index
        ) => {

            window.setTimeout(
                () => {

                    if (
                        els.progressBar
                    ) {

                        els.progressBar.style.width =
                            stage.width;

                    }


                    [
                        "step1",
                        "step2",
                        "step3"

                    ].forEach(
                        (
                            id
                        ) => {

                            const step =
                                document.getElementById(
                                    id
                                );


                            if (step) {

                                step.classList.remove(
                                    "active"
                                );

                            }

                        }
                    );


                    const activeStep =
                        document.getElementById(
                            stage.id
                        );


                    if (
                        activeStep
                    ) {

                        activeStep.classList.add(
                            "active"
                        );

                    }

                },

                380 +
                index * 420
            );

        }
    );

}


/* ============================================================
   OVERVIEW
============================================================ */

function renderOverview(
    data
) {

    currentData =
        data;

    // Remember the active contract so Watchtower can open the same
    // contract after navigation or a page refresh.
    if (data?.contract_id !== null && data?.contract_id !== undefined) {
        try {
            localStorage.setItem(
                "clauseguard.activeContractId",
                String(data.contract_id)
            );
        } catch (error) {
            console.warn("Could not persist the active contract ID:", error);
        }
    }

    currentClauses =
        normalizeClauses(
            data
        );


    const calculated =
        calculateSummary(
            currentClauses
        );


    const summary =
        data?.summary ||
        {};


    const overall =
        Number.isFinite(
            Number(
                summary.overall_score
            )
        )

            ? Number(
                summary.overall_score
            )

            : calculated.average;


    const high =
        Number.isFinite(
            Number(
                summary.high_risk_count
            )
        )

            ? Number(
                summary.high_risk_count
            )

            : calculated.HIGH;


    const medium =
        Number.isFinite(
            Number(
                summary.medium_risk_count
            )
        )

            ? Number(
                summary.medium_risk_count
            )

            : calculated.MEDIUM;


    const low =
        Number.isFinite(
            Number(
                summary.low_risk_count
            )
        )

            ? Number(
                summary.low_risk_count
            )

            : calculated.LOW;


    const attention =
        Number.isFinite(
            Number(
                summary.attention_count
            )
        )

            ? Number(
                summary.attention_count
            )

            : high +
              medium;


    if (
        els.overallScore
    ) {

        els.overallScore.textContent =
            overall;

    }


    if (
        els.totalClauses
    ) {

        els.totalClauses.textContent =
            currentClauses.length;

    }


    if (
        els.attentionCount
    ) {

        els.attentionCount.textContent =
            attention;

    }


    if (
        els.highCount
    ) {

        els.highCount.textContent =
            high;

    }


    if (
        els.mediumCount
    ) {

        els.mediumCount.textContent =
            medium;

    }


    if (
        els.lowCount
    ) {

        els.lowCount.textContent =
            low;

    }


    const fileName =
        data?.filename ||
        data?.document_name ||
        "Uploaded agreement";


    if (
        els.documentMeta
    ) {

        els.documentMeta.textContent =
            `${fileName} · ${
                currentClauses.length
            } clause${
                currentClauses.length === 1
                    ? ""
                    : "s"
            } organized for review.`;

    }


    renderPriorityFindings();


    showView(
        els.overviewView
    );


    setBreadcrumb(
        "Contract review"
    );


    window.scrollTo(
        {
            top:
                0,

            behavior:
                "smooth"
        }
    );

}


/* ============================================================
   PRIORITY FINDINGS
============================================================ */

function renderPriorityFindings() {

    if (
        !els.priorityGrid
    ) {

        return;

    }


    const sorted =
        [...currentClauses]
            .sort(
                (
                    a,
                    b
                ) =>
                    Number(
                        b.risk_score ||
                        0
                    )
                    -
                    Number(
                        a.risk_score ||
                        0
                    )
            )
            .slice(
                0,
                4
            );


    if (
        !sorted.length
    ) {

        els.priorityGrid.innerHTML = `

            <div class="priority-card">

                <div class="priority-main">

                    <div class="priority-title">
                        No findings returned
                    </div>

                    <div class="priority-meta">
                        The backend did not return
                        any clause results.
                    </div>

                </div>

            </div>

        `;


        return;

    }


    els.priorityGrid.innerHTML =
        sorted
            .map(
                (
                    clause
                ) => {

                    const level =
                        String(
                            clause.risk_level ||
                            "LOW"
                        ).toUpperCase();


                    return `

                        <button
                            class="priority-card"
                            type="button"
                            data-clause-id="${escapeHtml(
                                clause.clause_id
                            )}"
                        >

                            <div class="priority-main">

                                <div class="priority-title">
                                    ${escapeHtml(
                                        clauseTitle(
                                            clause
                                        )
                                    )}
                                </div>


                                <div class="priority-meta">

                                    Clause
                                    ${escapeHtml(
                                        clause.clause_id
                                    )}

                                    ·

                                    ${escapeHtml(
                                        clause.clause_type ||
                                        "Other"
                                    )}

                                    ·

                                    ${escapeHtml(
                                        level
                                    )}

                                </div>

                            </div>


                            <div
                                class="
                                    priority-score
                                    priority-${riskClass(
                                        level
                                    )}
                                "
                            >

                                ${escapeHtml(
                                    clause.risk_score ??
                                    0
                                )}

                            </div>

                        </button>

                    `;

                }
            )
            .join("");


    els.priorityGrid
        .querySelectorAll(
            "[data-clause-id]"
        )
        .forEach(
            (
                button
            ) => {

                button.addEventListener(
                    "click",
                    () => {

                        const id =
                            String(
                                button.dataset
                                    .clauseId
                            );


                        const clause =
                            currentClauses.find(
                                (
                                    item
                                ) =>
                                    String(
                                        item.clause_id
                                    ) === id
                            );


                        if (!clause) {

                            return;

                        }


                        activeRisk =
                            String(
                                clause.risk_level ||
                                "LOW"
                            ).toUpperCase();


                        openRiskGroup(
                            activeRisk,
                            id
                        );

                    }
                );

            }
        );

}


/* ============================================================
   OPEN RISK GROUP
============================================================ */

function openRiskGroup(
    level,
    selectedId = null
) {

    activeRisk =
        level;


    const filtered =
        currentClauses.filter(
            (
                clause
            ) =>
                String(
                    clause.risk_level ||
                    "LOW"
                ).toUpperCase() ===
                level
        );


    activeClauseId =
        selectedId ||
        (
            filtered[0]
                ? filtered[0].clause_id
                : null
        );


    const label =
        level.charAt(0) +
        level
            .slice(1)
            .toLowerCase();


    if (
        els.groupEyebrow
    ) {

        els.groupEyebrow.textContent =
            `${level} RISK`;

    }


    if (
        els.groupTitle
    ) {

        els.groupTitle.textContent =
            `${label} risk clauses`;

    }


    if (
        els.groupSubtitle
    ) {

        els.groupSubtitle.textContent =
            filtered.length

                ? "Select a clause to inspect the contract text and the signals detected by the current engine."

                : `No clauses were assigned to the ${label.toLowerCase()} risk category.`;

    }


    if (
        els.groupCountLabel
    ) {

        els.groupCountLabel.textContent =
            `${filtered.length} clause${
                filtered.length === 1
                    ? ""
                    : "s"
            }`;

    }


    renderClauseCards(
        filtered
    );


    if (
        filtered.length
    ) {

        const selected =
            filtered.find(
                (
                    clause
                ) =>
                    String(
                        clause.clause_id
                    ) ===
                    String(
                        activeClauseId
                    )
            )
            ||
            filtered[0];


        activeClauseId =
            selected.clause_id;


        renderDetail(
            selected
        );


    } else {

        if (
            els.detailPanel
        ) {

            els.detailPanel.innerHTML = `

                <div class="detail-empty">

                    <div class="detail-empty-mark">
                        C
                    </div>

                    <h3>
                        No clauses here
                    </h3>

                    <p>
                        This risk category currently
                        contains no detected clauses.
                    </p>

                </div>

            `;

        }

    }


    showView(
        els.groupView
    );


    setBreadcrumb(
        `${label} risk`
    );


    window.scrollTo(
        {
            top:
                0,

            behavior:
                "smooth"
        }
    );

}


/* ============================================================
   CLAUSE CARDS
============================================================ */

function renderReviewPath() {
    // The review screen now uses a full-width findings → detail flow.
    // Remove any guide card left by a stale render; do not inject filler content.
    document.querySelectorAll("#groupView .review-path-card").forEach((node) => node.remove());
}

function renderClauseCards(
    clauses
) {

    if (
        !els.clauseGrid
    ) {

        return;

    }


    els.clauseGrid.classList.toggle("single-clause", clauses.length === 1);

    if (
        !clauses.length
    ) {

        els.clauseGrid.innerHTML = `

            <div class="clause-card">

                <h3>
                    No clauses found
                </h3>

                <div class="clause-preview">
                    There are no clause-level
                    findings in this category.
                </div>

            </div>

        `;

        renderReviewPath(0);
        return;

    }


    els.clauseGrid.innerHTML =
        clauses
            .map(
                (
                    clause,
                    index
                ) => {

                    const level =
                        String(
                            clause.risk_level ||
                            "LOW"
                        ).toUpperCase();


                    const preview =
                        String(
                            clause.text ||
                            ""
                        )
                            .replace(
                                /\s+/g,
                                " "
                            )
                            .trim();


                    const active =
                        String(
                            clause.clause_id
                        ) ===
                        String(
                            activeClauseId
                        )
                            ? "active"
                            : "";


                    return `

                        <button
                            class="
                                clause-card
                                ${active}
                            "
                            type="button"
                            data-clause-id="${escapeHtml(
                                clause.clause_id
                            )}"
                            style="--card-delay: ${Math.min(index, 8) * 45}ms"
                            aria-label="Inspect clause ${escapeHtml(clause.clause_id)}: ${escapeHtml(clauseTitle(clause))}"
                        >

                            <div class="clause-top">

                                <span class="clause-id">

                                    CLAUSE
                                    ${escapeHtml(
                                        clause.clause_id
                                    )}

                                </span>


                                <span
                                    class="
                                        clause-risk
                                        priority-${riskClass(
                                            level
                                        )}
                                    "
                                >

                                    ${escapeHtml(
                                        level
                                    )}

                                </span>

                            </div>


                            <h3>

                                ${escapeHtml(
                                    clauseTitle(
                                        clause
                                    )
                                )}

                            </h3>


                            <div class="clause-preview">

                                ${escapeHtml(
                                    preview ||
                                    "No clause text returned."
                                )}

                            </div>

                            <div class="clause-card-footer">
                                <span>Inspect clause</span>
                                <span class="clause-card-arrow" aria-hidden="true">↗</span>
                            </div>

                        </button>

                    `;

                }
            )
            .join("");

    renderReviewPath(clauses.length);

    els.clauseGrid
        .querySelectorAll(
            "[data-clause-id]"
        )
        .forEach(
            (
                button
            ) => {

                button.addEventListener(
                    "click",
                    () => {

                        activeClauseId =
                            button.dataset
                                .clauseId;


                        const clause =
                            clauses.find(
                                (
                                    item
                                ) =>
                                    String(
                                        item.clause_id
                                    ) ===
                                    String(
                                        activeClauseId
                                    )
                            );


                        els.clauseGrid
                            .querySelectorAll("[data-clause-id]")
                            .forEach((card) => {
                                card.classList.toggle(
                                    "active",
                                    String(card.dataset.clauseId) === String(activeClauseId)
                                );
                            });

                        if (clause) {
                            renderDetail(clause);

                            // After a clause is selected, take the user directly to
                            // its detail section instead of requiring them to guess
                            // that more content sits below the findings grid.
                            window.requestAnimationFrame(() => {
                                const prefersReducedMotion = window.matchMedia(
                                    "(prefers-reduced-motion: reduce)"
                                ).matches;

                                els.detailPanel.scrollIntoView({
                                    behavior: prefersReducedMotion ? "auto" : "smooth",
                                    block: "start"
                                });
                            });
                        }

                    }
                );

            }
        );

}


/* ============================================================
   CLAUSE DETAIL
============================================================ */

function renderDetail(
    clause
) {
    if (!els.detailPanel) return;

    // A newly selected clause should always open at the beginning of its detail.
    els.detailPanel.scrollTop = 0;

    const level = String(clause.risk_level || "LOW").toUpperCase();
    const flags = Array.isArray(clause.risk_flags) ? clause.risk_flags : [];
    const reasons = Array.isArray(clause.risk_reasons) ? clause.risk_reasons : [];
    const clauseText = String(clause.text || "No clause text returned.").trim();
    const previewLimit = 290;
    const hasLongText = clauseText.length > previewLimit;
    const clausePreview = hasLongText
        ? `${clauseText.slice(0, previewLimit).trimEnd()}…`
        : clauseText;

    const listHtml = (items, emptyMessage) => items.length
        ? `<ul class="detail-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
        : `<p class="detail-empty-copy">${escapeHtml(emptyMessage)}</p>`;

    const sourceDisclosure = hasLongText
        ? `
            <details class="clause-source-details">
                <summary>
                    <span>Read complete clause text</span>
                    <span class="source-summary-arrow" aria-hidden="true">＋</span>
                </summary>
                <div class="clause-source-full">${escapeHtml(clauseText)}</div>
            </details>
        `
        : "";

    els.detailPanel.innerHTML = `
        <header class="detail-panel-header">
            <div class="detail-header-main">
                <div class="detail-kicker">
                    <span class="detail-kicker-mark" aria-hidden="true">§</span>
                    <span>CLAUSE ${escapeHtml(clause.clause_id)}</span>
                    <span class="detail-kicker-divider">/</span>
                    <span>${escapeHtml(clause.clause_type || "OTHER")}</span>
                </div>
                <h2 class="detail-title">${escapeHtml(clauseTitle(clause))}</h2>
                <p class="detail-subtitle">Review the detected signals, then use the AI insight for a deeper explanation.</p>
            </div>
            <div class="detail-meta" aria-label="Clause risk metadata">
                <span class="detail-chip risk-chip risk-${riskClass(level)} priority-${riskClass(level)}">
                    <span class="risk-chip-dot" aria-hidden="true"></span>
                    ${escapeHtml(level)} RISK
                </span>
                <span class="detail-chip score-chip">
                    <span>SCORE</span>
                    <strong>${escapeHtml(clause.risk_score ?? 0)}</strong>
                </span>
            </div>
        </header>

        <section class="ai-placeholder" aria-live="polite" aria-busy="false">
            <div class="ai-prompt-topline">
                <span class="ai-mark" aria-hidden="true">✦</span>
                <div class="ai-prompt-labels">
                    <div class="ai-label">AI-ASSISTED EXPLANATION</div>
                    <span class="ai-model-tag">QWEN3 · 4B</span>
                </div>
                <span class="ai-status-indicator"><i aria-hidden="true"></i> Ready</span>
            </div>
            <h3 class="ai-prompt-title">Understand this clause</h3>
            <p class="ai-prompt-copy">Get a plain-language explanation, why it may matter, points to review, and a negotiation direction.</p>
            <button type="button" class="ai-analyze-btn" id="aiAnalyzeButton">
                <span>Analyze with AI</span>
                <span class="ai-button-arrow" aria-hidden="true">↗</span>
            </button>
            <div class="ai-prompt-footnote">AI-generated guidance · Check the explanation against the original wording.</div>
        </section>

        <section class="detail-evidence-section" aria-label="Rule-based risk findings">
            <div class="detail-section-heading">
                <span class="detail-section-number">01</span>
                <div>
                    <h3>Risk signals</h3>
                    <p>What the current review engine detected.</p>
                </div>
            </div>
            <div class="detail-evidence-card">
                <div class="detail-evidence-label"><span class="evidence-symbol" aria-hidden="true">⌁</span> Detected signals</div>
                ${listHtml(flags, "No specific risk flags were returned by the current engine.")}
            </div>
            <div class="detail-evidence-card detail-reasons-card">
                <div class="detail-evidence-label"><span class="evidence-symbol" aria-hidden="true">↳</span> Why it was flagged</div>
                ${listHtml(reasons, "No detailed reason was returned by the current engine.")}
            </div>
        </section>

        <section class="detail-source-section" aria-label="Original contract wording">
            <div class="detail-section-heading">
                <span class="detail-section-number">02</span>
                <div>
                    <h3>Original wording</h3>
                    <p>Keep the analysis grounded in the source text.</p>
                </div>
            </div>
            <div class="detail-source-card">
                <div class="source-card-topline">
                    <span class="source-document-mark" aria-hidden="true">§</span>
                    <span>CONTRACT EXCERPT</span>
                    <span class="source-original-tag">Original text</span>
                </div>
                <blockquote class="clause-text-preview">${escapeHtml(clausePreview)}</blockquote>
                ${sourceDisclosure}
            </div>
        </section>
    `;

    const aiButton = document.getElementById("aiAnalyzeButton");
    if (aiButton) {
        aiButton.addEventListener("click", () => analyzeClauseWithAI(clause));
    }
}

/* ============================================================
   AI ANALYSIS
============================================================ */

async function analyzeClauseWithAI(
    clause
) {

    const container =
        document.querySelector(
            ".ai-placeholder"
        );


    const button =
        document.getElementById(
            "aiAnalyzeButton"
        );


    if (!container) {

        console.error("AI: .ai-placeholder container not found");
        return;

    }


    if (button) {
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
        button.innerHTML = `
            <span class="ai-loading-spinner" aria-hidden="true"></span>
            <span>Generating insight…</span>
        `;
    }

    container.classList.add("is-loading");
    container.setAttribute("aria-busy", "true");


    try {

        const response =
            await fetch(
                "/api/ai/clause-insight",
                {

                    method:
                        "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body:
                        JSON.stringify(
                            clause
                        )

                }
            );


        /* ----------------------------------------------------
           AUTHENTICATION
        ----------------------------------------------------- */

        if (
            response.status === 401 ||
            response.status === 403
        ) {

            window.location.href =
                "/login";

            return;

        }


        /* ----------------------------------------------------
           READ RESPONSE
        ----------------------------------------------------- */

        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(

                data.detail ||

                "AI analysis failed."

            );

        }


        if (
            !data.insight
        ) {

            throw new Error(
                "AI returned an empty result."
            );

        }

        // Pass container directly to avoid re-querying DOM
        renderAIInsight(data.insight, container);


    } catch (error) {

        console.error("AI ERROR:", error);


        renderAIError(
            error.message ||
            "Unable to generate AI insight.",
            container
        );

    }

}


/* ============================================================
   NORMALIZE AI RESPONSE
============================================================ */

function normalizeAIInsight(
    insight
) {

    /* --------------------------------------------------------
       Future-proofing:
       if the backend ever returns a string, keep the UI
       working instead of crashing.
    --------------------------------------------------------- */

    if (
        typeof insight ===
        "string"
    ) {

        return {

            meaning:
                insight,

            why_it_matters:
                "",

            what_to_review:
                [],

            negotiation_suggestion:
                []

        };

    }


    return {

        meaning:
            insight?.meaning ||
            "",

        why_it_matters:
            insight?.why_it_matters ||
            "",

        what_to_review:
            Array.isArray(
                insight?.what_to_review
            )
                ? insight.what_to_review
                : [],

        negotiation_suggestion:
            Array.isArray(
                insight?.negotiation_suggestion
            )
                ? insight.negotiation_suggestion
                : []

    };

}


/* ============================================================
   RENDER AI INSIGHT
============================================================ */

function renderAIInsight(insight, container) {
    if (!container) {
        console.error("AI: renderAIInsight called with null container");
        return;
    }

    container.classList.remove("is-loading");
    container.setAttribute("aria-busy", "false");

    if (!insight) {
        container.innerHTML = `
            <div class="ai-error-state">
                <span class="ai-error-mark" aria-hidden="true">!</span>
                <div class="ai-label">AI INSIGHT</div>
                <h3>There was no insight to display</h3>
                <p>No AI insight was returned for this clause.</p>
            </div>
        `;
        return;
    }

    // Preserve support for both the current structured response and a plain string.
    if (typeof insight === "string") {
        insight = { meaning: insight };
    }

    const meaning = typeof insight.meaning === "string" ? insight.meaning.trim() : "";
    const whyItMatters = typeof insight.why_it_matters === "string"
        ? insight.why_it_matters.trim()
        : "";
    const whatToReview = Array.isArray(insight.what_to_review)
        ? insight.what_to_review.filter(item => typeof item === "string" && item.trim())
        : [];
    const negotiationSuggestion = Array.isArray(insight.negotiation_suggestion)
        ? insight.negotiation_suggestion.filter(item => typeof item === "string" && item.trim())
        : [];
    const suggestedRewrite = typeof insight.suggested_rewrite === "string"
        ? insight.suggested_rewrite.trim()
        : "";

    const countLabel = (count, singular, plural = `${singular}s`) =>
        `${count} ${count === 1 ? singular : plural}`;

    const reviewList = whatToReview.length
        ? `
            <section class="ai-result-next-steps" aria-labelledby="aiReviewHeading">
                <div class="ai-result-subheading">
                    <div>
                        <span class="ai-result-eyebrow">YOUR REVIEW NOTES</span>
                        <h4 id="aiReviewHeading">Before you sign</h4>
                    </div>
                    <span class="ai-result-count">${escapeHtml(countLabel(whatToReview.length, "point"))}</span>
                </div>
                <ol class="ai-review-list">
                    ${whatToReview.map((item, index) => `
                        <li>
                            <span class="ai-review-index" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
                            <span>${escapeHtml(item)}</span>
                        </li>
                    `).join("")}
                </ol>
            </section>
        `
        : "";

    const negotiationDisclosure = negotiationSuggestion.length
        ? `
            <details class="ai-result-disclosure">
                <summary>
                    <span class="ai-disclosure-symbol" aria-hidden="true">↗</span>
                    <span class="ai-disclosure-copy">
                        <strong>Negotiation direction</strong>
                        <small>Possible changes to discuss with the other party</small>
                    </span>
                    <span class="ai-disclosure-count">${escapeHtml(String(negotiationSuggestion.length))}</span>
                    <span class="ai-disclosure-toggle" aria-hidden="true">＋</span>
                </summary>
                <div class="ai-disclosure-content">
                    <ul class="ai-suggestion-list">
                        ${negotiationSuggestion.map(item => `<li>${escapeHtml(item)}</li>`).join("")}
                    </ul>
                </div>
            </details>
        `
        : "";

    const rewriteDisclosure = suggestedRewrite
        ? `
            <details class="ai-result-disclosure ai-rewrite-disclosure">
                <summary>
                    <span class="ai-disclosure-symbol" aria-hidden="true">§</span>
                    <span class="ai-disclosure-copy">
                        <strong>Suggested rewrite</strong>
                        <small>Open to read alternative wording</small>
                    </span>
                    <span class="ai-disclosure-toggle" aria-hidden="true">＋</span>
                </summary>
                <div class="ai-disclosure-content">
                    <div class="ai-rewrite-box">${escapeHtml(suggestedRewrite)}</div>
                    <p class="ai-rewrite-note">Draft wording for review. Check that any revision reflects the parties’ intent and the rest of the agreement.</p>
                </div>
            </details>
        `
        : "";

    const primaryMeaning = meaning || "The AI did not return a plain-language explanation for this clause.";

    container.innerHTML = `
        <div class="ai-result-header">
            <div class="ai-result-header-main">
                <span class="ai-mark" aria-hidden="true">✦</span>
                <div class="ai-result-heading-copy">
                    <div class="ai-label">AI-ASSISTED EXPLANATION</div>
                    <h3 class="ai-result-title">AI clause brief</h3>
                </div>
            </div>
            <span class="ai-result-complete"><i aria-hidden="true"></i> Ready</span>
        </div>

        <div class="ai-result-content">
            <section class="ai-result-takeaway" aria-labelledby="aiTakeawayHeading">
                <span class="ai-result-eyebrow">THE TAKEAWAY</span>
                <h4 id="aiTakeawayHeading">In plain English</h4>
                <p class="ai-result-lead">${escapeHtml(primaryMeaning)}</p>
                ${whyItMatters ? `
                    <div class="ai-result-why">
                        <span class="ai-result-why-label">WHY IT MATTERS</span>
                        <p>${escapeHtml(whyItMatters)}</p>
                    </div>
                ` : ""}
            </section>

            ${reviewList}

            ${negotiationDisclosure || rewriteDisclosure ? `
                <section class="ai-result-more" aria-label="Additional AI guidance">
                    <div class="ai-result-more-heading">
                        <span class="ai-result-eyebrow">GO DEEPER</span>
                        <span>Optional detail</span>
                    </div>
                    ${negotiationDisclosure}
                    ${rewriteDisclosure}
                </section>
            ` : ""}

            <p class="ai-result-caveat">AI-generated guidance, not legal advice. Verify each point against the original contract and your circumstances.</p>
        </div>
    `;
}
/* ============================================================
   AI ERROR
============================================================ */

function renderAIError(
    message,
    container
) {
    if (!container) {
        console.error("AI: renderAIError called with null container");
        container = document.querySelector(".ai-placeholder");
        if (!container) return;
    }

    container.classList.remove("is-loading");
    container.setAttribute("aria-busy", "false");
    container.innerHTML = `
        <div class="ai-error-state">
            <span class="ai-error-mark" aria-hidden="true">!</span>
            <div class="ai-label">AI INSIGHT</div>
            <h3>Unable to generate an insight</h3>
            <p>${escapeHtml(message || "Unable to generate AI insight.")}</p>
            <div class="ai-error-footnote">Your contract review is still available. You can continue using the rule-based findings above.</div>
        </div>
    `;
}

/* ============================================================
   CURRENT SELECTED CLAUSE
============================================================ */

function clauseFromCurrentSelection() {

    return currentClauses.find(
        (
            clause
        ) =>
            String(
                clause.clause_id
            ) ===
            String(
                activeClauseId
            )
    ) || {

        clause_id:
            activeClauseId,

        clause_type:
            "Other",

        risk_level:
            "LOW",

        risk_score:
            0,

        risk_flags:
            [],

        risk_reasons:
            [],

        text:
            ""

    };

}


/* ============================================================
   FILE ANALYSIS
============================================================ */

async function analyzeFile() {

    clearError();


    if (
        !els.fileInput
    ) {

        return;

    }


    const file =
        els.fileInput.files[0];


    if (!file) {

        showError(
            "Choose a PDF or DOCX file first."
        );


        return;

    }


    runProcessingAnimation(
        file.name
    );


    const formData =
        new FormData();


    formData.append(
        "file",
        file
    );


    try {

        const response =
            await fetch(
                "/analyze-file",
                {

                    method:
                        "POST",

                    body:
                        formData

                }
            );


        if (
            response.status === 401 ||
            response.status === 403
        ) {

            window.location.href =
                "/login";


            return;

        }


        if (
            !response.ok
        ) {

            let message =
                `Server error (${response.status}).`;


            try {

                const errorData =
                    await response.json();


                if (
                    errorData.detail
                ) {

                    message =
                        errorData.detail;

                }

            } catch (
                parseError
            ) {

                console.error(
                    parseError
                );

            }


            throw new Error(
                message
            );

        }


        const data =
            await response.json();


        if (
            els.progressBar
        ) {

            els.progressBar.style.width =
                "100%";

        }


        await new Promise(
            (
                resolve
            ) =>
                setTimeout(
                    resolve,
                    260
                )
        );


        renderOverview(
            data
        );


    } catch (error) {

        console.error(
            "ANALYSIS ERROR:",
            error
        );


        showView(
            els.uploadView
        );


        setBreadcrumb(
            "Contract review"
        );


        showError(
            error.message ||
            "Analysis failed."
        );

    }

}


/* ============================================================
   ANALYSIS HISTORY + SAVED PDF REPORTS
============================================================ */

function formatHistoryDate(value) {
    if (!value) return "Date not recorded";
    const normalized = String(value).includes("T")
        ? String(value)
        : String(value).replace(" ", "T") + "Z";
    const date = new Date(normalized);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString(undefined, {
        year: "numeric", month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit"
    });
}

function historyRiskLabel(contract) {
    if (Number(contract.high_risk_count || 0) > 0) return "High-risk clauses";
    if (Number(contract.medium_risk_count || 0) > 0) return "Review recommended";
    return "Lower risk signals";
}

function renderAnalysisHistory(contracts) {
    const list = document.getElementById("analysisHistoryList");
    const countLine = document.getElementById("historyCountLine");
    if (!list) return;

    const records = Array.isArray(contracts) ? contracts : [];
    if (countLine) {
        countLine.textContent = `${records.length} saved ${records.length === 1 ? "analysis" : "analyses"}`;
    }

    if (!records.length) {
        list.innerHTML = `
            <div class="history-empty-state">
                <div class="history-empty-mark" aria-hidden="true">↶</div>
                <h2>No saved analyses yet</h2>
                <p>When you analyze a PDF or DOCX, ClauseGuard saves the clause-level results here for this account.</p>
                <button class="primary-btn" id="historyStartAnalysisBtn" type="button">Analyze a contract <span aria-hidden="true">→</span></button>
            </div>
        `;
        const startBtn = document.getElementById("historyStartAnalysisBtn");
        if (startBtn) startBtn.addEventListener("click", () => {
            openUploadView();
            setNavActive("newAnalysisNav");
            setBreadcrumb("New analysis");
        });
        return;
    }

    list.innerHTML = records.map((contract) => {
        const id = Number(contract.id);
        const name = escapeHtml(contract.filename || `Untitled contract ${id}`);
        const high = Number(contract.high_risk_count || 0);
        const medium = Number(contract.medium_risk_count || 0);
        const low = Number(contract.low_risk_count || 0);
        const total = Number(contract.total_clauses || 0);
        const overall = contract.overall_score === null || contract.overall_score === undefined
            ? "—" : escapeHtml(contract.overall_score);
        const topRisk = String(contract.highest_risk || "LOW").toLowerCase();
        return `
            <article class="history-card" data-contract-id="${id}">
                <div class="history-card-main">
                    <div class="history-file-mark" aria-hidden="true">§</div>
                    <div class="history-file-copy">
                        <h2>${name}</h2>
                        <p class="history-meta">Analyzed ${escapeHtml(formatHistoryDate(contract.created_at))} <span aria-hidden="true">·</span> ${total} clause${total === 1 ? "" : "s"}</p>
                    </div>
                    <span class="history-risk-pill risk-${escapeHtml(topRisk)}">${escapeHtml(historyRiskLabel(contract))}</span>
                </div>
                <div class="history-card-stats">
                    <div><strong>${overall}</strong><span>Mean risk score</span></div>
                    <div><strong>${high}</strong><span>High</span></div>
                    <div><strong>${medium}</strong><span>Medium</span></div>
                    <div><strong>${low}</strong><span>Low</span></div>
                </div>
                <div class="history-card-actions">
                    <button class="secondary-btn" type="button" data-history-open="${id}">Open analysis <span aria-hidden="true">→</span></button>
                    <a class="history-download-btn" href="/api/contracts/${id}/report.pdf" download>Download PDF <span aria-hidden="true">↓</span></a>
                </div>
            </article>
        `;
    }).join("");
}

async function openAnalysisHistoryView() {
    clearError();
    showView("analysisHistoryView");
    setNavActive("analysisHistoryNav");
    setBreadcrumb("Analysis history");

    const list = document.getElementById("analysisHistoryList");
    const countLine = document.getElementById("historyCountLine");
    if (list) list.innerHTML = '<div class="history-loading"><span class="history-loading-dot"></span>Loading saved analyses…</div>';
    if (countLine) countLine.textContent = "Loading your saved analyses…";

    try {
        const response = await fetch("/api/contracts?limit=100", { headers: { "Accept": "application/json" } });
        if (response.status === 401 || response.status === 403) {
            window.location.href = "/login";
            return;
        }
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Could not load analysis history (${response.status}).`);
        }
        const data = await response.json();
        renderAnalysisHistory(data.contracts || []);
    } catch (error) {
        console.error("ANALYSIS HISTORY LOAD ERROR:", error);
        if (countLine) countLine.textContent = "History could not be loaded";
        if (list) list.innerHTML = `
            <div class="history-empty-state history-empty-state--error">
                <h2>Could not load saved analyses</h2>
                <p>${escapeHtml(error.message || "Check the connection and try again.")}</p>
                <button class="secondary-btn" id="historyRetryBtn" type="button">Try again</button>
            </div>`;
        const retry = document.getElementById("historyRetryBtn");
        if (retry) retry.addEventListener("click", openAnalysisHistoryView);
    }
}

async function openSavedAnalysis(contractId) {
    clearError();
    try {
        const response = await fetch(`/api/contracts/${encodeURIComponent(contractId)}`, {
            headers: { "Accept": "application/json" }
        });
        if (response.status === 401 || response.status === 403) {
            window.location.href = "/login";
            return;
        }
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || "Could not open this saved analysis.");
        }
        const data = await response.json();
        const saved = { ...data, contract_id: data.contract_id ?? data.id };
        currentContractId = saved.contract_id;
        renderOverview(saved);
        setNavActive("overviewNav");
        setBreadcrumb("Contract review");
    } catch (error) {
        console.error("OPEN SAVED ANALYSIS ERROR:", error);
        showError(error.message || "Could not open this saved analysis.");
    }
}

/* ============================================================
   EVENT BINDINGS
============================================================ */

function bindEvents() {


    /* --------------------------------------------------------
       DROPZONE
    --------------------------------------------------------- */

    if (
        els.dropzone
    ) {

        els.dropzone.addEventListener(
            "click",
            () => {

                els.fileInput.click();

            }
        );


        els.dropzone.addEventListener(
            "keydown",
            (
                event
            ) => {

                if (
                    event.key ===
                    "Enter"
                    ||
                    event.key ===
                    " "
                ) {

                    event.preventDefault();

                    els.fileInput.click();

                }

            }
        );


        [
            "dragenter",
            "dragover"

        ].forEach(
            (
                eventName
            ) => {

                els.dropzone.addEventListener(
                    eventName,
                    (
                        event
                    ) => {

                        event.preventDefault();

                        els.dropzone.classList.add(
                            "dragover"
                        );

                    }
                );

            }
        );


        [
            "dragleave",
            "drop"

        ].forEach(
            (
                eventName
            ) => {

                els.dropzone.addEventListener(
                    eventName,
                    (
                        event
                    ) => {

                        event.preventDefault();

                        els.dropzone.classList.remove(
                            "dragover"
                        );

                    }
                );

            }
        );


        els.dropzone.addEventListener(
            "drop",
            (
                event
            ) => {

                const file =
                    event.dataTransfer
                        .files[0];


                if (!file) {

                    return;

                }


                const valid =
                    /\.(pdf|docx)$/i.test(
                        file.name
                    );


                if (!valid) {

                    showError(
                        "Please choose a PDF or DOCX file."
                    );

                    return;

                }


                const transfer =
                    new DataTransfer();


                transfer.items.add(
                    file
                );


                els.fileInput.files =
                    transfer.files;


                updateSelectedFile(
                    file
                );

            }
        );

    }


    /* --------------------------------------------------------
       FILE INPUT
    --------------------------------------------------------- */

    if (
        els.fileInput
    ) {

        els.fileInput.addEventListener(
            "change",
            () => {

                updateSelectedFile(
                    els.fileInput.files[0]
                );

            }
        );

    }


    /* --------------------------------------------------------
       ANALYZE CONTRACT
    --------------------------------------------------------- */

    if (
        els.analyzeFileBtn
    ) {

        els.analyzeFileBtn.addEventListener(
            "click",
            analyzeFile
        );

    }


    /* --------------------------------------------------------
       NEW ANALYSIS
    --------------------------------------------------------- */

    const newAnalysisNav =
        document.getElementById(
            "newAnalysisNav"
        );


    if (
        newAnalysisNav
    ) {

        newAnalysisNav.addEventListener(
            "click",
            () => {
                openUploadView();
                setNavActive("newAnalysisNav");
                setBreadcrumb("New analysis");
            }
        );

    }


    const topNewAnalysis =
        document.getElementById(
            "topNewAnalysis"
        );


    if (
        topNewAnalysis
    ) {

        topNewAnalysis.addEventListener(
            "click",
            () => {
                openUploadView();
                setNavActive("newAnalysisNav");
                setBreadcrumb("New analysis");
            }
        );

    }


    /* --------------------------------------------------------
       OVERVIEW
    --------------------------------------------------------- */

    const overviewNav =
        document.getElementById(
            "overviewNav"
        );


    if (
        overviewNav
    ) {

        overviewNav.addEventListener(
            "click",
            () => {
                setNavActive("overviewNav");

                if (
                    currentData
                ) {

                    renderOverview(
                        currentData
                    );

                } else {

                    openUploadView();

                }

            }
        );

    }


    /* --------------------------------------------------------
       RISK CARDS
    --------------------------------------------------------- */

    document
        .querySelectorAll(
            ".risk-card"
        )
        .forEach(
            (
                card
            ) => {

                card.addEventListener(
                    "click",
                    () => {

                        openRiskGroup(
                            card.dataset.risk
                        );

                    }
                );

            }
        );


    /* --------------------------------------------------------
       REVIEW FINDINGS
    --------------------------------------------------------- */

    const reviewAllBtn =
        document.getElementById(
            "reviewAllBtn"
        );


    if (
        reviewAllBtn
    ) {

        reviewAllBtn.addEventListener(
            "click",
            () => {

                openRiskGroup(
                    "HIGH"
                );

            }
        );

    }


    /* --------------------------------------------------------
       BACK TO OVERVIEW
    --------------------------------------------------------- */

    const backButton =
        document.getElementById(
            "backToOverview"
        );


    if (
        backButton
    ) {

        backButton.addEventListener(
            "click",
            () => {

                if (
                    currentData
                ) {

                    renderOverview(
                        currentData
                    );

                } else {

                    openUploadView();

                }

            }
        );

    }


/* --------------------------------------------------------
       LOGOUT
   --------------------------------------------------------- */

    if (
        els.logoutButton
    ) {

        els.logoutButton.addEventListener(
            "click",
            logoutUser
        );

    }

    /* --------------------------------------------------------
       ASK YOUR CONTRACT NAV
   --------------------------------------------------------- */

    const askContractNav =
        document.getElementById(
            "askContractNav"
        );

    if (
        askContractNav
    ) {

        askContractNav.addEventListener(
            "click",
            openAskContractView
        );

    }


    /* --------------------------------------------------------
       ANALYSIS HISTORY NAV
    --------------------------------------------------------- */
    const analysisHistoryNav = document.getElementById("analysisHistoryNav");
    if (analysisHistoryNav) {
        analysisHistoryNav.addEventListener("click", openAnalysisHistoryView);
    }

    const refreshHistoryBtn = document.getElementById("refreshHistoryBtn");
    if (refreshHistoryBtn) {
        refreshHistoryBtn.addEventListener("click", openAnalysisHistoryView);
    }

    const analysisHistoryList = document.getElementById("analysisHistoryList");
    if (analysisHistoryList) {
        analysisHistoryList.addEventListener("click", (event) => {
            const openButton = event.target.closest("[data-history-open]");
            if (openButton) {
                openSavedAnalysis(openButton.dataset.historyOpen);
            }
        });
    }


    /* --------------------------------------------------------
       WATCHTOWER NAV
    --------------------------------------------------------- */

    const watchtowerNav = document.getElementById("watchtowerNav");

    if (watchtowerNav) {
        watchtowerNav.addEventListener(
            "click",
            openWatchtowerView
        );
    }


    /* --------------------------------------------------------
       CHAT SEND
   --------------------------------------------------------- */

    if (
        els.chatSendBtn
    ) {

        els.chatSendBtn.addEventListener(
            "click",
            sendChatMessage
        );

    }

    if (
        els.chatInput
    ) {

        els.chatInput.addEventListener(
            "keydown",
            (event) => {
                if (
                    event.key === "Enter" &&
                    !event.shiftKey
                ) {
                    event.preventDefault();
                    sendChatMessage();
                }

                // Auto-resize textarea
                autoResizeTextarea(event.target);
            }
        );

    }


    /* --------------------------------------------------------
       CHAT CLEAR
   --------------------------------------------------------- */

    if (
        els.clearChatBtn
    ) {

        els.clearChatBtn.addEventListener(
            "click",
            clearChatHistory
        );

    }


    /* --------------------------------------------------------
       STARTER QUESTIONS
   --------------------------------------------------------- */

    document.querySelectorAll(
        ".starter-btn"
    ).forEach(
        (btn) => {
            btn.addEventListener(
                "click",
                () => {
                    const question = btn.dataset.question;
                    if (question) {
                        handleStarterQuestion(question);
                    }
                }
            );
        }
    );


    /* --------------------------------------------------------
       FOLLOW-UP QUESTIONS (delegated)
   --------------------------------------------------------- */

    // Use event delegation for dynamically rendered follow-up buttons
    if (els.chatMessages) {
        els.chatMessages.addEventListener(
            "click",
            (event) => {
                const btn = event.target.closest(".follow-up-btn");
                if (btn && btn.dataset.question) {
                    handleFollowUpQuestion(btn.dataset.question);
                }
            }
        );
    }

}


/* ============================================================
   WATCHTOWER NAVIGATION
============================================================ */
async function openWatchtowerView() {
    const button = document.getElementById("watchtowerNav");

    clearError();

    if (button) {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
    }

    try {
        // Load the contracts available to the authenticated user.
        const response = await fetch("/api/contracts", {
            headers: {
                Accept: "application/json"
            }
        });

        if (response.status === 401 || response.status === 403) {
            window.location.href = "/login";
            return;
        }

        if (!response.ok) {
            throw new Error(
                `Unable to load saved contracts (${response.status}).`
            );
        }

        const data = await response.json();
        const contracts = Array.isArray(data.contracts)
            ? data.contracts
            : [];

        if (contracts.length === 0) {
            openUploadView();
            showError(
                "No saved contracts found. Upload and analyze a contract before opening Watchtower."
            );
            return;
        }

        // Prefer the contract currently being reviewed.
        let preferredId = currentData?.contract_id ?? null;

        // If the dashboard has been refreshed, use the last saved selection.
        if (preferredId === null) {
            try {
                preferredId = localStorage.getItem(
                    "clauseguard.activeContractId"
                );
            } catch (error) {
                console.warn("Could not read the saved contract ID:", error);
            }
        }

        // Only use a selected ID present in the authenticated user's list.
        const selectedContract = contracts.find(
            contract => String(contract.id) === String(preferredId)
        ) || contracts[0];

        if (
            selectedContract?.id === null ||
            selectedContract?.id === undefined
        ) {
            throw new Error(
                "No valid contract ID is available for Watchtower."
            );
        }

        const contractId = String(selectedContract.id);

        try {
            localStorage.setItem(
                "clauseguard.activeContractId",
                contractId
            );
        } catch (error) {
            console.warn("Could not save the active contract ID:", error);
        }

        // Keep the main application URL and shell in place. Watchtower is
        // loaded inside its dedicated view and shares the existing session.
        const frame = document.getElementById("watchtowerFrame");
        const watchtowerView = document.getElementById("watchtowerView");
        if (!frame || !watchtowerView) {
            throw new Error(
                "Watchtower workspace is missing. Please update the application template."
            );
        }

        // Set dimensions at runtime too: the frame must never fall back to
        // the browser default 300x150 size if a stylesheet is cached/stale.
        watchtowerView.style.display = "block";
        watchtowerView.style.width = "100%";
        watchtowerView.style.height = "calc(100dvh - 84px)";
        watchtowerView.style.minHeight = "540px";
        watchtowerView.style.overflow = "hidden";
        watchtowerView.style.background = "var(--cg-ink)";

        frame.style.display = "block";
        frame.style.width = "100%";
        frame.style.height = "100%";
        frame.style.minHeight = "540px";
        frame.style.border = "0";
        frame.style.background = "var(--cg-ink)";

        if (frame.dataset.watchtowerLoadListener !== "bound") {
            frame.addEventListener("load", () => {
                frame.dataset.loaded = "true";
            });
            frame.dataset.watchtowerLoadListener = "bound";
        }

        const watchtowerUrl =
            `/static/watchtower/index.html?contract_id=${encodeURIComponent(contractId)}&embedded=1`;
        const needsNewDocument =
            frame.dataset.contractId !== contractId ||
            !frame.getAttribute("src") ||
            frame.getAttribute("src") === "about:blank";

        if (needsNewDocument) {
            frame.dataset.contractId = contractId;
            frame.dataset.loaded = "false";
            frame.src = watchtowerUrl;
        } else if (frame.dataset.loaded === "true" && frame.contentWindow) {
            // Refresh live Watchtower data without navigating or reloading /app.
            frame.contentWindow.postMessage(
                { type: "clauseguard:watchtower-refresh" },
                window.location.origin
            );
        }

        showView("watchtowerView");
        setNavActive("watchtowerNav");
        setBreadcrumb("Watchtower");

    } catch (error) {
        console.error("WATCHTOWER NAVIGATION ERROR:", error);
        showError(`Could not open Watchtower: ${error.message}`);

    } finally {
        if (button) {
            button.disabled = false;
            button.removeAttribute("aria-busy");
        }
    }
}


/* ============================================================
   CHAT — ASK YOUR CONTRACT
========================================================== */
async function restoreActiveContractForChat() {
    // Reuse the contract already analyzed in this browser session.
    if (currentData?.contract_id !== null && currentData?.contract_id !== undefined) {
        currentContractId = currentData.contract_id;
        return currentData;
    }

    let preferredId = null;

    try {
        preferredId = localStorage.getItem("clauseguard.activeContractId");
    } catch (error) {
        console.warn("Could not read active contract ID:", error);
    }

    const listResponse = await fetch("/api/contracts", {
        credentials: "include",
        headers: { Accept: "application/json" }
    });

    if (listResponse.status === 401 || listResponse.status === 403) {
        window.location.href = "/login";
        return null;
    }

    if (!listResponse.ok) {
        throw new Error("Could not load your saved contracts.");
    }

    const payload = await listResponse.json();
    const contracts = Array.isArray(payload.contracts) ? payload.contracts : [];

    if (contracts.length === 0) {
        currentData = null;
        currentClauses = [];
        currentContractId = null;
        return null;
    }

    // Prefer the last selected contract, otherwise use the most recently listed one.
    const selected = contracts.find(
        item => String(item.id) === String(preferredId)
    ) || contracts[0];

    const detailResponse = await fetch(
        `/api/contracts/${encodeURIComponent(selected.id)}`,
        {
            credentials: "include",
            headers: { Accept: "application/json" }
        }
    );

    if (detailResponse.status === 401 || detailResponse.status === 403) {
        window.location.href = "/login";
        return null;
    }

    if (!detailResponse.ok) {
        throw new Error("Could not restore the selected contract.");
    }

    const detail = await detailResponse.json();

    currentData = {
        ...detail,
        contract_id: detail.contract_id ?? detail.id
    };

    currentClauses = normalizeClauses(currentData);
    currentContractId = currentData.contract_id;

    try {
        localStorage.setItem(
            "clauseguard.activeContractId",
            String(currentContractId)
        );
    } catch (error) {
        console.warn("Could not save active contract ID:", error);
    }

    return currentData;
}


async function openAskContractView() {
    clearError();

    chatMessages = [];
    isChatLoading = false;
    currentContractId = currentData?.contract_id ?? null;
    syncChatViewState();

    showView("askContractView");
    setNavActive("askContractNav");
    setBreadcrumb("Ask Your Contract");

    // Show a real loading state while restoring saved contract context.
    if (els.chatMessages) {
        els.chatMessages.innerHTML = `
            <div class="chat-empty-state">
                <div class="chat-empty-icon">§</div>
                <h3 class="chat-empty-title">Restoring your contract</h3>
                <p class="chat-empty-text">
                    Loading your saved agreement and conversation.
                </p>
            </div>
        `;
    }

    hideStarterQuestions();

    try {
        const contract = await restoreActiveContractForChat();

        if (!contract || currentContractId == null) {
            renderChatMessages();
            return;
        }

        await loadChatHistory(currentContractId);

    } catch (error) {
        console.error("ASK YOUR CONTRACT ERROR:", error);
        renderChatMessages();
        showError(error.message || "Could not restore your saved contract.");

    } finally {
        window.scrollTo({ top: 0, behavior: "smooth" });
    }
}


async function loadChatHistory(contractId) {
    try {
        const response = await fetch(`/api/contracts/${contractId}/chat`);

        if (response.status === 401 || response.status === 403) {
            window.location.href = "/login";
            return;
        }

        if (!response.ok) {
            throw new Error("Failed to load chat history");
        }

        const data = await response.json();
        chatMessages = data.messages || [];

        renderChatMessages();

    } catch (error) {
        console.error("CHAT HISTORY LOAD ERROR:", error);
        // Not critical - start with empty chat
        renderChatMessages();
    }
}


function renderChatMessages() {
    if (!els.chatMessages) return;

    syncChatViewState();

    // Keep the no-contract path explicit and actionable.
    if (currentContractId === null || currentContractId === undefined) {
        els.chatMessages.innerHTML = `
            <div class="chat-empty-state chat-empty-state--no-contract">
                <div class="chat-empty-icon" aria-hidden="true">§</div>
                <span class="chat-empty-overline">START WITH AN AGREEMENT</span>
                <h3 class="chat-empty-title">Choose a contract to begin</h3>
                <p class="chat-empty-text">
                    Analyze an agreement first. Ask Your Contract will use the selected contract as context for your questions.
                </p>
                <button type="button" class="primary-btn" id="chatStartAnalysisBtn">
                    Start a new analysis <span aria-hidden="true">↗</span>
                </button>
            </div>
        `;
        hideStarterQuestions();

        document.getElementById("chatStartAnalysisBtn")?.addEventListener(
            "click",
            openUploadView
        );
        return;
    }

    const conversationMessages = chatMessages.filter(message => !message._loading);

    if (conversationMessages.length === 0) {
        els.chatMessages.innerHTML = `
            <div class="chat-empty-state chat-empty-state--ready">
                <div class="chat-empty-icon" aria-hidden="true">✳</div>
                <span class="chat-empty-overline">YOUR CONTRACT, CLARIFIED</span>
                <h3 class="chat-empty-title">What would you like to understand?</h3>
                <p class="chat-empty-text">
                    Ask about a clause, a potential risk, an obligation, or something you want clarified before signing.
                </p>
            </div>
        `;
        showStarterQuestions();
        syncChatViewState();
        return;
    }

    // Loading rows carry pre-built, trusted application markup; all other
    // messages continue through the escaping renderer below.
    els.chatMessages.innerHTML = chatMessages.map(message =>
        message._loading ? message.html : renderChatMessage(message)
    ).join("");

    // The message area is an actual scroll region in the redesigned layout.
    els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
    hideStarterQuestions();
    syncChatViewState();
}


function syncChatViewState() {
    const view = els.askContractView || document.getElementById("askContractView");
    if (!view) return;

    const hasContract = currentContractId !== null && currentContractId !== undefined;
    const hasConversation = chatMessages.some(message => !message._loading);
    const contractName =
        currentData?.filename ||
        currentData?.document_name ||
        currentData?.original_filename ||
        currentData?.contract_name ||
        currentData?.title ||
        "Selected agreement";

    view.classList.toggle("chat-no-contract", !hasContract);
    view.classList.toggle("chat-ready-empty", hasContract && !hasConversation);
    view.classList.toggle("chat-has-conversation", hasContract && hasConversation);

    if (els.chatContextLabel) {
        els.chatContextLabel.textContent = hasContract ? "ACTIVE CONTRACT" : "CONTRACT CONTEXT";
    }
    if (els.chatContractName) {
        els.chatContractName.textContent = hasContract ? contractName : "No contract selected";
        els.chatContractName.title = hasContract ? contractName : "No contract selected";
    }
    if (els.chatContextStatus) {
        els.chatContextStatus.textContent = hasContract
            ? "Answers use this agreement as context"
            : "Analyze an agreement to start asking questions";
    }
    if (els.clearChatBtn) {
        els.clearChatBtn.classList.toggle("hidden", !hasContract || !hasConversation);
        els.clearChatBtn.disabled = isChatLoading;
    }
    if (els.chatInput) {
        els.chatInput.disabled = !hasContract || isChatLoading;
    }
    if (els.chatSendBtn) {
        els.chatSendBtn.disabled = !hasContract || isChatLoading;
    }
}


function renderChatMessage(msg) {
    const isUser = msg.role === "user";
    const avatar = isUser ? "U" : "C";
    const time = formatTimestamp(msg.created_at);
    
    // Sanitize clause_id for display: extract numeric ID or use clause_type as fallback
    function sanitizeClauseId(clauseId, clauseType) {
        if (!clauseId) return clauseType || "Unknown";
        const str = String(clauseId);
        // Extract numeric ID from path-like strings (e.g., "../../../8" -> "8")
        const match = str.match(/(\d+)(?!\d)/);
        if (match) return `Clause ${match[1]}`;
        // If no numeric ID found, use clause type
        return clauseType ? `${clauseType}` : `Clause ${str}`;
    }
    
    let sourcesHtml = "";
    if (msg.grounded && msg.sources && msg.sources.length > 0) {
        sourcesHtml = `
            <div class="chat-message-sources">
                <div class="sources-label">
                    SOURCE
                    ${msg.sources.length > 1 ? `(${msg.sources.length} clauses)` : ""}
                </div>
                ${msg.sources.map(src => `
                    <div class="source-item">
                        <div class="source-header">
                            <span class="source-clause-id">${escapeHtml(sanitizeClauseId(src.clause_id, src.clause_type))}</span>
                            <span class="source-type">${escapeHtml(src.clause_type)}</span>
                            ${src.page_number ? `<span class="source-page">Page ${escapeHtml(src.page_number)}</span>` : ""}
                        </div>
                        <div class="source-evidence">${escapeHtml(src.evidence)}</div>
                    </div>
                `).join("")}
            </div>
        `;
    }

    let followUpsHtml = "";
    if (msg.follow_up_suggestions && msg.follow_up_suggestions.length > 0) {
        followUpsHtml = `
            <div class="chat-follow-ups">
                ${msg.follow_up_suggestions.map(s => `
                    <button class="follow-up-btn" data-question="${escapeHtml(s)}">${escapeHtml(s)}</button>
                `).join("")}
            </div>
        `;
    }

    return `
        <div class="chat-message ${isUser ? "user" : "assistant"}">
            <div class="chat-message-avatar">${avatar}</div>
            <div class="chat-message-content">
                <div class="chat-message-text">${escapeHtml(msg.content).replace(/\r?\n/g, "<br>")}</div>
                ${sourcesHtml}
                ${followUpsHtml}
            </div>
        </div>
    `;
}


function formatTimestamp(timestamp) {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}


function showStarterQuestions() {
    if (els.chatStarter) {
        els.chatStarter.classList.remove("hidden");
    }
}


function hideStarterQuestions() {
    if (els.chatStarter) {
        els.chatStarter.classList.add("hidden");
    }
}


function setNavActive(navId) {
    // Remove active from all nav items
    document.querySelectorAll(".nav-item").forEach(btn => {
        btn.classList.remove("active");
    });
    
    // Add active to selected
    const activeBtn = document.getElementById(navId);
    if (activeBtn) {
        activeBtn.classList.add("active");
    }
}


async function sendChatMessage() {
    const input = els.chatInput;
    if (!input) return;

    const question = input.value.trim();
    if (!question || isChatLoading) return;

    if (!currentContractId) {
        showError("No contract selected.");
        return;
    }

    // Disable input
    isChatLoading = true;
    input.disabled = true;
    if (els.chatSendBtn) els.chatSendBtn.disabled = true;

    // Hide starter questions
    hideStarterQuestions();

    // Add user message immediately (optimistic)
    const userMsg = {
        role: "user",
        content: question,
        created_at: new Date().toISOString()
    };
    chatMessages.push(userMsg);
    renderChatMessages();

    // Clear input
    input.value = "";
    input.style.height = "auto";

    // Show loading indicator
    showChatLoading();

    try {
        const response = await fetch("/api/ai/contract-chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                contract_id: currentContractId,
                question: question
            })
        });

        if (response.status === 401 || response.status === 403) {
            window.location.href = "/login";
            return;
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Chat failed");
        }

        // Remove loading indicator
        hideChatLoading();

        // Add assistant message
        const assistantMsg = {
            role: "assistant",
            content: data.answer,
            answer_type: data.answer_type,
            grounded: data.grounded,
            sources: data.sources || [],
            follow_up_suggestions: data.follow_up_suggestions || [],
            created_at: new Date().toISOString()
        };
        chatMessages.push(assistantMsg);
        renderChatMessages();

    } catch (error) {
        console.error("CHAT ERROR:", error);
        hideChatLoading();
        
        // Show error message
        const errorMsg = {
            role: "assistant",
            content: "Sorry, I couldn't process your question. Please try again.",
            created_at: new Date().toISOString()
        };
        chatMessages.push(errorMsg);
        renderChatMessages();
    } finally {
        isChatLoading = false;
        input.disabled = false;
        if (els.chatSendBtn) els.chatSendBtn.disabled = false;
        input.focus();
    }
}


function showChatLoading() {
    if (!els.chatMessages) return;
    
    const loadingHtml = `
        <div class="chat-message assistant">
            <div class="chat-message-avatar">C</div>
            <div class="chat-message-content">
                <div class="chat-loading">
                    <span>Qwen3 is thinking</span>
                    <div class="chat-loading-dots">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Add loading to messages array temporarily
    chatMessages.push({ _loading: true, html: loadingHtml });
    renderChatMessages();
}


function hideChatLoading() {
    // Remove loading message
    chatMessages = chatMessages.filter(msg => !msg._loading);
}


async function clearChatHistory() {
    if (!currentContractId) return;

    if (!confirm("Clear all chat history for this contract?")) return;

    try {
        const response = await fetch(`/api/contracts/${currentContractId}/chat`, {
            method: "DELETE"
        });

        if (response.status === 401 || response.status === 403) {
            window.location.href = "/login";
            return;
        }

        if (!response.ok) {
            throw new Error("Failed to clear chat");
        }

        chatMessages = [];
        renderChatMessages();

    } catch (error) {
        console.error("CLEAR CHAT ERROR:", error);
        showError("Failed to clear chat history.");
    }
}


function handleStarterQuestion(question) {
    if (els.chatInput) {
        els.chatInput.value = question;
        els.chatInput.focus();
        // Auto-send
        setTimeout(() => sendChatMessage(), 50);
    }
}


function handleFollowUpQuestion(question) {
    if (els.chatInput) {
        els.chatInput.value = question;
        els.chatInput.focus();
        setTimeout(() => sendChatMessage(), 50);
    }
}


function autoResizeTextarea(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 140) + "px";
}


/* ============================================================
   INITIALIZE
========================================================== */

async function initializeApp() {

    const authenticated =
        await loadCurrentUser();


    if (!authenticated) {

        return;

    }


    bindEvents();

}


initializeApp();