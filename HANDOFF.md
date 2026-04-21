# CareCompanion — Project Handoff Brief
**For:** Next Claude agent (paid tier)
**Date:** April 2026
**Status:** ~85% complete — core app fully functional, polish items remaining

---

## What This Project Is

A single HTML file app sold on Etsy as a digital download. Target buyer: adult children (40–60yo women) caring for an aging parent. Priced at $25–$35.

- **No installation** — opens in any browser, double-click the .html file
- **No server, no account, no subscription** — 100% local localStorage
- **AI features** via Anthropic API (user supplies their own API key)
- **Single file** — everything is self-contained in carecompanion.html

---

## Files In This Bundle

| File | Description |
|------|-------------|
| `carecompanion.html` | The main app — 135KB, 3168 lines, 61 JS functions |
| `carecompanion_demo.html` | Same app pre-loaded with realistic sample data (Margaret, dementia + diabetes) |
| `CareCompanion_README.docx` | Professional user guide to bundle with Etsy sale |
| `HANDOFF.md` | This document |

---

## Tech Stack

- **Pure HTML/CSS/JS** — no frameworks, no build tools, no npm
- **localStorage** for all persistence
- **Anthropic API** (`claude-sonnet-4-20250514`) called directly from browser
- **Google Fonts** — Playfair Display + Lato (loaded from CDN)
- **No external JS libraries**

### localStorage Keys
```
cc_profile       — { name, dob, condition, caregiver }
cc_medications   — array of medication objects
cc_logs          — array of symptom log entries
cc_appointments  — array of appointment objects
cc_careteam      — array of contact objects
cc_handoff       — array of handoff note objects
cc_memories      — array of memory box entries
cc_stress        — array of caregiver wellbeing check-ins
cc_emergency     — emergency card field values
cc_disclaimer    — boolean
cc_medchecks     — legacy key (unused, kept for compat)
cc_medchecks_YYYY-MM-DD — daily medication check-off state (auto-purged)
cc_apikey        — Anthropic API key
cc_tour_done     — boolean, set after onboarding tour completed
```

---

## App Sections (11 total)

| Section | Nav Index | Page ID | Key Functions |
|---------|-----------|---------|---------------|
| Dashboard | 0 | page-dashboard | renderDashboard() |
| Medications | 1 | page-medications | addMedication(), renderMedications() |
| Symptom Log | 2 | page-symptoms | addLogEntry(), renderSymptomLog() |
| Appointments | 3 | page-appointments | addAppointment(), sortAppointments(), renderAppointments() |
| Care Team | 4 | page-careteam | addContact(), renderCareTeam() |
| Handoff Notes | 5 | page-handoff | addHandoff(), renderHandoff() |
| Memory Box | 6 | page-memory | addMemory(), renderMemories() |
| My Wellbeing | 7 | page-stress | addStressEntry(), renderStress() |
| AI Assistant | 8 | page-ai | sendChat(), generateBriefing(), generateFamilyUpdate(), generateDoctorPrep(), checkInteractions() |
| Emergency Card | 9 | page-emergency | loadEmergencyCard(), saveEmergencyFields(), updateEmergencyCard() |
| Data & Backup | 10 | page-export | exportData(), importData(), clearAllData() |

---

## Design System

### Colour Palette (CSS variables)
```css
--cream: #faf7f2        /* page background */
--warm-white: #fff9f4   /* card background */
--sage: #7a9e87         /* primary action colour */
--sage-dark: #4e7560    /* hover state */
--rose: #c9847a         /* secondary / delete */
--brown: #6b5344        /* sidebar background, headings */
--gold: #c4a46b         /* accents, highlights */
--text: #111111         /* body text */
--text-muted: #2a2a2a   /* secondary text */
--border: #c8b8a8       /* borders */
```

### Typography
- **Display/headings:** Playfair Display (Google Fonts)
- **Body:** Lato (Google Fonts)
- **Base size:** 18px, weight 400

### Responsive Breakpoints
- Desktop > 1024px: Full 260px sidebar
- Tablet 769–1024px: 64px icon-only sidebar
- Mobile ≤ 768px: Slide-out sidebar with hamburger button + swipe gestures

---

## Key Architectural Decisions

### Why No Frameworks
Kept as vanilla HTML/JS deliberately so any non-developer can open and inspect the file. No build step means buyers can trust what they're running.

### Why localStorage (Not IndexedDB)
Simpler API, synchronous reads, enough for this data volume. The downside (cleared by browser cache wipe) is mitigated by the JSON export/import backup system.

### The `file://` Protocol Issue
Running from local filesystem blocks `location.reload()`. All post-action refreshes use manual `renderAll()` calls instead. Never use `location.reload()` in this codebase.

### Global Dark Text Override
Early in the CSS there is:
```css
p, span, div, li, td, th, label, input, select, textarea, button, a {
  color: #111111;
}
```
This was added after persistent text contrast issues. Sidebar, buttons, hero, and chat bubbles override this with `!important` rules. Be careful adding new colour-specific elements — they may need an explicit override.

### AI Context Injection
`getContextSummary()` builds a plain-text summary of profile, medications, recent logs, and appointments. This is prepended as the system prompt to every AI call, giving the model full care context without the user having to re-explain.

---

## What's Complete ✅

