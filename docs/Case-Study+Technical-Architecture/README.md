# SupportOps AI — Case Study & Technical Architecture

Two companion documents built with plain semantic HTML and CSS (no frameworks, no JavaScript), following the same pattern used across this portfolio's projects.

## Folder contents

```
Case-Study+Technical-Architecture/
├── case-study.html                                # Business-facing narrative: problem → solution → evidence
├── case-study.md                                   # Markdown version (GitHub rendering, ATS-style text)
├── SupportOps-AI-Case-Study.pdf                     # Print-exported PDF
├── technical-architecture.html                      # Engineering-facing reference: components, data flow, gaps
├── technical-architecture.md                         # Markdown version
├── SupportOps-AI-Technical-Architecture.pdf           # Print-exported PDF
├── styles.css                                        # Shared styling (screen + print/A4 rules), both documents
├── assets/                                           # Screenshots referenced by both documents
└── README.md
```

## What each document is for

- **Case Study** — the story: the problem (safe automation of support triage), the solution (LangGraph control flow + CrewAI reasoning + a deterministic policy engine), and the evidence it works. A **Resources** section at the bottom links to the GitHub repo, README, demo video, and docs folder for anyone who wants to verify or dig deeper.
- **Technical Architecture** — the engineering reference: system architecture, per-capability build status (implemented / partial / not built), data flow, error handling, testing approach, and an explicit list of open architectural gaps — including a fixed-value confidence-score placeholder the codebase itself names honestly rather than hiding.

## Why this project reads differently from a finished-product case study

SupportOps AI is a portfolio build, not a live deployment — there's no production ticket volume, and several capabilities (per-tenant policy thresholds, a real model-derived confidence score, additional agent tools beyond the knowledge base) are documented as open gaps rather than claimed as done. Both documents are written to reflect that status honestly: what's backed by real Postgres/Redis logic and a 167-test suite is marked verified; what's still a `TODO` in the code is called out as an open gap, not glossed over.

## How to edit

Content lives directly in `case-study.html` / `technical-architecture.html` as semantic `<section>` blocks; the `.md` files are the plain-text equivalents kept in sync by hand. Shared visual language lives in `styles.css` (identical design system to the other case studies in this portfolio) — edit content in the HTML files, not the CSS, for normal changes.

## Exporting to PDF

Both PDFs were generated headlessly via the Chrome DevTools Protocol (`Page.printToPDF` with `displayHeaderFooter: false`) rather than the plain `chrome --headless --print-to-pdf` CLI flag, which on this machine always injected a browser-default header/footer regardless of flags passed. To regenerate after edits, open either HTML file in a Chromium-based browser and use **Print → Save as PDF** (the stylesheet sets A4 size and margins via `@page`, headers/footers off), or drive `Page.printToPDF` over the DevTools Protocol.

## Design notes

Same visual system as this portfolio's other case studies: dark-navy headings and table headers, a blue accent for section numbers/links, tinted stage/card backgrounds to distinguish pipeline steps, and green/amber/red status pills for implementation status. Resources/verification links are isolated at the bottom of each document, not woven into the narrative.
