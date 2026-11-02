/* ============================================================
   CLAUSEGUARD — AI INVESTIGATION MODULE
   Scroll-driven visual narrative. Extracted from prototype.
   Initializes ONLY when the investigation view is opened.
   ============================================================ */

(function() {
    "use strict";

    // Module state
    let investigationInitialized = false;
    let investigationTimeline = null;
    let investigationScrollTrigger = null;
    let prefersReducedMotion = false;

    // DOM references
    const invEls = {};

    // Mock data (from prototype)
    const SECTIONS = [
        { name: "Definitions",            lines: 6 },
        { name: "Term",                   lines: 3 },
        { name: "Services",               lines: 5 },
        { name: "Payment",                lines: 4 },
        { name: "Termination",            lines: 4, clauses: {0: "9.1", 2: "9.3"} },
        { name: "Confidentiality",        lines: 3 },
        { name: "Indemnification",        lines: 3, clauses: {1: "14.2"} },
        { name: "Limitation of Liability", lines: 2, clauses: {0: "15.1"} },
        { name: "Insurance",              lines: 2 },
        { name: "Governing Law",          lines: 1, clauses: {0: "22.1"} }
    ];

    const FINDINGS = [
        { id: "9.1",  name: "Termination for Convenience", sev: "med",  desc: "Only Bridgeforth may terminate for convenience; Solant has no matching right." },
        { id: "9.3",  name: "Auto-Renewal",                 sev: "med",  desc: "Silent 60-day renewal window with no cap on the number of renewal terms." },
        { id: "14.2", name: "Indemnification",              sev: "high", desc: "Uncapped, one-directional indemnity with no reference to the liability ceiling in §15." },
        { id: "15.1", name: "Limitation of Liability",      sev: "high", desc: "Cap excludes indemnification claims — the ceiling doesn't actually apply to §14.2." },
        { id: "22.1", name: "Governing Law & Venue",        sev: "low",  desc: "Disputes are heard in Bridgeforth's home state, an inconvenient forum for Solant." }
    ];

    const FOCUS_ID = "14.2";
    const RELATED_IDS = ["15.1", "9.1"]; // plus one synthetic node below for Insurance §16.2

    const sevColor = { high: "var(--risk-high)", med: "var(--risk-med)", low: "var(--risk-low)" };
    const sevHex   = { high: "#A63B2C", med: "#B4812B", low: "#4E6E62" };

    // ============================================================
    // INITIALIZATION
    // ============================================================

    function initInvestigationModule() {
        if (investigationInitialized) {
            return;
        }

        // Cache DOM elements
        cacheElements();

        checkReducedMotion();

        // Register GSAP ScrollTrigger
        if (typeof gsap !== "undefined" && typeof ScrollTrigger !== "undefined") {
            gsap.registerPlugin(ScrollTrigger);
        }

        buildMockData();
        setupScrollTimeline();
        setupHeroIntro();
        setupReviewInteractions();
        setupReplay();

        investigationInitialized = true;
    }

    function cacheElements() {
        // Hero
        invEls.hero = document.getElementById("invHero");
        invEls.heroDot = document.getElementById("invHeroDot");
        invEls.heroDocName = document.getElementById("invHeroDocName");
        invEls.heroParties = document.getElementById("invHeroParties");
        invEls.heroClauseCount = document.getElementById("invHeroClauseCount");

        // Stage
        invEls.stageWrap = document.getElementById("invStageWrap");
        invEls.stage = document.getElementById("invStage");
        invEls.stageSvg = document.getElementById("invStageSvg");
        invEls.progressFill = document.getElementById("invProgressFill");
        invEls.actNum = document.getElementById("invActNum");
        invEls.actName = document.getElementById("invActName");

        // SVG groups
        invEls.gContract = document.getElementById("invGContract");
        invEls.gFindings = document.getElementById("invGFindings");
        invEls.gFocus = document.getElementById("invGFocus");
        invEls.focusBox = document.getElementById("invFocusBox");
        invEls.gEvidence = document.getElementById("invGEvidence");
        invEls.evidenceConnector = document.getElementById("invEvidenceConnector");
        invEls.signalRing = document.getElementById("invSignalRing");
        invEls.gRelated = document.getElementById("invGRelated");
        invEls.gConsequence = document.getElementById("invGConsequence");

        // Captions
        invEls.cap1 = document.getElementById("invCap1");
        invEls.cap2 = document.getElementById("invCap2");
        invEls.cap3 = document.getElementById("invCap3");
        invEls.cap4 = document.getElementById("invCap4");
        invEls.cap5 = document.getElementById("invCap5");
        invEls.cap6 = document.getElementById("invCap6");
        invEls.cap7 = document.getElementById("invCap7");

        // Caption sub-elements
        invEls.findingsCaptionList = document.getElementById("invFindingsCaptionList");
        invEls.signalCaptionList = document.getElementById("invSignalCaptionList");

        // Review
        invEls.reviewList = document.getElementById("invReviewList");
        invEls.reviewCount = document.getElementById("invReviewCount");
        invEls.replayBtn = document.getElementById("invReplayBtn");

        // Store SVG namespace
        invEls.svgNS = "http://www.w3.org/2000/svg";
    }

    function checkReducedMotion() {
        prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    // ============================================================
    // LAYOUT — turn the section list into line geometry
    // ============================================================

    let lineData = [];
    let findingElements = {};

    function buildMockData() {
        // Calculate total lines for hero
        const totalLines = SECTIONS.reduce((a, s) => a + s.lines, 0);
        if (invEls.heroClauseCount) {
            invEls.heroClauseCount.textContent = totalLines;
        }

        // Build line geometry
        const PAGE = { x: 388, y: 60, w: 224, h: 580 };
        const gapBetweenSections = (PAGE.h - totalLines * 11) / (SECTIONS.length + 1);
        let y = PAGE.y + gapBetweenSections;
        let seed = 7;

        function rand() {
            seed = (seed * 9301 + 49297) % 233280;
            return seed / 233280;
        }

        SECTIONS.forEach((sec) => {
            for (let i = 0; i < sec.lines; i++) {
                const w = PAGE.w * (0.45 + rand() * 0.42);
                const clauseId = (sec.clauses && sec.clauses[i]) ? sec.clauses[i] : null;
                lineData.push({
                    section: sec.name,
                    x1: PAGE.x,
                    y1: y,
                    x2: PAGE.x + w,
                    y2: y,
                    clauseId: clauseId
                });
                y += 11;
            }
            y += gapBetweenSections;
        });

        // Draw contract frame + clause lines
        drawContractFrame();
        drawClauseLines();
        drawFindings();
        drawFindingsCaptionList();
        drawRelatedClauses();
        drawConsequenceBars();
    }

    function drawContractFrame() {
        const PAGE = { x: 388, y: 60, w: 224, h: 580 };
        const frame = document.createElementNS(invEls.svgNS, "rect");
        frame.setAttribute("class", "inv-doc-frame");
        frame.setAttribute("x", PAGE.x - 18);
        frame.setAttribute("y", PAGE.y - 18);
        frame.setAttribute("width", PAGE.w + 36);
        frame.setAttribute("height", PAGE.h + 36);
        frame.setAttribute("rx", 2);
        invEls.gContract.appendChild(frame);
    }

    function drawClauseLines() {
        lineData.forEach((l, idx) => {
            const el = document.createElementNS(invEls.svgNS, "line");
            el.setAttribute("class", "inv-clause-line");
            el.setAttribute("data-idx", idx);
            el.setAttribute("x1", l.x1);
            el.setAttribute("y1", l.y1);
            el.setAttribute("x2", l.x1); // start collapsed for draw-in
            el.setAttribute("y2", l.y1);
            invEls.gContract.appendChild(el);
            l.el = el;
        });
    }

    function findLine(clauseId) {
        for (let i = 0; i < lineData.length; i++) {
            if (lineData[i].clauseId === clauseId) return lineData[i];
        }
        return null;
    }

    function drawFindings() {
        FINDINGS.forEach((f) => {
            const line = findLine(f.id);
            if (!line) return;

            const cx = line.x2 + 14;
            const cy = line.y1;

            const ring = document.createElementNS(invEls.svgNS, "circle");
            ring.setAttribute("class", "inv-finding-ring");
            ring.setAttribute("cx", cx);
            ring.setAttribute("cy", cy);
            ring.setAttribute("r", 3);
            ring.setAttribute("style", "stroke:" + sevHex[f.sev]);

            const dot = document.createElementNS(invEls.svgNS, "circle");
            dot.setAttribute("class", "inv-finding-dot");
            dot.setAttribute("cx", cx);
            dot.setAttribute("cy", cy);
            dot.setAttribute("r", 3);
            dot.setAttribute("style", "fill:" + sevHex[f.sev]);

            invEls.gFindings.appendChild(ring);
            invEls.gFindings.appendChild(dot);

            f._dot = dot;
            f._ring = ring;
            f._pos = { x: cx, y: cy };
        });
    }

    function drawFindingsCaptionList() {
        if (!invEls.findingsCaptionList) return;

        FINDINGS.forEach((f) => {
            const row = document.createElement("div");
            row.className = "frow";
            row.innerHTML = '<span class="sev" style="background:' + sevHex[f.sev] + '"></span><span>§' + f.id + ' — ' + f.name + '</span>';
            invEls.findingsCaptionList.appendChild(row);
            f._row = row;
        });
    }

    function drawRelatedClauses() {
        const focusLine = findLine(FOCUS_ID);
        const centerPt = { x: 500, y: 350 };

        const satellites = [
            { id: "15.1", label: "§15.1 — Liability cap excludes this claim" },
            { id: "9.1",  label: "§9.1 — One-sided termination rights" },
            { id: "16.2", label: "§16.2 — Insurance floor doesn't cover the gap" }
        ];

        satellites.forEach((s, i) => {
            const angle = (-40 + i * 40) * Math.PI / 180;
            const r = 190;
            const x = centerPt.x + Math.cos(angle) * r * 1.35;
            const y = centerPt.y + Math.sin(angle) * r * 0.55 - 40;

            const arc = document.createElementNS(invEls.svgNS, "path");
            const midX = (centerPt.x + x) / 2;
            const midY = (centerPt.y + y) / 2 - 60;
            arc.setAttribute("class", "inv-related-arc");
            arc.setAttribute("d", "M" + centerPt.x + "," + centerPt.y + " Q" + midX + "," + midY + " " + x + "," + y);
            invEls.gRelated.appendChild(arc);

            const node = document.createElementNS(invEls.svgNS, "g");
            node.setAttribute("class", "inv-related-node");
            node.setAttribute("opacity", 0);

            const c = document.createElementNS(invEls.svgNS, "circle");
            c.setAttribute("cx", x);
            c.setAttribute("cy", y);
            c.setAttribute("r", 6);

            const t = document.createElementNS(invEls.svgNS, "text");
            t.setAttribute("x", x + (i === 1 ? 0 : (x > centerPt.x ? 14 : -14)));
            t.setAttribute("y", y - 14);
            t.setAttribute("text-anchor", i === 1 ? "middle" : (x > centerPt.x ? "start" : "end"));
            t.setAttribute("style", "font-family:Inter,sans-serif;font-size:11px;fill:var(--ink-soft)");
            t.textContent = s.label;

            node.appendChild(c);
            node.appendChild(t);
            invEls.gRelated.appendChild(node);

            s._node = node;
            s._arc = arc;
        });

        // Center node
        const centerNode = document.createElementNS(invEls.svgNS, "g");
        centerNode.setAttribute("class", "inv-related-node center");
        centerNode.setAttribute("opacity", 0);

        const cc = document.createElementNS(invEls.svgNS, "circle");
        cc.setAttribute("cx", centerPt.x);
        cc.setAttribute("cy", centerPt.y);
        cc.setAttribute("r", 9);

        const ct = document.createElementNS(invEls.svgNS, "text");
        ct.setAttribute("x", centerPt.x);
        ct.setAttribute("y", centerPt.y + 28);
        ct.setAttribute("text-anchor", "middle");
        ct.setAttribute("style", "font-family:Fraunces,serif;font-style:italic;font-size:13px;fill:var(--teal)");
        ct.textContent = "§14.2";

        centerNode.appendChild(cc);
        centerNode.appendChild(ct);
        invEls.gRelated.appendChild(centerNode);

        invEls.centerNode = centerNode;
        invEls.satellites = satellites;
    }

    function drawConsequenceBars() {
        const baseY = 430;
        const barH = 34;
        const x0 = 300;
        const maxW = 420;

        const bars = [
            { label: "Typical cap — comparable MSAs", w: maxW * 0.42, fill: "var(--teal-2)", y: baseY, amt: "$2.4M" },
            { label: "§14.2 — this agreement",        w: maxW,      fill: "var(--risk-high)", y: baseY + 64, amt: "Uncapped" }
        ];

        bars.forEach((b) => {
            const g = document.createElementNS(invEls.svgNS, "g");
            g.setAttribute("class", "inv-consequence-bar");

            const track = document.createElementNS(invEls.svgNS, "rect");
            track.setAttribute("x", x0);
            track.setAttribute("y", b.y);
            track.setAttribute("width", maxW);
            track.setAttribute("height", barH);
            track.setAttribute("fill", "none");
            track.setAttribute("stroke", "var(--rule)");

            const fill = document.createElementNS(invEls.svgNS, "rect");
            fill.setAttribute("x", x0);
            fill.setAttribute("y", b.y);
            fill.setAttribute("width", 0);
            fill.setAttribute("height", barH);
            fill.setAttribute("fill", b.fill);
            fill.setAttribute("class", "bar-fill");

            const label = document.createElementNS(invEls.svgNS, "text");
            label.setAttribute("x", x0);
            label.setAttribute("y", b.y - 10);
            label.setAttribute("style", "font-family:Inter,sans-serif;font-size:12px;fill:var(--ink-soft)");
            label.textContent = b.label;

            g.appendChild(track);
            g.appendChild(fill);
            g.appendChild(label);
            invEls.gConsequence.appendChild(g);

            b._fill = fill;
            b._g = g;
        });

        invEls.gConsequence._bars = bars;
        invEls.gConsequence._maxW = maxW;
    }

    // ============================================================
    // MASTER TIMELINE — scrubbed by scroll across the pinned stage
    // ============================================================

    function setupScrollTimeline() {
        if (typeof gsap === "undefined" || typeof ScrollTrigger === "undefined") {
            // Fallback: show all statically
            showAllStatic();
            return;
        }

        const acts = [
            "The contract",
            "Findings emerge",
            "Focus: §14.2",
            "Exact evidence",
            "Why it was flagged",
            "Related clauses",
            "Consequence",
            "Handoff"
        ];

        const captionMap = {
            0: invEls.cap1,
            1: invEls.cap2,
            2: invEls.cap3,
            3: invEls.cap4,
            4: invEls.cap5,
            5: invEls.cap6,
            6: invEls.cap7,
            7: null
        };

        function showCap(id, dur) {
            const el = captionMap[id];
            if (el) {
                tl.to(el, { opacity: 1, duration: dur || 1 }, "<");
            }
        }

        function hideCap(id, dur) {
            const el = captionMap[id];
            if (el) {
                tl.to(el, { opacity: 0, duration: dur || 0.6 }, "<");
            }
        }

        const tl = gsap.timeline({
            scrollTrigger: {
                trigger: "#invStageWrap",
                start: "top top",
                end: "bottom bottom",
                scrub: 0.6,
                pin: "#invStage",
                onUpdate: (self) => {
                    invEls.progressFill.style.width = (self.progress * 100).toFixed(2) + "%";
                    const idx = Math.min(7, Math.floor(self.progress * 8));
                    invEls.actNum.textContent = String(idx + 1).padStart(2, "0");
                    invEls.actName.textContent = acts[idx];
                }
            },
            defaults: { ease: "power2.inOut" }
        });

        investigationTimeline = tl;
        investigationScrollTrigger = tl.scrollTrigger;

        // viewBox proxy for the SVG "camera"
        const vb = { x: 0, y: 0, w: 1000, h: 700 };
        function applyVB() {
            invEls.stageSvg.setAttribute("viewBox", vb.x + " " + vb.y + " " + vb.w + " " + vb.h);
        }

        /* ---------- ACT 1 — whole contract draws in ---------- */
        tl.addLabel("act1", 0);
        showCap(0, 1.4);
        lineData.forEach((l, i) => {
            tl.to(l.el, { attr: { x2: l.x2 }, opacity: 0.32, duration: 0.06 }, 0.3 + i * 0.02);
        });
        tl.to({}, { duration: 2 }); // hold
        hideCap(0);

        /* ---------- ACT 2 — findings emerge ---------- */
        tl.addLabel("act2");
        showCap(1, 1);
        FINDINGS.forEach((f, i) => {
            tl.to(f._dot, { opacity: 1, duration: 0.3 }, "<+=" + (i * 0.35));
            tl.fromTo(f._ring, { attr: { r: 3 }, opacity: 0.9 }, { attr: { r: 11 }, opacity: 0, duration: 0.7 }, "<");
            tl.to(f._row, { opacity: 1, x: 0, duration: 0.4 }, "<");
        });
        tl.to({}, { duration: 1.6 });
        hideCap(1);
        tl.to(Array.from(document.querySelectorAll(".inv-clause-line")), { opacity: 0.1, duration: 0.6 }, "<");

        /* ---------- ACT 3 — focus on §14.2 ---------- */
        tl.addLabel("act3");
        tl.to(FINDINGS.map((f) => f._dot).filter((d, i) => FINDINGS[i].id !== FOCUS_ID),
            { opacity: 0.15, duration: 0.5 }, "<");

        const focusLine = findLine(FOCUS_ID);
        const focusCx = focusLine.x1 + 40;
        const focusCy = focusLine.y1;

        tl.to(vb, {
            x: focusCx - 180, y: focusCy - 130, w: 360, h: 260, duration: 2.2, onUpdate: applyVB
        }, "<");

        tl.to("#invFocusBox", {
            attr: { x: focusLine.x1 - 14, y: focusLine.y1 - 16, width: (focusLine.x2 - focusLine.x1) + 70, height: 32 },
            opacity: 1, duration: 1.4
        }, "<+=0.4");

        tl.to(FINDINGS.filter((f) => f.id === FOCUS_ID)[0]._dot, { opacity: 1, duration: 0.4 }, "<");
        showCap(2, 1);
        tl.to({}, { duration: 1.8 });
        hideCap(2);

        /* ---------- ACT 4 — exact evidence + connector ---------- */
        tl.addLabel("act4");
        const badgeX = focusLine.x2 + 90;
        const badgeY = focusLine.y1 - 10;

        tl.to(vb, { x: focusCx - 160, y: focusCy - 170, w: 320, h: 230, duration: 1.6, onUpdate: applyVB }, "<");

        tl.to("#invEvidenceConnector", {
            attr: { d: "M" + (focusLine.x1 + 30) + "," + focusLine.y1 + " L" + badgeX + "," + badgeY },
            opacity: 0.8, duration: 1.2
        }, "<+=0.3");

        tl.to("#invSignalRing", {
            attr: { cx: badgeX, cy: badgeY, r: 8 },
            opacity: 1, duration: 0.8,
            onStart: function() {
                document.getElementById("invSignalRing").style.stroke = sevHex.high;
            }
        }, "<+=0.3");

        showCap(3, 1.2);
        tl.to({}, { duration: 2.4 });
        hideCap(3);

        /* ---------- ACT 5 — signal / why ---------- */
        tl.addLabel("act5");
        tl.to(vb, { x: focusCx - 120, y: focusCy - 190, w: 260, h: 190, duration: 1.4, onUpdate: applyVB }, "<");
        showCap(4, 1);

        const whyLis = document.querySelectorAll("#invCap5 li");
        whyLis.forEach((li, i) => {
            gsap.set(li, { opacity: 0, x: 8 });
            tl.to(li, { opacity: 1, x: 0, duration: 0.5 }, "<+=" + (i === 0 ? 0.2 : 0.35));
        });

        tl.to({}, { duration: 1.8 });
        hideCap(4);
        tl.to(["#invEvidenceConnector", "#invSignalRing", "#invFocusBox"], { opacity: 0, duration: 0.6 }, "<");

        /* ---------- ACT 6 — related clauses, orbital ---------- */
        tl.addLabel("act6");
        tl.to(vb, { x: 170, y: 120, w: 660, h: 460, duration: 1.8, onUpdate: applyVB }, "<");
        showCap(5, 1);

        tl.to(invEls.centerNode, { opacity: 1, duration: 0.6 }, "<+=0.3");

        invEls.satellites.forEach((s, i) => {
            tl.fromTo(s._arc, { strokeDasharray: 220, strokeDashoffset: 220 }, { strokeDashoffset: 0, opacity: 0.55, duration: 0.9 }, "<+=" + (i * 0.35));
            tl.to(s._node, { opacity: 1, duration: 0.5 }, "<+=0.4");
        });

        tl.to({}, { duration: 1.8 });
        hideCap(5);
        tl.to([invEls.centerNode, invEls.gRelated], { opacity: 0, duration: 0.6 }, "<");

        /* ---------- ACT 7 — consequence ---------- */
        tl.addLabel("act7");
        tl.to(vb, { x: 230, y: 340, w: 560, h: 200, duration: 1.6, onUpdate: applyVB }, "<");
        showCap(6, 1);

        invEls.gConsequence._bars.forEach((b, i) => {
            tl.to(b._g, { opacity: 1, duration: 0.3 }, "<+=" + (i * 0.2));
            tl.to(b._fill, { attr: { width: b.w }, duration: 1.1 }, "<");
        });

        tl.to({}, { duration: 2 });
        hideCap(6);

        /* ---------- ACT 8 — pull back out, hand off to review ---------- */
        tl.addLabel("act8");
        tl.to(vb, { x: 0, y: 0, w: 1000, h: 700, duration: 1.6, onUpdate: applyVB }, "<");
        tl.to(["#invGConsequence", "#invGFindings", "#invGFocus", "#invGRelated"], { opacity: 0, duration: 0.8 }, "<");
        tl.to(Array.from(document.querySelectorAll(".inv-clause-line")), { opacity: 0, duration: 0.8 }, "<");
        tl.to("#invGContract .inv-doc-frame", { opacity: 0, duration: 0.8 }, "<");
        tl.to("#invStage", { opacity: 0.0, duration: 0.6 }, ">-0.2");
    }

    function showAllStatic() {
        // GSAP not available - show everything
        lineData.forEach((l) => {
            if (l.el) {
                l.el.setAttribute("x2", l.x2);
                l.el.setAttribute("opacity", "0.32");
            }
        });
        FINDINGS.forEach((f) => {
            if (f._dot) f._dot.setAttribute("opacity", "1");
            if (f._ring) f._ring.setAttribute("opacity", "0.7");
            if (f._row) f._row.style.opacity = "1";
        });
        if (invEls.focusBox) invEls.focusBox.setAttribute("opacity", "1");
        if (invEls.evidenceConnector) invEls.evidenceConnector.setAttribute("opacity", "0.8");
        if (invEls.signalRing) invEls.signalRing.setAttribute("opacity", "1");
        if (invEls.centerNode) invEls.centerNode.setAttribute("opacity", "1");
        invEls.satellites.forEach((s) => {
            if (s._node) s._node.setAttribute("opacity", "1");
            if (s._arc) s._arc.setAttribute("opacity", "0.55");
        });
        invEls.gConsequence._bars.forEach((b) => {
            if (b._g) b._g.setAttribute("opacity", "1");
            if (b._fill) b._fill.setAttribute("width", b.w);
        });
        // Show all captions
        [invEls.cap1, invEls.cap2, invEls.cap3, invEls.cap4, invEls.cap5, invEls.cap6, invEls.cap7].forEach((cap) => {
            if (cap) cap.style.opacity = "1";
        });
        // Update progress
        invEls.progressFill.style.width = "100%";
        invEls.actNum.textContent = "08";
        invEls.actName.textContent = "Handoff";
    }

    // ============================================================
    // HERO OPENING MARK: dot travels the line on load
    // ============================================================

    function setupHeroIntro() {
        if (!invEls.heroDot) return;

        gsap.fromTo(invEls.heroDot,
            { attr: { cx: 0 } },
            { attr: { cx: 560 }, duration: prefersReducedMotion ? 0.01 : 2.6, ease: "power1.inOut", delay: 0.3 }
        );
    }

    // ============================================================
    // REVIEW LIST INTERACTIONS
    // ============================================================

    function setupReviewInteractions() {
        if (!invEls.reviewList) return;

        let reviewedCount = 0;

        FINDINGS.forEach((f) => {
            const item = document.createElement("div");
            item.className = "inv-review-item";

            const sevClass = f.sev === "high" ? "inv-sev-high" : (f.sev === "med" ? "inv-sev-med" : "inv-sev-low");
            const sevLabel = f.sev === "high" ? "HIGH" : (f.sev === "med" ? "MEDIUM" : "LOW");

            item.innerHTML =
                '<div class="inv-sev-tag ' + sevClass + '">' + sevLabel + '</div>' +
                '<div><span class="inv-clause-name">' + f.name + '</span><span class="inv-clause-id">§' + f.id + '</span><p>' + f.desc + '</p></div>' +
                '<button type="button">Mark reviewed</button>';

            const btn = item.querySelector("button");
            btn.addEventListener("click", function() {
                const wasDone = btn.classList.contains("done");
                btn.classList.toggle("done");
                btn.textContent = wasDone ? "Mark reviewed" : "Reviewed";
                reviewedCount += wasDone ? -1 : 1;
                if (invEls.reviewCount) {
                    invEls.reviewCount.textContent = reviewedCount;
                }
            });

            invEls.reviewList.appendChild(item);
        });
    }

    // ============================================================
    // REPLAY
    // ============================================================

    function setupReplay() {
        if (!invEls.replayBtn) return;

        invEls.replayBtn.addEventListener("click", function() {
            window.scrollTo({ top: 0, behavior: prefersReducedMotion ? "auto" : "smooth" });
        });
    }

    // ============================================================
    // PUBLIC API
    // ============================================================

    window.ClauseGuardInvestigation = {
        init: initInvestigationModule,
        destroy: function() {
            if (investigationTimeline) {
                investigationTimeline.kill();
                investigationTimeline = null;
            }
            if (investigationScrollTrigger) {
                investigationScrollTrigger.kill();
                investigationScrollTrigger = null;
            }
            investigationInitialized = false;
        }
    };
})();