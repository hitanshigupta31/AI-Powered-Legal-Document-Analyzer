CLAUSEGUARD — ANALYSIS HISTORY + PDF SUMMARY REPORTS

WHAT THIS ADDS
- Adds an Analysis history item to the existing authenticated workspace sidebar.
- Lists the signed-in user's saved contract analyses (up to 100 newest records).
- Shows analysis date, clause count, mean risk score, and LOW/MEDIUM/HIGH counts.
- Opens a previous analysis inside the existing Contract Review view without uploading it again.
- Adds a per-contract downloadable PDF summary generated from saved clause results and risk reasons.
- Protects history and PDF downloads by checking the signed-in user's ownership of each contract.
- Does not introduce a new database table. Successful analyses are already saved in the existing contracts table.

FILES TO REPLACE
1. backend/main.py                  -> your existing backend/main.py
2. frontend/templates/index.html    -> frontend/templates/index.html
3. frontend/static/app.js           -> frontend/static/app.js
4. frontend/static/style.css        -> frontend/static/style.css

The frontend/static/watchtower folder is included as a baseline copy for completeness. This feature does not modify Watchtower's own assets. Since Watchtower is already installed in your project, you can leave that folder untouched unless you need to restore it from the current integration package.

DEPENDENCY
Add the line from requirements-additions.txt to your existing requirements.txt, or run this in the same Python environment that runs FastAPI:
    pip install "reportlab>=4.0,<5.0"

Do not replace your entire requirements.txt with requirements-additions.txt; it contains only the additional dependency.

HOW TO TEST
1. Back up the current files.
2. Install ReportLab in the Python environment used by FastAPI.
3. Replace the four files listed above.
4. Restart FastAPI and sign in.
5. Analyze a PDF/DOCX. Open Analysis history; the new analysis should appear.
6. Open analysis to restore its saved clause findings.
7. Download PDF and confirm it opens with contract metadata, risk distribution and priority findings.
8. Sign into a different test account and confirm its history does not show the first user's contracts.

PRIVACY AND SCOPE
History and report endpoints only return records belonging to the authenticated user. The PDF is generated from saved analysis results and does not rerun the AI model. It reports stored rule-based findings and their available reasons. Transient AI explanations are not included because the current backend does not persist those clause-insight responses.

VALIDATION PERFORMED
- Python AST/syntax parse: passed.
- JavaScript syntax checks: passed for app.js and Watchtower JavaScript assets.
- HTML parsing and duplicate-ID check: passed.
- CSS brace-balance check: passed.
- Actual PDF route smoke test against synthetic saved-contract data: passed.
- PDF text extraction sanity check: passed.
- Per-user isolation check: a different user receives 404 for the requested contract.
- ZIP integrity: passed.

The integration was tested against the latest available ClauseGuard backend source snapshot in this working session. If you made additional backend edits after that snapshot, compare them before replacing backend/main.py.