- All 11 sections fully functional
- CRUD operations on all data types with delete buttons
- Medication daily check-off (persists per day, auto-resets midnight)
- Emergency card auto-populates from profile + care team + medications
- Appointment sorting (by date then time, past/upcoming visual separation)
- Getting Started checklist on empty dashboard (disappears when complete)
- Trend charts: mood, pain, caregiver wellbeing (14-day bar charts)
- Good Days strip (auto-shows when 😊 mood entries exist)
- Burnout alert (triggers when avg wellbeing ≤ 4 over last 5 entries)
- AI: chat, briefing, family update, doctor prep, medication interaction check
- Onboarding tour (6 steps, highlights nav items, fires after setup)
- Data export (JSON, dated filename, delayed URL revoke)
- Data import (validates file, counts sections, re-renders all UI without reload)
- Mobile sidebar (hamburger, slide animation, swipe gestures, overlay tap-to-close)
- Print styles (emergency card only, sidebar/buttons hidden)
- Disclaimer + setup flow (no flash, correct sequencing)
- README.docx user guide (12 pages, professionally formatted)
- QC: 19/19 static checks passing, JS syntax clean, no duplicate functions/IDs

---

## What Still Needs Work 🔧

### High Priority
1. **Search/filter on long lists** — once a user has 30+ log entries or 10+ medications, there's no way to search or filter. Most impactful UX gap remaining.
2. **Medication refill alerts on dashboard** — medications with upcoming refill dates should surface on the dashboard (e.g. "3 medications need refill this week"). The `refill` field is stored but never surfaced.

### Medium Priority
3. **Symptom log pagination** — the log list can get very long. Add a "Show more / Show less" toggle or show only the last 30 days by default.
4. **Appointment past/upcoming count in stat card** — the "Next Appointment" stat card could show the full upcoming count, not just the next one.
5. **Memory box search** — ability to search or filter memories by mood or keyword.
6. **Print stylesheet for Handoff Notes** — currently only the emergency card has good print styles. A printable handoff summary would be useful.

### Low Priority / Nice to Have
7. **Dark mode** — the CSS variables are already set up for it, just needs a toggle and a `prefers-color-scheme` media query.
8. **Keyboard shortcuts** — power users would benefit from `Ctrl+M` for medications, `Ctrl+L` for log, etc.
9. **Export as PDF** — currently only JSON export. A formatted PDF of the full care record would be valuable.
10. **Etsy listing** — needs mockup screenshots showing the app in action. Consider creating 5–7 lifestyle mockup images.

---

## Etsy Listing Strategy

### Two-Tier Pricing (Recommended)
- **Classic Edition** — $14: All tracking features, no AI. Good entry point.
- **AI Edition** — $29: Everything + AI features. Main product.

### Listing Keywords to Target
`caregiver organizer`, `elderly parent care tracker`, `medication tracker printable`, `caregiver planner digital`, `dementia caregiver tool`, `family caregiver app`, `aging parent organizer`

### Bundle With
- `carecompanion.html` (the app)
- `CareCompanion_README.docx` (user guide)
- A 1-page Quick Start PDF (not yet created — good first task)

---

## Development Workflow

### Testing Changes
1. Make edits to `carecompanion.html`
2. Syntax check: extract `<script>` block and run `node --check`
3. Open in browser, use "↺ Reset & Start Fresh" in sidebar to clear state
4. Test with the demo file (`carecompanion_demo.html`) for populated data
5. Test mobile by opening browser DevTools → Toggle device toolbar

### QC Script Pattern
The previous agent built Python QC scripts to check for:
- Duplicate function names
- Duplicate HTML IDs
- Missing `getElementById` targets
- `KEYS` reference integrity
- Tooltip nav indices in range
- No `location.reload()` calls
Run these after any significant change.

### Critical Rules
- **Never use `location.reload()`** — blocked on `file://` protocol
- **Never add duplicate function declarations** — JS silently uses the last one
- **Always syntax-check JS** before delivering — a single syntax error breaks everything
- **Test the disclaimer/setup flow** in an incognito window when touching that code
- **The global color override** (`button { color: #111111 }`) — new white-on-dark elements need `color: white !important`

---

## Sample Data

The `carecompanion_demo.html` file contains pre-loaded data for "Margaret" (82, vascular dementia + type 2 diabetes). Data includes:
- 8 medications (Metformin, Lisinopril, Donepezil, Aspirin, Atorvastatin, Vitamin D3, Lorazepam, Melatonin)
- 21 days of symptom logs
- 8 appointments (6 upcoming, 2 past)
- 6 care team contacts
- 5 handoff notes
- 8 memory entries
- 14 caregiver wellbeing check-ins

Use this file to test features with realistic data.

---

## Conversation Context

This project was built from scratch over a single long conversation. The progression was:

1. Research phase — identified caregiver app market, Etsy digital product strategy
2. Design phase — settled on aesthetic (warm, organic, not clinical), feature set, legal considerations
3. Build phase — iterative HTML/CSS/JS development
4. Bug fix phase — disclaimer flow, navigation, tour, export/import
5. Polish phase — medication persistence, emergency card autofill, mobile, getting started, appointment sort
6. Documentation — README.docx

The buyer (Kevin) is non-technical, sells on Etsy, and wants to offer both a Classic and AI Edition. The primary target buyer is adult children caring for aging parents.

---

*Generated April 2026 — CareCompanion v1.0*
