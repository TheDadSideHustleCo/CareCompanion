#!/usr/bin/env python3
"""
CareCompanion-specific QA script.
Tests: code integrity, PWA readiness, print system, data persistence, UI correctness.
Usage: python3 carecompanion_qa.py <path-to-html-file>
"""

import re, sys, subprocess, tempfile, os

if len(sys.argv) < 2:
    print("Usage: carecompanion_qa.py <path-to-html-file>")
    sys.exit(1)

with open(sys.argv[1], 'r') as f:
    html = f.read()

passes, fails, warns = [], [], []

def ok(name):         passes.append(f"  ✓  {name}")
def fail(name, why):  fails.append(f"  ✗  {name}: {why}")
def warn(name, why):  warns.append(f"  ⚠  {name}: {why}")
def find(p, fl=0):    return re.search(p, html, fl)
def count(p, fl=0):   return len(re.findall(p, html, fl))
def has(s):           return s in html

def fn_body(name):
    """Extract the full body of a JS function by brace counting."""
    m = re.search(rf'function {name}\s*\(', html)
    if not m: return ''
    body = html[m.end():]
    # skip to opening brace
    brace = body.find('{')
    if brace == -1: return ''
    body = body[brace+1:]
    depth = 1; pos = 0
    while pos < len(body) and depth > 0:
        if body[pos] == '{': depth += 1
        elif body[pos] == '}': depth -= 1
        pos += 1
    return body[:pos]


# ════════════════════════════════════════
#  LAYER 0 — SECURITY (always run first)
#  XSS via innerHTML must be caught before
#  any layout or functionality check.
# ════════════════════════════════════════

# 0a — esc() sanitizer defined
if find(r'function esc\s*\('):
    ok("esc() sanitizer function defined")
else:
    fail("esc() sanitizer missing", "User text injected raw into innerHTML — XSS vulnerability")

# 0b — free-text fields wrapped in esc() before innerHTML injection
xss_risk_fields_l0 = [
    r'a\.title', r'a\.doctor', r'a\.address', r'a\.notes', r'a\.visitNotes',
    r'm\.name', r'm\.dose', r'm\.notes',
    r'c\.name', r'c\.notes',
    r'n\.meds', r'n\.notes',
    r'mem\.title', r'mem\.text',
    r'e\.notes', r'e\.gratitude',
    r'l\.symptoms', r'l\.questions',
]
xss_raw = []
for field in xss_risk_fields_l0:
    raw = re.search(rf'\$\{{{field}\}}', html)
    escaped = re.search(rf'\$\{{esc\({field}\)\}}', html)
    if raw and not escaped:
        xss_raw.append(field.replace('\\', ''))
if xss_raw:
    fail("XSS — raw user text in innerHTML", f"Not wrapped in esc(): {xss_raw[:5]}")
else:
    ok("All free-text fields wrapped in esc() — XSS protected")

# 0c — no eval() or Function() constructor
if not find(r'\beval\s*\(|\bnew\s+Function\s*\('):
    ok("No eval() or new Function() — no remote code execution risk")
else:
    fail("eval() or new Function() found", "Dynamic code execution — high security risk")


# ════════════════════════════════════════
#  LAYER 1 — CODE INTEGRITY
# ════════════════════════════════════════

scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
combined = '\n'.join(scripts)
with tempfile.NamedTemporaryFile(suffix='.js', mode='w', delete=False) as f:
    f.write(combined); tmpjs = f.name
result = subprocess.run(['node', '--check', tmpjs], capture_output=True, text=True)
os.unlink(tmpjs)
if result.returncode == 0: ok("JS syntax valid")
else: fail("JS syntax", result.stderr.split('\n')[0])

if find(r'CareCompanion v1\.\d'): ok("Version string in UI")
else: fail("Version string", "Not shown in sidebar/UI")

m = find(r"_version:\s*'([^']+)'")
if m: ok(f"Backup schema version set ({m.group(1)})")
else: fail("Backup schema version", "_version missing from export object")

if count(r'console\.log') == 0: ok("No console.log statements")
else: fail("Debug logs", f"{count(r'console.log')} console.log found")

ai_remnants = ['Anthropic', 'Your API key', 'currentAiPanel', '.chat-bubble', '.chat-msg', 'chat-avatar']
found = [r for r in ai_remnants if r in html]
if not found: ok("No AI/API remnants")
else: fail("AI remnants", f"Found: {found}")

if find(r'const KEYS\s*=\s*\{'): ok("KEYS object defined")
else: fail("KEYS object", "localStorage key map missing")

# Check for duplicate function definitions — later definition silently overrides earlier one
fn_names = re.findall(r'\bfunction\s+(\w+)\s*\(', combined)
from collections import Counter as _Counter
fn_counts = _Counter(fn_names)
dupes = [name for name, cnt in fn_counts.items() if cnt > 1]
if not dupes:
    ok("No duplicate function definitions")
else:
    for name in dupes:
        fail(f"Duplicate function: {name}()",
             f"Defined {fn_counts[name]}x — later definition silently overrides earlier one")

for k in ['profile','medications','logs','appointments','careteam','handoff','memories','stress','disclaimer','medChecks','emergency']:
    if k in html: ok(f"KEYS.{k} present")
    else: fail(f"KEYS.{k}", "Missing from KEYS object")


# ════════════════════════════════════════
#  LAYER 2 — PWA READINESS
# ════════════════════════════════════════

if has("serviceWorker.register"): ok("Service worker registered")
else: fail("Service worker", "No registration call found")

sw_v = find(r"carecompanion-v(\d+)")
if sw_v:
    ok(f"SW cache versioned (v{sw_v.group(1)})")
else:
    # SW may be a separate file — check same dir, parent dir, and gitpush/ sibling
    import os as _os
    html_dir = _os.path.dirname(_os.path.abspath(sys.argv[1]))
    candidate_paths = [
        _os.path.join(html_dir, 'sw.js'),
        _os.path.join(html_dir, '..', 'gitpush', 'sw.js'),
        _os.path.join(html_dir, 'gitpush', 'sw.js'),
    ]
    sw_found = False
    for sw_path in candidate_paths:
        if _os.path.exists(sw_path):
            sw_content = open(sw_path).read()
            sw_v2 = re.search(r"carecompanion-v(\d+)", sw_content)
            if sw_v2:
                ok(f"SW cache versioned in sw.js (v{sw_v2.group(1)})")
            else:
                warn("SW cache version", f"sw.js found at {sw_path} but no version string")
            sw_found = True
            break
    if not sw_found:
        warn("SW cache version", "No sw.js found — cannot verify cache version")

if has("SKIP_WAITING"): ok("SKIP_WAITING handler present")
else: fail("SKIP_WAITING", "Update mechanism missing")

if find(r"setInterval.*reg\.update"): ok("60s SW update polling present")
else: warn("SW polling", "No setInterval update polling found")

for tag, label in [
    ('name="viewport"', "Viewport meta"),
    ('apple-mobile-web-app-capable', "iOS PWA meta"),
    ('mobile-web-app-capable', "Android PWA meta"),
    ('theme-color', "theme-color meta"),
    ('rel="manifest"', "manifest.json link"),
    ('rel="apple-touch-icon"', "Apple touch icon"),
]:
    if has(tag): ok(f"{label} present")
    else: warn(label, f"Missing: {tag}")

if find(r'sw-update-banner|id="update-banner"|update.*banner', re.IGNORECASE): ok("Update banner UI present")
else: fail("Update banner", "No update banner element found")


# ════════════════════════════════════════
#  LAYER 3 — PRINT SYSTEM
# ════════════════════════════════════════

print_buttons = re.findall(r'onclick="([^"]*window\.print[^"]*)"', html)
if len(print_buttons) >= 5: ok(f"{len(print_buttons)} print buttons found")
else: fail("Print buttons", f"Only {len(print_buttons)} found, expected 5+")

for b in print_buttons:
    if 'addEventListener' in b:
        fail("Safari print block", f"addEventListener in button: {b[:80]}")
    else:
        ok(f"No addEventListener in: ...{b[-40:]}")

for section in ['med','ct','handoff','ec','visit']:
    if f"dataset.print='{section}'" in html: ok(f"data-print='{section}' set on button")
    else: fail(f"data-print='{section}'", "Button missing this attribute")

media_block = ''
m = find(r'@media print\s*\{(.*?)\n  </style>', re.DOTALL)
if m: media_block = m.group(1)

for section in ['med','ct','handoff','ec']:
    rule = f'body[data-print="{section}"] #{section}-print-header'
    if rule in html: ok(f"CSS shows #{section}-print-header")
    else: fail(f"#{section}-print-header CSS", f"Missing @media print rule: {rule}")

if '#page-visit-prep { display: none !important; }' in html: ok("Visit prep hidden by default in @media print")
else: fail("Visit prep default hide", "#page-visit-prep not explicitly hidden in @media print")

# Visit prep must NOT be nested inside a .page div (parent display:block overrides child display:none)
vp_pos = html.find('id="page-visit-prep"')
page_starts = [m.start() for m in re.finditer(r'class="page"', html)]
page_ends = []
for ps in page_starts:
    # Find matching closing div by counting depth
    depth = 0
    i = ps
    while i < len(html):
        if html[i:i+4] == '<div': depth += 1
        elif html[i:i+6] == '</div':
            depth -= 1
            if depth == 0: page_ends.append(i); break
        i += 1
nested = any(ps < vp_pos < pe for ps, pe in zip(page_starts, page_ends))
if nested: fail("Visit prep DOM position", "#page-visit-prep is nested inside a .page div — parent display:block overrides child display:none, bleed onto every print")
else: ok("Visit prep is not nested inside a .page div")

if 'body[data-print="visit"] #page-visit-prep' in html: ok("Visit prep shown only for data-print='visit'")
else: fail("Visit prep show rule", "Missing CSS rule")

if media_block and re.search(r'\.print-doc-header\s*\{[^}]*display\s*:\s*flex', media_block):
    fail("Blanket print-doc-header", "display:flex forces ALL headers visible on every print — blank pages")
else:
    ok("No blanket .print-doc-header display:flex in @media print")

vp = find(r'id="visit-prep-print-header"[^>]*style="([^"]*)"')
if vp and 'flex' in vp.group(1).replace(' ',''):
    fail("visit-prep-print-header inline style", "display:flex overrides CSS hide — blank page on every print")
else:
    ok("visit-prep-print-header not inline flex")

ap_count = count(r"addEventListener\('afterprint'")
if ap_count == 1: ok("Single afterprint handler")
elif ap_count == 0: fail("afterprint handler", "No afterprint cleanup registered")
else: fail("afterprint handler", f"{ap_count} registered — will cause double-cleanup")

if has('delete document.body.dataset.print'): ok("afterprint removes data-print attribute")
else: fail("afterprint cleanup", "data-print not removed — second print uses wrong header")

med_calls = [m.start() for m in re.finditer(r'renderMedicationPrintTable\(\)', html)]
med_fn = find(r'function renderMedicationPrintTable')
if med_fn and len(med_calls) >= 2 and min(med_calls) < med_fn.start():
    ok(f"Medication print table pre-rendered at startup ({len(med_calls)} call sites)")
else:
    fail("Medication table startup", f"renderMedicationPrintTable called {len(med_calls)} times — needs startup call before function def")

ct_calls = count(r'renderCareTeamPrintGrid\(\)')
if ct_calls >= 3: ok(f"Care team grid pre-rendered ({ct_calls} call sites)")
else: warn("Care team grid", f"Only {ct_calls} call sites — needs startup, save, and delete calls")


# ════════════════════════════════════════
#  LAYER 4 — DATA PERSISTENCE
# ════════════════════════════════════════

if find(r'function save\s*\(') and find(r'function load\s*\('): ok("save() and load() functions defined")
else: fail("save/load", "Core persistence functions missing")

if find(r'try\s*\{[^}]*localStorage', re.DOTALL): ok("localStorage wrapped in try/catch")
else: fail("localStorage safety", "No try/catch around localStorage")

if find(r"data\._app.*CareCompanion|_app.*!==.*CareCompanion"):
    ok("Backup import validates _app field")
else:
    fail("Backup validation", "Import does not check _app — wrong file imports silently")


# ════════════════════════════════════════
#  LAYER 5 — UI CORRECTNESS
# ════════════════════════════════════════

for s in ['dashboard','medications','symptoms','appointments','careteam','handoff','memory','stress','emergency','export']:
    if f"navigate('{s}'" in html or f'navigate("{s}"' in html: ok(f"Nav '{s}' present")
    else: fail(f"Nav '{s}'", "Not found in navigation")

if "As needed (PRN)" in html: ok("PRN frequency option present")
else: fail("PRN frequency", "'As needed (PRN)' missing from dropdown")

if find(r"toLowerCase\(\)\.includes\(['\"]as needed"):
    ok("PRN refill check uses includes() not strict equality")
else:
    fail("PRN refill check", "May miss PRN meds — use .toLowerCase().includes()")

for fn in ['deleteContact','deleteHandoff','deleteMemory','deleteStress']:
    block = find(rf'function {fn}.*?^}}', re.DOTALL | re.MULTILINE)
    if block and 'confirm(' in block.group(0): ok(f"{fn}() has confirm()")
    else: warn(f"{fn}() confirm", "No confirm() dialog — accidental deletes possible")

for fn in ['addMemory','deleteMemory','addStressEntry','deleteStress','addHandoff','deleteHandoff']:
    block = find(rf'function {fn}.*?^}}', re.DOTALL | re.MULTILINE)
    if block and 'renderDashboard()' in block.group(0): ok(f"renderDashboard() called in {fn}()")
    else: fail(f"renderDashboard in {fn}()", "Dashboard not updated after mutation")

if has('cc_tour_done') and has('hasData'): ok("Tour suppressed for returning users")
else: fail("Tour suppression", "Returning users may see onboarding tour")

if find(r'font-size:\s*18px'): ok("Base font 18px (elderly-appropriate)")
else: warn("Base font size", "18px not found")


# ════════════════════════════════════════
#  LAYER 6 — BUTTON TARGETING INTEGRITY
#  Checks that querySelector/getElementById calls in edit functions
#  resolve to the correct unique element, not an ambiguous first match.
# ════════════════════════════════════════

# For each page, check that edit functions use getElementById (unambiguous)
# not querySelector('.btn-primary') which matches the FIRST btn-primary on the page.
# Pattern: if a page has >1 btn-primary and an edit function uses querySelector for that page, it's a bug.

pages_with_multiple_primary_btns = []
page_ids = re.findall(r'id="page-(\w+)"', html)
for page in set(page_ids):
    page_m = re.search(rf'id="page-{page}"', html)
    if not page_m: continue
    # Find end of this page's div (rough: next page div or end of body)
    next_page = re.search(r'id="page-\w+"', html[page_m.end():])
    end = page_m.end() + next_page.start() if next_page else len(html)
    page_html = html[page_m.start():end]
    btn_primaries = len(re.findall(r'class="btn btn-primary"', page_html))
    if btn_primaries > 1:
        pages_with_multiple_primary_btns.append((page, btn_primaries))

for page, count_btns in pages_with_multiple_primary_btns:
    qs = find(rf"querySelector\(['\"]#page-{page} .btn-primary['\"]")
    if qs:
        fail(f"Button targeting on '{page}' page",
             f"querySelector('#page-{page} .btn-primary') is ambiguous — {count_btns} btn-primary elements exist. Use getElementById on a dedicated ID instead.")
    else:
        ok(f"Button targeting on '{page}' page ({count_btns} btn-primaries, no ambiguous querySelector)")

# Check that edit functions for each section use getElementById for their save button
save_btn_checks = [
    ('med-save-btn',    'addMedication',    'Medication save button has dedicated ID'),
    ('appt-save-btn',   'addAppointment|saveAppointment', 'Appointment save button has dedicated ID'),
    ('ct-save-btn',     'addContact|saveContact',         'Care team save button has dedicated ID'),
    ('ho-save-btn',     'addHandoff|saveHandoff',         'Handoff save button has dedicated ID'),
    ('stress-save-btn', 'addStressEntry|saveStress',      'Stress save button has dedicated ID'),
    ('log-save-btn',    'addLogEntry|saveLog',            'Symptom log save button has dedicated ID'),
]
for btn_id, fn_pattern, label in save_btn_checks:
    has_id = f'id="{btn_id}"' in html
    has_fn = bool(find(fn_pattern))
    if not has_fn:
        pass  # function doesn't exist, skip
    elif has_id:
        ok(label)
    else:
        warn(label, f'id="{btn_id}" not found — edit→save may target wrong button if page has multiple btn-primary')

# Check that querySelector('.btn-primary') is never used to change button text in edit functions
ambiguous_qs = re.findall(r"querySelector\(['\"][^'\"]*\.btn-primary['\"][^)]*\)\.textContent\s*=", html)
if ambiguous_qs:
    fail("Ambiguous btn-primary querySelector", f"{len(ambiguous_qs)} instance(s) set textContent via querySelector('.btn-primary') — use getElementById with a dedicated ID")
else:
    ok("No ambiguous .btn-primary querySelector targeting")


# ════════════════════════════════════════
#  LAYER 7 — EDIT STATE MANAGEMENT
#  Each section has an editingXxxId variable. Verify it is always
#  cleared after save/delete/cancel so forms can't get stuck in edit mode.
# ════════════════════════════════════════

edit_vars = [
    ('editingMedId',     'addMedication',   'deleteMedication'),
    ('editingLogId',     'addLogEntry',      'deleteLog'),
    ('editingApptId',    'addAppointment',   'deleteAppointment'),
    ('editingContactId', 'addContact',       'deleteContact'),
    ('editingHandoffId', 'addHandoff',       'deleteHandoff'),
    ('editingStressId',  'addStressEntry',   'deleteStress'),
    ('editingMemoryId',  'addMemory',        'deleteMemory'),
]

for var, save_fn, delete_fn in edit_vars:
    if var not in html:
        continue  # section not present

    # Save function must null the var
    body = fn_body(save_fn)
    if body:
        if f'{var} = null' in body:
            ok(f"{var} cleared in {save_fn}()")
        else:
            fail(f"{var} not cleared in {save_fn}()", "Edit state persists after save — re-opening form may corrupt new entries")

    # Delete function must null the var (in case user deletes while editing)
    body = fn_body(delete_fn)
    if body:
        if var in body and 'null' in body:
            ok(f"{var} cleared in {delete_fn}() if editing deleted record")
        else:
            warn(f"{var} in {delete_fn}()", "Deleting while editing may leave stale editingId")


# ════════════════════════════════════════
#  LAYER 8 — DATA ROUND-TRIP INTEGRITY
#  For each add/edit form, verify every field that is written to
#  localStorage is also read back when populating the edit form.
# ════════════════════════════════════════

# Extract fields written to localStorage in each save function
# and fields read back in each edit function — check they match.
form_pairs = [
    ('addMedication', 'editMedication', [
        'med-name', 'med-dose', 'med-freq', 'med-food',
        'med-notes', 'med-doctor', 'med-refill', 'med-pills',
    ]),
    ('addLogEntry', 'editLog', [
        'log-date', 'log-sleep', 'log-appetite', 'log-pain', 'log-symptoms', 'log-questions',
    ]),
    ('addAppointment', 'editAppointment', [
        'appt-title', 'appt-date', 'appt-doctor', 'appt-location', 'appt-notes',
    ]),
    ('addContact', 'editContact', [
        'ct-name', 'ct-role', 'ct-phone', 'ct-email', 'ct-notes',
    ]),
    ('addHandoff', 'editHandoff', [
        'ho-date', 'ho-notes',
    ]),
    ('addStressEntry', 'editStress', [
        'stress-date', 'stress-notes',
    ]),
]

for save_fn, edit_fn, fields in form_pairs:
    save_body = fn_body(save_fn)
    edit_body = fn_body(edit_fn)
    if not save_body or not edit_body:
        continue
    for field in fields:
        in_save = field in save_body
        in_edit = field in edit_body
        if in_save and in_edit:
            ok(f"{field} saved and restored in {save_fn}/{edit_fn}")
        elif in_save and not in_edit:
            fail(f"{field} not restored in {edit_fn}()", "Field is saved but edit form never populates it — user sees blank field when editing")
        elif not in_save and in_edit:
            warn(f"{field} in {edit_fn} but not {save_fn}", "Field restored in edit form but may not be saved")
        # both missing — field doesn't exist in this form, skip


# ════════════════════════════════════════
#  LAYER 9 — RENDER-AFTER-MUTATION
#  Every function that saves or deletes data must call the
#  correct render function so the UI reflects the change immediately.
# ════════════════════════════════════════

render_checks = [
    # (function, renders_that_must_be_called)
    ('addMedication',   ['renderMedications', 'renderDashboard']),
    ('deleteMedication',['renderMedications', 'renderDashboard']),
    ('addLogEntry',     ['renderSymptomLog',  'renderDashboard']),
    ('deleteLog',       ['renderSymptomLog',  'renderDashboard']),
    ('addAppointment',  ['renderAppointments','renderDashboard']),
    ('deleteAppointment',['renderAppointments','renderDashboard']),
    ('addContact',      ['renderCareTeam']),
    ('deleteContact',   ['renderCareTeam']),
    ('addHandoff',      ['renderHandoff',     'renderDashboard']),
    ('deleteHandoff',   ['renderHandoff',     'renderDashboard']),
    ('addMemory',       ['renderMemories',    'renderDashboard']),
    ('deleteMemory',    ['renderMemories',    'renderDashboard']),
    ('addStressEntry',  ['renderStress',      'renderDashboard']),
    ('deleteStress',    ['renderStress',      'renderDashboard']),
]

for fn, renders in render_checks:
    body = fn_body(fn)
    if not body:
        continue
    for render in renders:
        if render + '()' in body:
            ok(f"{fn}() calls {render}()")
        else:
            fail(f"{fn}() missing {render}()", "UI not updated after mutation — user sees stale data until page refresh")


# ════════════════════════════════════════
#  LAYER 10 — INPUT VALIDATION
#  Required fields must be guarded. Number fields must handle
#  zero, empty, and non-numeric without crashing.
# ════════════════════════════════════════

# Each save function should have at least one guard (alert/return) for required fields
required_guards = [
    ('addMedication',  r"if\s*\(!name\)|if\s*\(name\s*===|alert.*name"),
    ('addLogEntry',    r"if\s*\(!date\)|if\s*\(!.*log-date|alert.*date"),
    ('addAppointment', r"if\s*\(!.*title\)|if\s*\(!.*date\)|alert.*(title|date)"),
    ('addContact',     r"if\s*\(!.*name\)|alert.*name"),
    ('addHandoff',     r"if\s*\(!.*notes\)|if\s*\(!.*date\)|alert.*(note|date)"),
    ('addStressEntry', r"if\s*\(!.*date\)|if\s*\(!selected|alert.*(date|wellbeing|select|level)"),
]

for fn, guard_pattern in required_guards:
    body = fn_body(fn)
    if not body:
        continue
    if re.search(guard_pattern, body, re.IGNORECASE):
        ok(f"{fn}() validates required fields")
    else:
        warn(f"{fn}() missing required field validation", "Form may save empty/invalid records")

# Number fields: parseInt result should be guarded against NaN
number_field_uses = re.findall(r'parseInt\([^)]+\)', html)
nan_checks = count(r'isNaN\(|Number\.isNaN\(|\|\|\s*0\b|!.*parseInt|parseInt.*\|\|')
if nan_checks >= 3:
    ok(f"parseInt results guarded against NaN ({nan_checks} guards found)")
else:
    warn("NaN guards", f"Only {nan_checks} parseInt guards — number fields may crash on non-numeric input")

# Date fields: new Date() on empty string gives Invalid Date
date_guards = count(r"\.value\s*&&.*new Date|if\s*\(.*date\).*new Date|new Date\(.*\+.*T12")
if date_guards >= 2:
    ok(f"Date fields guarded before new Date() ({date_guards} patterns)")
else:
    warn("Date field safety", f"Only {date_guards} date guards — empty date fields may produce Invalid Date errors")


# ════════════════════════════════════════
#  LAYER 11 — RECORD ID INTEGRITY
#  Every record type must have a unique id assigned on creation
#  and preserved through edits. Without this, edit/delete targets
#  the wrong record or creates duplicates.
# ════════════════════════════════════════

# Each add function must assign id: Date.now() to new records
id_checks = [
    ('addMedication',  'id: Date.now()'),
    ('addLogEntry',    'id: Date.now()'),
    ('addAppointment', 'id: Date.now()'),
    ('addContact',     'id: Date.now()'),
    ('addHandoff',     'id: Date.now()'),
    ('addStressEntry', 'id: Date.now()'),
    ('addMemory',      'id: Date.now()'),
]
for fn, pattern in id_checks:
    body = fn_body(fn)
    if not body: continue
    if pattern in body:
        ok(f"{fn}() assigns unique id to new records")
    else:
        fail(f"{fn}() missing id assignment", "Records created without unique ID — edit/delete will fail")

# Each edit function must use the id to find the record (not name/index)
edit_id_checks = [
    ('editMedication',  r'\.find\(.*\.id\s*==='),
    ('editLog',         r'\.find\(.*\.id\s*==='),
    ('editAppointment', r'\.find\(.*\.id\s*==='),
    ('editContact',     r'\.find\(.*\.id\s*==='),
    ('editHandoff',     r'\.find\(.*\.id\s*==='),
    ('editStress',      r'\.find\(.*\.id\s*==='),
    ('editMemory',      r'\.find\(.*\.id\s*==='),
]
for fn, pattern in edit_id_checks:
    body = fn_body(fn)
    if not body: continue
    if re.search(pattern, body):
        ok(f"{fn}() looks up record by id (not index/name)")
    else:
        warn(f"{fn}() record lookup", "Not using .find(x => x.id === id) — may edit wrong record")

# Edit/update spreads new data over existing record (preserving unedited fields)
spread_checks = [
    # Pattern: { ...existing, ...newData } — may have extra fields after the spreads
    ('addMedication',   r'\{\s*\.\.\.\w+,\s*\.\.\.\w+'),
    ('addLogEntry',     r'\{\s*\.\.\.\w+,\s*\.\.\.\w+'),
    ('addAppointment',  r'\{\s*\.\.\.\w+,\s*\.\.\.\w+'),
    ('addContact',      r'\{\s*\.\.\.\w+,\s*\.\.\.\w+'),
    ('addHandoff',      r'\{\s*\.\.\.\w+,\s*\.\.\.\w+'),
    ('addStressEntry',  r'\{\s*\.\.\.\w+,\s*\.\.\.\w+'),
    ('addMemory',       r'\{\s*\.\.\.\w+,\s*\.\.\.\w+'),
]
for fn, pattern in spread_checks:
    body = fn_body(fn)
    if not body: continue
    if re.search(pattern, body):
        ok(f"{fn}() spreads existing record when editing (preserves unedited fields)")
    else:
        warn(f"{fn}() edit spread", "May overwrite entire record instead of merging — could lose fields")


# ════════════════════════════════════════
#  LAYER 12 — FREQUENCY / DOSE COVERAGE
#  freqToDoseCount() must handle every option in the frequency
#  dropdown. Missing options return undefined → NaN in pill math.
# ════════════════════════════════════════

# Extract all <option> values from the frequency dropdown
freq_options = re.findall(r'<option[^>]*>([^<]+)</option>', html)
# Filter to frequency-looking options (exclude food/sleep/etc dropdowns)
freq_keywords = ['daily','twice','three','hours','needed','weekly','monthly']
freq_opts = [o.strip() for o in freq_options if any(k in o.lower() for k in freq_keywords)]

# Verify freqToDoseCount always returns a number (never undefined)
# Strategy: simulate the function logic — check it has a default return (catches all cases).
# A literal-string search is too strict because the function uses .includes() substring matching
# (e.g., 'Once daily'.includes('twice') = false → falls through to return 1, which is correct).
ftd_body = fn_body('freqToDoseCount')
if not ftd_body:
    warn("freqToDoseCount", "Function not found")
else:
    # Must have a numeric default return to cover all unrecognised strings
    has_default_return = bool(re.search(r'return\s+1\b', ftd_body))
    if has_default_return:
        ok("freqToDoseCount has default return 1 — all unrecognised frequencies return 1 (no NaN)")
    else:
        fail("freqToDoseCount missing default return",
             "Unrecognised frequency strings return undefined → NaN in pill math")

    # Verify specific high-risk cases: 'twice' and 'three' must be handled (these are explicit)
    for keyword, expected in [('twice', '2'), ('three', '3'), ('every 8', '3'), ('every 6', '4')]:
        if keyword in ftd_body.lower():
            ok(f"freqToDoseCount handles '{keyword}' → {expected}")
        else:
            fail(f"freqToDoseCount missing '{keyword}' branch",
                 f"Expected return {expected} for this frequency pattern")


# ════════════════════════════════════════
#  LAYER 13 — NAVIGATION INTEGRITY
#  Every page referenced in navigate() has a matching DOM element.
#  pageTitles map covers all navigable pages.
# ════════════════════════════════════════

# Find all navigate() call targets
nav_targets = set(re.findall(r"navigate\(['\"](\w+)['\"]", html))
# Find all page div IDs
page_divs = set(re.findall(r'id="page-(\w+)"', html))
# Find pageTitles map entries
page_titles_block = find(r'const pageTitles\s*=\s*\{([^}]+)\}')
titled_pages = set()
if page_titles_block:
    # Match both quoted ('key':) and bare identifier (key:) forms
    titled_pages = set(re.findall(r"['\"]?(\w+)['\"]?\s*:", page_titles_block.group(1)))

for target in sorted(nav_targets):
    if target in page_divs:
        ok(f"navigate('{target}') has matching page div")
    else:
        fail(f"navigate('{target}') broken", f"No id='page-{target}' div — navigating crashes silently")

for target in sorted(nav_targets):
    if target in titled_pages:
        ok(f"pageTitles covers '{target}'")
    else:
        warn(f"pageTitles missing '{target}'", "Page title bar will show undefined or raw page name")

# Check navigate() render dispatch — every page should have a render call inside navigate()
navigate_body = fn_body('navigate')
if navigate_body:
    for target in sorted(nav_targets):
        # Each page should have: if (page === 'target') renderXxx() or similar
        if f"'{target}'" in navigate_body or f'"{target}"' in navigate_body:
            ok(f"navigate('{target}') has render dispatch")
        else:
            warn(f"navigate('{target}') missing render dispatch",
                 "Page may show stale data — render not called on navigation")


# ════════════════════════════════════════
#  LAYER 14 — BACKUP / RESTORE COMPLETENESS
#  Export must include every KEYS entry.
#  Import must restore every KEYS entry.
#  Neither must silently skip a key.
# ════════════════════════════════════════

# Extract defined KEYS
keys_block = find(r'const KEYS\s*=\s*\{([^}]+)\}')
defined_keys = []
if keys_block:
    defined_keys = re.findall(r"(\w+)\s*:", keys_block.group(1))

export_body = fn_body('exportData')
import_body = fn_body('importData')

# Check if export/import use Object.values(KEYS) bulk iteration — covers all keys automatically
export_bulk = export_body and 'Object.values(KEYS)' in export_body
import_bulk = import_body and 'Object.values(KEYS)' in import_body

if export_bulk:
    ok("exportData() uses Object.values(KEYS) — backs up all keys automatically")
elif export_body:
    # Fall back to per-key literal check
    for key in defined_keys:
        if key in export_body:
            ok(f"exportData() includes KEYS.{key}")
        else:
            fail(f"exportData() missing KEYS.{key}", "This data is never backed up")

if import_bulk:
    ok("importData() uses Object.values(KEYS) — restores all keys automatically")
elif import_body:
    for key in defined_keys:
        if key in import_body:
            ok(f"importData() restores KEYS.{key}")
        else:
            fail(f"importData() missing KEYS.{key}", "This data is never restored from backup")

# Import should not crash on missing keys (graceful degradation)
if import_body and ('||' in import_body or 'hasOwnProperty' in import_body or 'undefined' in import_body):
    ok("importData() handles missing keys gracefully")
else:
    warn("importData() missing key safety", "Importing old backup missing a key may crash or overwrite with undefined")


# ════════════════════════════════════════
#  LAYER 15 — RAW localStorage ACCESS
#  All localStorage calls must go through save()/load() helpers
#  which have try/catch. Direct calls bypass error protection.
# ════════════════════════════════════════

# Find all direct localStorage.setItem / getItem calls
direct_set = [(html[:m.start()].count('\n')+1, html[max(0,m.start()-60):m.end()+60])
              for m in re.finditer(r'localStorage\.setItem\s*\(', html)]
direct_get = [(html[:m.start()].count('\n')+1, html[max(0,m.start()-60):m.end()+60])
              for m in re.finditer(r'localStorage\.getItem\s*\(', html)]

# These are acceptable: save/load helpers, export/import, dynamic-key med checks,
# and any function that uses a runtime-computed key (not a static KEYS entry).
allowed_contexts = ['function save(', 'function load(', 'exportData', 'importData',
                    'cc_medchecks', 'cc_pwa_dismissed', 'cc_tour_done',
                    'toggleMedCheck', 'logPRNDose', 'getTodayKey', 'getMedChecksForToday',
                    'todayKey', 'storageKey']

raw_set_violations = []
for line, ctx in direct_set:
    if not any(a in ctx for a in allowed_contexts):
        raw_set_violations.append(f"line {line}")

raw_get_violations = []
for line, ctx in direct_get:
    if not any(a in ctx for a in allowed_contexts):
        raw_get_violations.append(f"line {line}")

if not raw_set_violations:
    ok("All localStorage.setItem calls are in safe contexts")
else:
    fail("Raw localStorage.setItem", f"Unguarded direct writes at: {', '.join(raw_set_violations)}")

if not raw_get_violations:
    ok("All localStorage.getItem calls are in safe contexts")
else:
    fail("Raw localStorage.getItem", f"Unguarded direct reads at: {', '.join(raw_get_violations)}")


# ════════════════════════════════════════
#  LAYER 16 — PRINT HEADER POPULATION
#  preparePrintHeaders() must be called at startup and after
#  profile save. Print headers must reference IDs that exist.
# ════════════════════════════════════════

if has('preparePrintHeaders'):
    # Must be called at startup (before or after DOMContentLoaded)
    startup_block = re.search(r'DOMContentLoaded[^{]*\{(.{0,3000})', html, re.DOTALL)
    if startup_block and 'preparePrintHeaders' in startup_block.group(1):
        ok("preparePrintHeaders() called at startup")
    else:
        # May be called via renderAll() or similar
        render_all = fn_body('renderAll')
        if render_all and 'preparePrintHeaders' in render_all:
            ok("preparePrintHeaders() called via renderAll() at startup")
        else:
            fail("preparePrintHeaders() startup", "Print headers never populated on first load — blank patient name on print")

    # Must be called after profile is saved (function may be named saveProfile or saveSetup)
    save_profile_body = fn_body('saveProfile') or fn_body('saveSetup')
    if save_profile_body and 'preparePrintHeaders' in save_profile_body:
        ok("preparePrintHeaders() called after profile save")
    else:
        warn("preparePrintHeaders() after profile save", "Changing patient name doesn't update print headers until restart")

    # Check the IDs it writes to actually exist
    prep_body = fn_body('preparePrintHeaders')
    if prep_body:
        written_ids = re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", prep_body)
        for wid in written_ids:
            if f'id="{wid}"' in html:
                ok(f"preparePrintHeaders writes to existing element #{wid}")
            else:
                fail(f"preparePrintHeaders targets #{wid}", f"Element id='{wid}' not found in DOM — print header silently blank")
else:
    warn("preparePrintHeaders", "Function not found — print headers may not be populated")


# ════════════════════════════════════════
#  LAYER 17 — CSS PAGE VISIBILITY
#  Pages default to display:none. Only the active page shows.
#  No page div should have an inline display:block that
#  bypasses the active class toggle.
# ════════════════════════════════════════

# Check .page default is display:none
if re.search(r'\.page\s*\{[^}]*display\s*:\s*none', html):
    ok(".page default is display:none")
else:
    fail(".page default", "Pages not hidden by default — multiple pages may show simultaneously")

# Check .page.active is display:block
if re.search(r'\.page\.active\s*\{[^}]*display\s*:\s*block', html):
    ok(".page.active is display:block")
else:
    fail(".page.active", "Active page not shown — navigating shows blank screen")

# No page div should have inline style display:block (bypasses active class)
page_divs_inline = re.findall(r'<div[^>]*class="page"[^>]*style="[^"]*display\s*:\s*block[^"]*"', html)
if page_divs_inline:
    fail("Page div inline display:block", f"{len(page_divs_inline)} page div(s) hardcoded visible — shows alongside active page")
else:
    ok("No page divs have inline display:block")

# formatDate() used wherever dates shown to user (no raw ISO strings in innerHTML)
raw_iso_in_html = re.findall(r'innerHTML.*?\d{4}-\d{2}-\d{2}|innerText.*?\d{4}-\d{2}-\d{2}', html)
if raw_iso_in_html:
    warn("Raw ISO dates in UI", f"{len(raw_iso_in_html)} place(s) may show YYYY-MM-DD instead of formatted date")
else:
    ok("No raw ISO date strings detected in UI output")


# ════════════════════════════════════════
#  LAYER 18 — MOBILE LAYOUT INTEGRITY
#  Hard min-width values wider than a phone viewport (~390px) inside
#  scrollable containers cause overflow that bleeds off-screen.
#  Any element with a fixed min-width > 360px is a mobile layout risk.
# ════════════════════════════════════════

MOBILE_VIEWPORT = 390  # conservative phone width in px

# Find all min-width declarations in CSS (px values only)
min_width_decls = re.findall(r'([\w\-\.#]+[^{]*)\{[^}]*min-width\s*:\s*(\d+)px', html, re.DOTALL)
for selector, val in min_width_decls:
    px = int(val)
    selector = selector.strip().split('\n')[-1].strip()
    if px > MOBILE_VIEWPORT:
        fail(f"Mobile overflow risk: {selector} min-width:{px}px",
             f"Wider than mobile viewport ({MOBILE_VIEWPORT}px) — will overflow on phones")
    elif px > 300:
        # warn on anything that might be tight on narrow phones
        warn(f"Mobile layout check: {selector} min-width:{px}px",
             f"May be tight on narrow phones (viewport ~{MOBILE_VIEWPORT}px)")

# Also catch inline style min-width overrides in templates (style="...min-width:Xpx...")
# Exclude @media query conditions (min-width inside @media(...) is a breakpoint, not an element width)
html_no_media = re.sub(r'@media[^{]+\{', '', html)  # strip media query headers
inline_min = re.findall(r'style="[^"]*min-width\s*:\s*(\d+)px', html_no_media)
inline_wide = [int(v) for v in inline_min if int(v) > MOBILE_VIEWPORT]
if inline_wide:
    for w in inline_wide:
        fail(f"Inline style min-width:{w}px",
             f"Hard-coded inline width wider than mobile viewport — will overflow on phones")
else:
    ok(f"No inline style min-width values wider than {MOBILE_VIEWPORT}px")

# Check that chart containers have overflow-x:auto (so if they do scroll, it's intentional)
chart_containers = re.findall(r'\.chart-container\s*\{([^}]+)\}', html)
for block in chart_containers:
    if 'overflow-x' in block or 'overflow' in block:
        ok("chart-container has overflow-x set")
    else:
        fail("chart-container missing overflow-x",
             "Charts that exceed container width will bleed off-screen instead of scrolling")

# Check grid-2 collapses to single column on mobile
mobile_blocks = re.findall(r'@media[^{]*max-width[^{]*\{(.+?)(?=@media|\Z)', html, re.DOTALL)
grid2_collapses = any('grid-2' in b and '1fr' in b for b in mobile_blocks)
if grid2_collapses:
    ok("grid-2 collapses to single column on mobile")
else:
    fail("grid-2 mobile breakpoint missing",
         "Two-column grid stays two columns on phones — content too narrow to read")


# ════════════════════════════════════════
#  LAYER 19 — CHART DOM INTEGRITY
#  renderBarChart() must write bars directly into the .chart-bars element,
#  not wrap them in a second .chart-bars div (causes nested containers,
#  broken layout, labels clipped inside fixed-height area).
#  Labels must live in a sibling .chart-labels div OUTSIDE .chart-bars.
# ════════════════════════════════════════

# Check renderBarChart doesn't create nested .chart-bars
render_bar_fn = fn_body('renderBarChart')
if render_bar_fn:
    # Bad pattern: innerHTML includes a new chart-bars wrapper
    if 'chart-bars' in render_bar_fn:
        fail("renderBarChart nests chart-bars div",
             "innerHTML contains a new .chart-bars wrapper inside the existing one — double container breaks layout")
    else:
        ok("renderBarChart writes bars directly into container, no nested chart-bars")

    # Labels must be in a separate element outside the bar container
    if 'chart-labels' in render_bar_fn and ('after(' in render_bar_fn or 'insertAdjacentHTML' in render_bar_fn or 'appendChild' in render_bar_fn):
        ok("renderBarChart places labels in sibling element outside bar container")
    elif 'chart-labels' in render_bar_fn:
        warn("renderBarChart label placement unclear",
             "Verify labels are outside fixed-height .chart-bars container or they will be clipped")
    else:
        warn("renderBarChart has no label row", "Date labels may be missing from charts")
else:
    # If renderBarChart doesn't exist, check each chart render directly
    for chart_id in ['chart-mood', 'chart-pain', 'chart-stress']:
        # Verify the chart element IDs exist in HTML
        if f'id="{chart_id}"' in html:
            ok(f"#{chart_id} element exists in DOM")
        else:
            fail(f"#{chart_id} missing", "Chart container not found — chart will silently fail to render")

# Check chart-bars has padding-top to give room for values above bars
chart_bars_css = re.search(r'\.chart-bars\s*\{([^}]+)\}', html)
if chart_bars_css:
    block = chart_bars_css.group(1)
    if 'padding-top' in block or 'padding:' in block:
        ok("chart-bars has padding-top — room for values above tallest bar")
    else:
        warn("chart-bars missing padding-top",
             "Values/emojis above bars may be clipped by the container top edge")
    if 'align-items: flex-end' in block or 'align-items:flex-end' in block:
        ok("chart-bars uses align-items:flex-end — bars grow from baseline up")
    else:
        warn("chart-bars align-items not flex-end", "Bars may not align to baseline correctly")

# Chart labels show weekday name (Mon/Tue) not raw date — readable on narrow phone screens
if find(r"weekday.*short|short.*weekday"):
    ok("Chart labels use weekday short name (Mon/Tue) — readable on narrow phone screens")
else:
    warn("Chart date labels", "Labels may show MM-DD format — truncates on phone screens")


# ════════════════════════════════════════
#  LAYER 20 — MISSING COVERAGE GAPS
#  Checks identified from real bugs found in production:
#  confirm() on all deletes, PRN division-by-zero, scroll targets,
#  toast calls, todayKey format, nav highlight index, refill guard.
# ════════════════════════════════════════

# 20a — confirm() on ALL destructive deletes (not just 4)
for fn in ['deleteMedication', 'deleteAppointment']:
    block = find(rf'function {fn}.*?^}}', re.DOTALL | re.MULTILINE)
    if block and 'confirm(' in block.group(0):
        ok(f"{fn}() has confirm() before delete")
    else:
        warn(f"{fn}() missing confirm()", "Accidental deletes with no undo")

# 20b — PRN division-by-zero guard in pill/refill math
# freqToDoseCount must have a default return of 1 (not 0) so Math.floor(pills/doses) never divides by zero
freq_body = fn_body('freqToDoseCount')
if freq_body:
    # Extract the final return value (default case, after all .includes() branches)
    default_returns = re.findall(r'return\s+(\d+)\s*;', freq_body)
    if default_returns and default_returns[-1] == '1':
        ok("freqToDoseCount default return is 1 — no divide-by-zero in daysLeft")
    else:
        fail("freqToDoseCount default return", f"Default return is '{default_returns[-1] if default_returns else 'missing'}' — should be 1 to prevent divide-by-zero")
else:
    warn("freqToDoseCount not found", "Cannot verify divide-by-zero protection")

# 20c — goToMedication uses getElementById (scroll target must be rendered first)
gotoMed = fn_body('goToMedication')
if gotoMed:
    if 'getElementById' in gotoMed and 'scrollIntoView' in gotoMed:
        ok("goToMedication() uses getElementById + scrollIntoView (unambiguous scroll target)")
    else:
        fail("goToMedication()", "Must use getElementById for scroll target, not querySelector")

# 20d — navigateToAppointment uses getElementById
gotoAppt = fn_body('navigateToAppointment')
if gotoAppt:
    if 'getElementById' in gotoAppt and 'scrollIntoView' in gotoAppt:
        ok("navigateToAppointment() uses getElementById + scrollIntoView")
    else:
        fail("navigateToAppointment()", "Must use getElementById for scroll target")

# 20e — showToast() called after key mutations (save and delete)
toast_calls = count(r'showToast\(')
if toast_calls >= 6:
    ok(f"showToast() called after mutations ({toast_calls} call sites)")
else:
    warn(f"showToast() only {toast_calls} call sites", "Users may not get feedback after save/delete — aim for ≥6")

# 20f — todayKey format is stable (date-only string, not datetime)
# getTodayKey() should return a date-only key (not datetime) so checks survive page reloads
getTodayKey_body = fn_body('getTodayKey')
if getTodayKey_body:
    if re.search(r"split\(['\"]T['\"]\)\[0\]|toLocaleDateString|slice\(0,\s*10\)", getTodayKey_body):
        ok("getTodayKey() returns date-only string — med checks stable across midnight")
    else:
        warn("getTodayKey() format unclear", "Key may include time component — checks could reset mid-day")
else:
    warn("getTodayKey() not found", "Cannot verify med check key format is date-only")

# 20g — navigate() uses el parameter for highlight (not fragile index lookup)
# Best pattern: navigate(page, el) → el.classList.add('active')
# This is immune to index mis-counts (the [2] vs [3] bug).
nav_fn_body = fn_body('navigate')
if nav_fn_body:
    # Check it removes active from all nav items first
    if re.search(r"querySelectorAll.*nav-item.*forEach.*remove.*active|forEach.*classList\.remove.*active", nav_fn_body):
        ok("navigate() clears all nav-item active classes before setting new one")
    else:
        warn("navigate() active-clear", "May not clear previous active nav item before highlighting new one")
    # Check it adds active via the passed element, not a hardcoded index
    if re.search(r"\bel\b.*classList.*add.*active|classList.*add.*active.*\bel\b", nav_fn_body):
        ok("navigate() highlights active nav via passed 'el' parameter — immune to index bugs")
    elif re.search(r"navItems\s*\[\s*\d+\s*\].*active", nav_fn_body):
        warn("navigate() uses hardcoded navItems[N] index", "Index must match DOM order exactly — easy to break (the [2] vs [3] bug)")
    else:
        warn("navigate() active highlight method unclear", "Verify correct nav item is highlighted on each page transition")
else:
    warn("navigate() body not found", "Cannot verify nav highlight logic")

# 20h — refill threshold guard (daysLeft threshold defined, not hardcoded 0)
if find(r'daysLeft\s*[<>]=?\s*\d+|refillThreshold|LOW_SUPPLY|days.*<.*\d'):
    ok("Refill alert has threshold comparison (not just == 0)")
else:
    warn("Refill threshold", "Could not confirm daysLeft threshold — may only alert at exactly 0 days")

# 20i — deleteLog has confirm() guard (function is named deleteLog, not deleteLogEntry)
block = find(r'function deleteLog\b.*?^}', re.DOTALL | re.MULTILINE)
if block and 'confirm(' in block.group(0):
    ok("deleteLog() has confirm() before delete")
else:
    warn("deleteLog() missing confirm()", "Log entries can be deleted with no undo dialog")


# 20j — recurring appointment end-date validation: must alert if recurEnd missing, must use >= not >
add_appt_body = fn_body('addAppointment') or ''
if re.search(r'isRecurring.*!recurEnd.*alert|!recurEnd.*alert', add_appt_body):
    ok("addAppointment() alerts user if 'Repeat until' date is missing")
else:
    fail("addAppointment() missing recurEnd validation", "Silently creates single appt when recurring checkbox is checked but end date is empty")

if re.search(r'recurEnd\s*>=\s*date', add_appt_body):
    ok("addAppointment() uses recurEnd >= date (inclusive — same-day end date creates at least 1 occurrence)")
elif re.search(r'recurEnd\s*>\s*date', add_appt_body):
    fail("addAppointment() uses recurEnd > date (strict)", "End date equal to start date creates zero occurrences — user sees only 1 appointment")
else:
    warn("addAppointment() recurEnd comparison unclear", "Verify recurrence guard includes same-day end date")



# ════════════════════════════════════════
#  LAYER 21 — UNTESTED FUNCTION COVERAGE
#  Real bugs can hide in functions QA never looked at.
#  These checks verify the critical logic in every
#  module that was previously uncovered.
# ════════════════════════════════════════

# 21a — clearAllData() has double-confirm guard (most destructive action in app)
clear_body = fn_body('clearAllData') or ''
confirm_count = len(re.findall(r'confirm\(', clear_body))
if confirm_count >= 2:
    ok(f"clearAllData() has {confirm_count} confirm() guards — double confirmation before wipe")
elif confirm_count == 1:
    warn("clearAllData() only 1 confirm()", "Most destructive action should require double-confirmation")
else:
    fail("clearAllData() missing confirm()", "All data can be wiped with no confirmation")

# 21b — delete functions in all modules have confirm() guard
for fn in ['deleteContact', 'deleteHandoff', 'deleteMemory', 'deleteStress']:
    block = fn_body(fn) or ''
    if 'confirm(' in block:
        ok(f"{fn}() has confirm() before delete")
    else:
        fail(f"{fn}() missing confirm()", "Record deleted with no undo dialog")

# 21c — required-field validation in all add functions
for fn, field in [('addContact', 'name'), ('addHandoff', 'date'), ('addMemory', 'title'), ('addStressEntry', 'selectedStress')]:
    block = fn_body(fn) or ''
    if 'alert(' in block and 'return' in block:
        ok(f"{fn}() has required-field validation")
    else:
        fail(f"{fn}() missing required-field validation", f"Can save empty {field} record")

# 21d — toggleMedCheck() saves to localStorage using todayKey
toggle_body = fn_body('toggleMedCheck') or ''
if 'localStorage.setItem' in toggle_body and 'todayKey' in toggle_body:
    ok("toggleMedCheck() saves check state to localStorage keyed by today")
else:
    fail("toggleMedCheck() save", "Med check state may not persist after page reload")

if 'pills' in toggle_body and ('pills - 1' in toggle_body or 'pills + ' in toggle_body or '+= ' in toggle_body or '-= ' in toggle_body or 'isDone ? -1 : 1' in toggle_body):
    ok("toggleMedCheck() adjusts pill count on check/uncheck")
else:
    warn("toggleMedCheck() pill deduction", "Checking off a dose may not reduce pill count")

# 21e — logPRNDose() increments count (not sets to true) and deducts pills
prn_body = fn_body('logPRNDose') or ''
if re.search(r'\|\|\s*0\)\s*\+\s*1|checks\[key\]\s*\+\s*1|\+= 1', prn_body):
    ok("logPRNDose() increments PRN count (not boolean) — multiple doses tracked correctly")
else:
    fail("logPRNDose() increment", "PRN may use boolean true instead of count — can't track 2nd/3rd dose today")

if 'pills' in prn_body and ('pills - 1' in prn_body or 'med.pills - 1' in prn_body):
    ok("logPRNDose() deducts 1 pill per dose")
else:
    warn("logPRNDose() pill deduction", "PRN dose may not reduce pill count")

# 21f — generateRecurringDates() caps at max, uses correct day increments
recur_body = fn_body('generateRecurringDates') or ''
if re.search(r'max\s*=\s*\d+|\.length\s*<\s*\d+', recur_body):
    ok("generateRecurringDates() has max occurrence cap — prevents runaway loops")
else:
    fail("generateRecurringDates() no cap", "Could generate hundreds of appointments if end date is far out")

for freq, pattern in [('weekly', r'getDate\(\)\s*\+\s*7'), ('biweekly', r'getDate\(\)\s*\+\s*14'), ('monthly', r'getMonth\(\)\s*\+\s*1')]:
    if re.search(pattern, recur_body):
        ok(f"generateRecurringDates() {freq} uses correct increment")
    else:
        warn(f"generateRecurringDates() {freq} increment unclear", f"Verify {freq} adds correct days/months")

# 21g — markAttended/unmarkAttended both save and re-render
for fn, flag in [('markAttended', 'true'), ('unmarkAttended', 'false')]:
    block = fn_body(fn) or ''
    if f'attended: {flag}' in block and 'save(' in block and 'renderAppointments' in block:
        ok(f"{fn}() sets attended={flag}, saves, and re-renders")
    else:
        fail(f"{fn}()", f"May not correctly set attended={flag}, save, or re-render")

# 21h — sortAppointments() sorts ascending by date (a before b, not b before a)
sort_body = fn_body('sortAppointments') or ''
if re.search(r'a\.date.*localeCompare.*b\.date|a\.date\s*[<>]\s*b\.date', sort_body):
    ok("sortAppointments() sorts ascending by date (a.date vs b.date — earliest first)")
else:
    warn("sortAppointments() sort direction unclear", "Descending order would show past appointments first")

# 21i — updatePillDaysLeft() uses freqToDoseCount (not hardcoded divisor)
pill_body = fn_body('updatePillDaysLeft') or ''
if 'freqToDoseCount' in pill_body:
    ok("updatePillDaysLeft() calls freqToDoseCount() — correct doses-per-day for all frequencies")
else:
    fail("updatePillDaysLeft()", "May use hardcoded divisor — wrong days-left for weekly/biweekly meds")

# 21j — reimportFromProfile() populates name, dob, and conditions fields
reimport_body = fn_body('reimportFromProfile') or ''
for field in ['ec-name', 'ec-dob', 'ec-conditions']:
    if field in reimport_body:
        ok(f"reimportFromProfile() populates #{field}")
    else:
        fail(f"reimportFromProfile() missing #{field}", "Emergency card field not synced from profile")

# 21k — timeStrTo24() handles am/pm and midnight/noon edge cases
time_body = fn_body('timeStrTo24') or ''
if re.search(r"h\s*===?\s*12.*h\s*=\s*0|am.*h\s*=\s*0", time_body):
    ok("timeStrTo24() handles 12am → 00:00 edge case (midnight)")
else:
    warn("timeStrTo24() 12am edge case", "12:00am may convert to 12:00 instead of 00:00")

if re.search(r"pm.*h\s*!==?\s*12.*h\s*\+=\s*12|pm.*h\s*\+\s*12", time_body):
    ok("timeStrTo24() handles pm hours correctly (adds 12, skips 12pm)")
else:
    warn("timeStrTo24() pm conversion", "pm hours may not convert correctly")



# ════════════════════════════════════════
#  LAYER 22 — DEEPER CORRECTNESS CHECKS
#  Data integrity, state leaks, offline,
#  and edge cases found by code review.
# ════════════════════════════════════════

# 22a — exportData() iterates Object.values(KEYS) — all keys exported automatically
export_body = fn_body('exportData') or ''
if re.search(r'Object\.values\(KEYS\).*forEach|Object\.values\(KEYS\).*map', export_body, re.DOTALL):
    ok("exportData() uses Object.values(KEYS) — all storage keys exported automatically")
else:
    fail("exportData() key coverage", "May hard-code keys — new keys added to KEYS won't be exported unless manually added")

# 22b — importData() iterates Object.values(KEYS) — all keys restored automatically
import_body = fn_body('importData') or ''
if re.search(r'Object\.values\(KEYS\).*forEach|Object\.values\(KEYS\).*map', import_body, re.DOTALL):
    ok("importData() uses Object.values(KEYS) — all storage keys restored automatically")
else:
    fail("importData() key coverage", "May hard-code keys — new keys added to KEYS won't be restored on import")

# 22c — importData() validates backup file before restoring (_version + _app check)
if re.search(r'_version.*_app|_app.*_version', import_body):
    ok("importData() validates _version and _app before restoring — rejects foreign files")
else:
    fail("importData() validation", "May restore data from wrong app's backup file")

# 22d — medication edit preserves original id (map by id, not push)
edit_med_body = fn_body('addMedication') or ''
if re.search(r'editingMedId.*map|map.*editingMedId', edit_med_body, re.DOTALL):
    ok("addMedication() edit path uses .map() by id — preserves original med id")
else:
    fail("addMedication() edit", "May replace med with new id — orphans med check history (todayKey entries)")

# 22e — appointment date format: today key uses same YYYY-MM-DD format as stored dates
dashboard_body = fn_body('renderDashboard') or ''
if re.search(r"toISOString\(\)\.split\(['\"]T['\"]\)\[0\]|new Date\(\)\.toISOString\(\)\.split", dashboard_body):
    ok("renderDashboard() today uses toISOString().split('T')[0] — matches stored date format")
else:
    warn("renderDashboard() today format", "Verify today key matches stored appointment date format (YYYY-MM-DD)")

# 22f — navigate() calls clearMedForm() when switching to medications page
#        prevents stale editingMedId if user navigates away mid-edit
navigate_body = fn_body('navigate') or ''
if 'clearMedForm' in navigate_body:
    ok("navigate() calls clearMedForm() on medications page — clears stale edit state on navigation")
else:
    warn("navigate() med edit state", "Navigating away mid-edit may leave editingMedId set — next save overwrites wrong record")

# 22g — clearAllData() re-shows disclaimer overlay after wipe
clear_body = fn_body('clearAllData') or ''
if 'disclaimer-overlay' in clear_body and ('display' in clear_body or 'style' in clear_body):
    ok("clearAllData() re-shows disclaimer overlay — fresh start flow works after wipe")
else:
    fail("clearAllData() disclaimer reset", "After wipe, disclaimer not re-shown — app looks broken on next open")

# 22h — addLogEntry() mood is optional (no alert guard on selectedMood)
log_body = fn_body('addLogEntry') or ''
if re.search(r'!selectedMood.*alert|alert.*!selectedMood', log_body):
    fail("addLogEntry() blocks save if no mood", "Mood should be optional — caregivers may not know patient's mood")
else:
    ok("addLogEntry() mood is optional — log can be saved without mood selection")

# 22i — formatDate() handles empty/null gracefully (returns '—' not crash)
fmt_date_body = fn_body('formatDate') or ''
if re.search(r'if\s*\(!d\)|if\s*\(!d\s*\)', fmt_date_body):
    ok("formatDate() guards against empty/null — returns '—' instead of crashing")
else:
    fail("formatDate()", "No empty guard — formatDate('') or formatDate(null) may crash")

# 22j — formatTime() handles empty/null gracefully (returns '' not crash)
fmt_time_body = fn_body('formatTime') or ''
if re.search(r'if\s*\(!t\)|if\s*\(!t\s*\)', fmt_time_body):
    ok("formatTime() guards against empty/null — returns '' instead of crashing")
else:
    fail("formatTime()", "No empty guard — formatTime('') or formatTime(null) may crash")

# 22k — burnout alert threshold is <= 4 (not == 4 or < 4)
stress_render = fn_body('renderStress') or ''
if re.search(r'avg\s*<=\s*4|avg\s*<\s*5', stress_render):
    ok("renderStress() burnout alert fires at avg ≤ 4 — correct low-wellbeing threshold")
else:
    warn("Burnout alert threshold", "Cannot confirm burnout fires at avg ≤ 4 — may miss at-risk caregivers")

# 22l — SW cache includes the root HTML path
sw_content = ''
import os
html_dir = os.path.dirname(os.path.abspath(sys.argv[1]))
sw_candidates = [
    os.path.join(html_dir, 'sw.js'),
    os.path.join(html_dir, '..', 'gitpush', 'sw.js'),
    os.path.join(html_dir, '..', '..', 'gitpush', 'sw.js'),
    '/sessions/elegant-cool-bardeen/gitpush/sw.js',
]
for path in sw_candidates:
    if os.path.exists(path):
        with open(path) as f:
            sw_content = f.read()
        break

if sw_content:
    if re.search(r"['\"/]CareCompanion/?['\"]|['\"/]index\.html['\"]|['\"]\/['\"]", sw_content):
        ok("SW cache includes root HTML path — app works offline")
    else:
        fail("SW cache missing root HTML", "Offline visit shows blank page — HTML not cached")
else:
    warn("sw.js not found beside HTML", "Cannot verify SW caches root HTML for offline use")

# 22m — no external CDN resource loads (app must work fully offline)
cdn_refs = re.findall(r'(https?://(?!fonts\.googleapis\.com)[^\s"\'<>]+\.(js|css|woff2?))', html)
if not cdn_refs:
    ok("No external CDN JS/CSS dependencies — app works fully offline")
else:
    fail("External CDN dependencies found", f"{[r[0] for r in cdn_refs[:3]]} — these fail offline")

# 22n — renderAll() calls every render function
render_all_body = fn_body('renderAll') or ''
for fn in ['renderMedications', 'renderSymptomLog', 'renderAppointments',
           'renderCareTeam', 'renderHandoff', 'renderMemories', 'renderStress',
           'renderDashboard', 'renderCharts', 'renderRefillAlerts']:
    if fn in render_all_body:
        ok(f"renderAll() calls {fn}()")
    else:
        fail(f"renderAll() missing {fn}()", "Module won't initialize on app load or after import restore")

# 22o — PRN label shows count not boolean (checks[key] not checks[key] === true)
prn_body = fn_body('logPRNDose') or ''
if re.search(r'checks\[key\][^=]|Given.*checks\[key\]', prn_body):
    ok("logPRNDose() displays count value — '3× today' not just 'Given'")
else:
    warn("logPRNDose() label", "PRN count display may show wrong value")



# ════════════════════════════════════════
#  LAYER 23 — SECURITY, NUMERIC SAFETY,
#  AND RENDER COMPLETENESS
#  Found by auditing innerHTML injection,
#  NaN paths, and unchecked render calls.
# ════════════════════════════════════════

# 23a — XSS: user data injected into innerHTML must not include raw script tags
# Check that no render function inserts user data directly without at least
# a text-only context (href/onclick with id numbers is fine; free-text fields are risk)
# Strategy: flag any template literal that embeds a free-text field directly into innerHTML
xss_risk_fields = ['a\\.title', 'a\\.doctor', 'a\\.address', 'a\\.notes', 'a\\.visitNotes',
                   'm\\.name', 'm\\.dose', 'm\\.notes', 'c\\.name', 'c\\.notes',
                   'n\\.meds', 'n\\.meals', 'n\\.notes', 'n\\.watch',
                   'mem\\.title', 'mem\\.text', 'e\\.notes', 'e\\.gratitude']
# Check that free-text fields use esc() wrapper, not raw injection
xss_hits = []
for field in xss_risk_fields:
    raw = re.search(rf'\$\{{{field}\}}', html)          # ${field} without esc
    escaped = re.search(rf'\$\{{esc\({field}\)\}}', html)  # ${esc(field)} present
    if raw and not escaped:
        xss_hits.append(field.replace('\\.', '.'))
if xss_hits:
    fail("XSS — raw user text in innerHTML", f"Fields not wrapped in esc(): {xss_hits[:5]}")
elif find(r'function esc\('):
    ok("esc() sanitizer defined and applied to free-text innerHTML injections — XSS protected")
else:
    warn("XSS", "No esc() sanitizer found — user text injected raw into innerHTML")

# 23b — pillsMax correctly updated on edit (higher of new vs existing)
add_med_body = fn_body('addMedication') or ''
if re.search(r'Math\.max.*pills.*pillsMax|pillsMax.*Math\.max', add_med_body):
    ok("addMedication() sets pillsMax = Math.max(newPills, existingPillsMax) — refill tracking correct")
else:
    warn("pillsMax update logic", "May overwrite pillsMax with lower value — days-left calculation becomes wrong after partial edit")

# 23c — med check old key cleanup: getMedChecksForToday() prunes stale keys
get_checks_body = fn_body('getMedChecksForToday') or ''
if re.search(r'startsWith.*cc_medchecks_|cc_medchecks_.*startsWith', get_checks_body) and 'removeItem' in get_checks_body:
    ok("getMedChecksForToday() prunes old cc_medchecks_* keys — localStorage doesn't grow unbounded")
else:
    fail("getMedChecksForToday() no key cleanup", "Old daily check keys accumulate in localStorage forever")

# 23d — KEYS.medChecks ('cc_medchecks') is a static key but actual keys are dynamic
# Export/import iterates KEYS — but the actual checks use cc_medchecks_YYYY-MM-DD
# Today's med checks are NOT exported. This is intentional (daily reset) — verify it's documented
if re.search(r'cc_medchecks_.*toISOString|getTodayKey.*cc_medchecks', html):
    ok("Med checks use dynamic date key (cc_medchecks_YYYY-MM-DD) — correctly resets daily, not exported")
else:
    warn("Med check key pattern unclear", "Cannot confirm daily med checks use date-stamped key")

# 23e — refill alert uses correct thresholds: <= 0 is overdue, 1-7 is soon
refill_body = fn_body('renderRefillAlerts') or ''
if re.search(r'daysLeft\s*<=\s*0', refill_body):
    ok("renderRefillAlerts() overdue threshold is daysLeft <= 0")
else:
    fail("renderRefillAlerts() overdue threshold", "Overdue condition not found — may never show 'out of pills' alert")

if re.search(r'daysLeft\s*<=\s*7', refill_body):
    ok("renderRefillAlerts() soon threshold is daysLeft <= 7")
else:
    fail("renderRefillAlerts() soon threshold", "7-day warning threshold not found")

if re.search(r'Refill overdue|overdue', refill_body, re.IGNORECASE):
    ok("renderRefillAlerts() shows 'Refill overdue' label for critical meds")
else:
    warn("renderRefillAlerts() overdue label", "No overdue label found in refill alerts")

# 23f — markAttended() auto-opens edit form and focuses visit notes
mark_body = fn_body('markAttended') or ''
if 'editAppointment' in mark_body:
    ok("markAttended() calls editAppointment() — edit form opens automatically after marking attended")
else:
    fail("markAttended() edit form", "Does not open edit form after marking attended — user can't add visit notes easily")

if 'appt-visit-notes-row' in mark_body and 'display' in mark_body:
    ok("markAttended() shows visit notes row after marking attended")
else:
    warn("markAttended() visit notes row", "Visit notes field may not be visible after marking attended")

if re.search(r'appt-visit-notes.*focus\(\)|focus\(\).*appt-visit-notes', mark_body):
    ok("markAttended() focuses visit notes input — keyboard opens immediately")
else:
    warn("markAttended() focus", "Visit notes field not focused — user must tap manually to type")

# 23g — parseInt NaN guard in updatePillDaysLeft
pill_days_body = fn_body('updatePillDaysLeft') or ''
if re.search(r'isNaN|!pills\b|pills\s*<=\s*0|if\s*\(!pills', pill_days_body):
    ok("updatePillDaysLeft() guards against NaN/empty pill input")
else:
    fail("updatePillDaysLeft() NaN guard", "parseInt('') = NaN — label shows '~NaN days supply' when pill field is blank")

# 23h — formatTime() midnight edge case: hour=0 should show 12:xx AM not 0:xx AM
fmt_time_body = fn_body('formatTime') or ''
if re.search(r'hour\s*\|\|\s*12|hour\s*===?\s*0.*12|!\s*hour.*12', fmt_time_body):
    ok("formatTime() handles midnight (hour=0) → shows 12:xx AM correctly")
else:
    warn("formatTime() midnight edge case", "00:xx may display as 0:xx AM instead of 12:xx AM")

# 23i — renderGettingStarted() is called from renderDashboard (shows on load)
dash_body = fn_body('renderDashboard') or ''
if 'renderGettingStarted' in dash_body:
    ok("renderDashboard() calls renderGettingStarted() — checklist visible on first load")
else:
    fail("renderDashboard() missing renderGettingStarted()", "Getting started checklist never renders on dashboard load")

# 23j — renderGoodDaysWidget() is called from renderDashboard (separate from renderGoodDays)
if 'renderGoodDaysWidget' in dash_body:
    ok("renderDashboard() calls renderGoodDaysWidget() — good days widget updates on dashboard")
else:
    fail("renderDashboard() missing renderGoodDaysWidget()", "Good days widget on dashboard never updates")

# 23k — navigate() closes sidebar on mobile after navigation
nav_body = fn_body('navigate') or ''
if re.search(r'closeSidebar|innerWidth.*768|768.*innerWidth', nav_body):
    ok("navigate() closes sidebar on mobile — sidebar doesn't stay open after navigation")
else:
    warn("navigate() sidebar", "Sidebar may remain open after navigation on mobile")

# 23l — KEYS.medChecks static key exists but dynamic keys are used correctly
# The static KEYS.medChecks is in KEYS but actual storage uses getTodayKey()
# Verify KEYS.medChecks is not used anywhere for actual check storage (would break daily reset)
medchecks_uses = re.findall(r'KEYS\.medChecks', html)
if len(medchecks_uses) <= 1:  # only the definition
    ok("KEYS.medChecks static key not used for check storage — daily reset works correctly")
else:
    warn(f"KEYS.medChecks used {len(medchecks_uses)} times", "Verify static key not used alongside dynamic date key — could confuse export/import")


# ════════════════════════════════════════
#  LAYER 24 — LAYOUT, DATA INTEGRITY,
#  EDGE CASES, EMPTY STATES
# ════════════════════════════════════════

# 24a — address text span has flex:1;min-width:0 (fix for mobile wrapping)
if find(r'flex:1;min-width:0;word-break:break-word;overflow-wrap:anywhere.*esc\(a\.address\)'):
    ok("Address span has flex:1;min-width:0 — wraps beside emoji on mobile")
else:
    fail("Address span missing flex:1;min-width:0", "Address text drops below emoji on narrow phones")

# 24b — doctor span has flex:1;min-width:0 (same fix for consistency)
if find(r'flex:1;min-width:0;word-break:break-word;overflow-wrap:anywhere.*esc\(a\.doctor\)'):
    ok("Doctor span has flex:1;min-width:0 — wraps beside emoji on mobile")
else:
    fail("Doctor span missing flex:1;min-width:0", "Doctor name drops below emoji on narrow phones")

# 24c — visit prep print: page-visit-prep element exists
if find(r'id=["\']page-visit-prep["\']'):
    ok("page-visit-prep element present — print target exists")
else:
    fail("page-visit-prep missing", "Doctor Visit Prep print will fail — no target element")

# 24d — visit prep print: data-print="visit" triggers correct CSS
if find(r'data-print=["\']visit["\']') and find(r'data-print="visit".*page-visit-prep|body\[data-print="visit"\].*page-visit-prep', re.DOTALL):
    ok("data-print='visit' wires up to page-visit-prep CSS — print layout correct")
else:
    fail("data-print='visit' not linked to page-visit-prep CSS", "Visit prep print layout broken")

# 24e — exportData() uses Object.values(KEYS) — exports all sections dynamically
export_body = fn_body('exportData')
if 'Object.values(KEYS)' in export_body and 'forEach' in export_body:
    ok("exportData() iterates Object.values(KEYS) — all data sections included automatically")
else:
    fail("exportData() may not export all sections", "Hardcoded keys miss new sections; use Object.values(KEYS)")

# 24f — exportData() includes _app field for import validation
if '_app' in export_body and 'CareCompanion' in export_body:
    ok("exportData() sets _app:'CareCompanion' — import validation works")
else:
    fail("exportData() missing _app field", "importData() will reject backup as invalid")

# 24g — importData() validates _app === 'CareCompanion' before restoring
import_body = fn_body('importData')
if "_app !== 'CareCompanion'" in import_body or '_app.*CareCompanion' in import_body:
    ok("importData() checks _app field — foreign JSON files rejected")
else:
    fail("importData() missing _app validation", "Any JSON file with _version key will wipe user data")

# 24h — importData() requires confirm() before overwriting data
if 'confirm(' in import_body:
    ok("importData() requires confirm() before restoring — accidental overwrites prevented")
else:
    fail("importData() missing confirm()", "Single mis-click imports file and wipes all current data")

# 24i — importData() restores via Object.values(KEYS) — no hardcoded key list
if 'Object.values(KEYS)' in import_body:
    ok("importData() restores via Object.values(KEYS) — all keys covered")
else:
    warn("importData() key restore", "Hardcoded key list may miss new data sections on import")

# 24j — renderHandoff() renders handoff-list element
handoff_body = fn_body('renderHandoff')
if 'handoff-list' in handoff_body:
    ok("renderHandoff() targets handoff-list element — render target correct")
else:
    fail("renderHandoff() missing handoff-list target", "Handoff notes never render on screen")

# 24k — renderHandoff() shows empty state when no notes
if 'empty-state' in handoff_body and 'No handoff' in handoff_body:
    ok("renderHandoff() shows empty state — no blank screen on first load")
else:
    warn("renderHandoff() empty state", "Blank screen shown when no handoff notes exist")

# 24l — renderHandoff() uses esc() on caregiver name field (XSS in handoff)
if "esc(n.caregiver)" in handoff_body or "esc(n.meds)" in handoff_body:
    ok("renderHandoff() uses esc() on user-entered text — XSS prevented in handoff notes")
else:
    fail("renderHandoff() missing esc()", "Caregiver-entered text injected raw into innerHTML — XSS risk")

# 24m — appointments sorted chronologically (date then time)
if find(r'\.sort\s*\(\s*\(a,\s*b\)\s*=>\s*\{[^}]*date.*localeCompare[^}]*time.*localeCompare', re.DOTALL):
    ok("Appointments sorted by date then time — chronological order correct")
else:
    warn("Appointment sort", "Appointments may not sort by date+time — check sort comparator")

# 24n — saveAppointment() validates blank title and date before saving
save_appt_area = ''
m = re.search(r'const title = document\.getElementById\(["\']appt-title["\'].*?(?=function )', html, re.DOTALL)
if m: save_appt_area = m.group(0)
if "!title || !date" in save_appt_area or "!title" in save_appt_area and "!date" in save_appt_area:
    ok("saveAppointment() validates blank title and date — empty appointments blocked")
else:
    fail("saveAppointment() missing blank date/title validation", "Undated appointments corrupt sort order and render blank cards")

# 24o — logPRNDose() deducts pill count and floors at 0
prn_body = fn_body('logPRNDose')
if 'Math.max(0' in prn_body and 'pills - 1' in prn_body:
    ok("logPRNDose() deducts pill and floors at 0 — no negative pill counts")
else:
    fail("logPRNDose() pill deduction missing Math.max(0)", "Pill count can go negative — refill alerts break")

# 24p — logPRNDose() updates inline label with dose count
if 'Given' in prn_body and 'today' in prn_body:
    ok("logPRNDose() updates inline 'Given N× today' label — UI reflects current dose count")
else:
    warn("logPRNDose() inline label", "Dose count not shown inline — caregiver cannot see how many given today")

# 24q — renderStress() shows empty state when no entries
stress_body = fn_body('renderStress')
if 'empty-state' in stress_body and "No check-in" in html:
    ok("renderStress() shows empty state — no blank panel on first load")
else:
    warn("renderStress() empty state", "No empty state — blank panel shown when no stress entries exist")

# 24r — renderStress() only checks burnout when entries >= 3 (no div-by-zero)
if 'entries.length >= 3' in stress_body or 'entries.length > 2' in stress_body:
    ok("renderStress() only calculates burnout when >= 3 entries — no NaN average")
else:
    fail("renderStress() burnout guard missing", "Average of empty array = NaN — burnout alert may show incorrectly")

# 24s — formatDate() handles YYYY-MM-DD string input (not Date object)
format_body = fn_body('formatDate')
if 'T12:00' in format_body:
    ok("formatDate() appends T12:00:00 — noon local time prevents UTC midnight off-by-one-day")
elif 'T00:00' in format_body or '+00:00' in format_body:
    ok("formatDate() handles timezone offset on date string")
else:
    warn("formatDate() timezone handling", "new Date('YYYY-MM-DD') parses as UTC midnight — may show previous day in negative-offset timezones")

# 24t — KEYS object defined (central key registry)
if find(r'const KEYS\s*=\s*\{') or find(r'var KEYS\s*=\s*\{'):
    ok("KEYS object defined — central localStorage key registry prevents typos")
else:
    fail("KEYS object missing", "localStorage keys scattered as magic strings — import/export will break")

# 24u — no raw localStorage.setItem outside of save() helper (except known exceptions)
raw_sets = re.findall(r'localStorage\.setItem\s*\(', html)
save_helper = re.findall(r'function save\s*\(', html)
if save_helper:
    ok(f"save() helper defined — localStorage writes centralized ({len(raw_sets)} total setItem calls)")
else:
    warn("save() helper missing", "Raw localStorage.setItem scattered — typos in keys cause silent data loss")

# 24v — appt-info on mobile has flex:1 and min-width:0 in CSS
if find(r'appt-info.*flex.*1.*min-width.*0|appt-info\s*\{[^}]*flex.*1', re.DOTALL):
    ok("appt-info has flex:1 and min-width:0 — info column shrinks correctly beside badge")
else:
    warn("appt-info flex", "appt-info may not shrink — content overflows on mobile")


# ════════════════════════════════════════
#  LAYER 25 — ONBOARDING, EMERGENCY CARD,
#  RECURRING LOGIC, DASHBOARD WIDGETS,
#  MED DOSE LOGIC
# ════════════════════════════════════════

# 25a — clearAllData() requires double confirm() before wiping
clear_body = fn_body('clearAllData')
confirm_count = clear_body.count('confirm(')
if confirm_count >= 2:
    ok("clearAllData() requires two confirm() dialogs — accidental full wipe prevented")
else:
    fail("clearAllData() missing double confirm()", f"Only {confirm_count} confirm() — one mis-click deletes all data permanently")

# 25b — clearAllData() calls localStorage.clear()
if 'localStorage.clear()' in clear_body:
    ok("clearAllData() calls localStorage.clear() — full wipe executed")
else:
    fail("clearAllData() missing localStorage.clear()", "Data not actually deleted on clear")

# 25c — clearAllData() re-shows disclaimer overlay after wipe
if 'disclaimer-overlay' in clear_body and 'display' in clear_body:
    ok("clearAllData() re-shows disclaimer overlay — fresh-start flow correct")
else:
    warn("clearAllData() disclaimer reset", "Disclaimer not shown after wipe — app may appear stale on re-open")

# 25d — acceptDisclaimer() saves KEYS.disclaimer = true
accept_body = fn_body('acceptDisclaimer')
if 'KEYS.disclaimer' in accept_body and ('true' in accept_body or 'save(' in accept_body):
    ok("acceptDisclaimer() saves KEYS.disclaimer=true — won't show again on reload")
else:
    fail("acceptDisclaimer() doesn't persist acceptance", "Disclaimer re-shown every time app loads")

# 25e — acceptDisclaimer() opens setup overlay when no profile exists
if 'setup-overlay' in accept_body and ('remove' in accept_body or 'display' in accept_body):
    ok("acceptDisclaimer() opens setup overlay when no profile — onboarding flow correct")
else:
    warn("acceptDisclaimer() setup flow", "Setup overlay not opened after disclaimer — new users land on blank app")

# 25f — saveSetup() syncs emergency card from profile when _saved !== true
setup_body = fn_body('saveSetup')
if '_saved' in setup_body and 'ec.' in setup_body:
    ok("saveSetup() syncs emergency card from profile when not manually saved — auto-populate works")
else:
    warn("saveSetup() emergency card sync", "Emergency card not pre-filled from profile — users must enter name/dob twice")

# 25g — saveEmergencyFields() sets _saved:true to lock auto-sync
ec_body = fn_body('saveEmergencyFields')
if '_saved' in ec_body and 'true' in ec_body:
    ok("saveEmergencyFields() sets _saved:true — prevents profile sync from overwriting manual edits")
else:
    fail("saveEmergencyFields() missing _saved:true", "Profile saves will overwrite manually edited emergency card data")

# 25h — freqToDoseCount() maps 'twice' → 2, 'three' → 3, 'every 8' → 3, 'every 6' → 4
freq_body = fn_body('freqToDoseCount')
if 'twice' in freq_body and 'return 2' in freq_body:
    ok("freqToDoseCount() maps 'twice' → 2 doses")
else:
    fail("freqToDoseCount() 'twice' mapping broken", "Twice-daily meds show only 1 dose checkbox")

if 'every 6' in freq_body and 'return 4' in freq_body:
    ok("freqToDoseCount() maps 'every 6' → 4 doses")
else:
    fail("freqToDoseCount() 'every 6h' mapping broken", "Every-6-hour meds show wrong dose count")

# 25i — getDoseCount() uses times field as source of truth when provided
dose_count_body = fn_body('getDoseCount')
if 'm.times' in dose_count_body and 'split' in dose_count_body:
    ok("getDoseCount() uses m.times as source of truth when provided — saved times override freq string")
else:
    warn("getDoseCount() times field", "Dose count derived from frequency string only — ignores saved times field")

# 25j — getDoseLabels() returns individual time strings when m.times set
dose_label_body = fn_body('getDoseLabels')
if 'm.times' in dose_label_body and 'split' in dose_label_body and 'parts' in dose_label_body:
    ok("getDoseLabels() returns time strings from m.times — checkboxes show actual times not 'Dose 1/2'")
else:
    warn("getDoseLabels() times display", "Dose checkboxes show generic 'Dose 1' instead of actual times")

# 25k — generateRecurringDates() caps at 52 max instances
recur_body = fn_body('generateRecurringDates')
if 'max' in recur_body and '52' in recur_body and 'dates.length < max' in recur_body:
    ok("generateRecurringDates() capped at 52 instances — no runaway infinite loops")
else:
    fail("generateRecurringDates() missing max cap", "Recurring appointments with distant end date could generate thousands of records")

# 25l — generateRecurringDates() uses T12:00:00 on date strings (timezone safe)
if 'T12:00:00' in recur_body:
    ok("generateRecurringDates() appends T12:00:00 — timezone-safe date math")
else:
    warn("generateRecurringDates() timezone", "Date math without T12:00:00 may skip or duplicate dates in negative-UTC timezones")

# 25m — generateRecurringDates() handles all four frequencies
for freq_val in ['daily', 'weekly', 'biweekly', 'monthly']:
    if freq_val in recur_body:
        ok(f"generateRecurringDates() handles '{freq_val}' frequency")
    else:
        fail(f"generateRecurringDates() missing '{freq_val}'", f"'{freq_val}' recurring appointments never generate instances")

# 25n — renderGoodDays() hides strip when no good-mood entries
good_body = fn_body('renderGoodDays')
if "strip.style.display = 'none'" in good_body or "display.*none" in good_body:
    ok("renderGoodDays() hides widget when no 😊 entries — no empty box on dashboard")
else:
    warn("renderGoodDays() empty state", "Good Days widget shows empty box when no happy entries exist")

# 25o — renderGoodDays() streak guard prevents infinite loop
if 'streak > 365' in good_body or 'streak >= 365' in good_body:
    ok("renderGoodDays() streak loop guarded at 365 — no infinite loop on long streaks")
else:
    fail("renderGoodDays() streak loop unguarded", "while(true) streak loop could hang browser if data is corrupt")

# 25p — renderMoodSnapshot() shows empty state when no logs
mood_body = fn_body('renderMoodSnapshot')
if 'empty-state' in mood_body or 'No log' in mood_body:
    ok("renderMoodSnapshot() shows empty state — no blank panel when no logs")
else:
    warn("renderMoodSnapshot() empty state", "Blank panel shown when no log entries exist")

# 25q — renderMedSearch() shows prompt when query is empty
med_search_body = fn_body('renderMedSearch')
if "!query" in med_search_body or "!query.trim()" in med_search_body:
    ok("renderMedSearch() shows prompt when query empty — no phantom search on load")
else:
    warn("renderMedSearch() empty query", "Empty query may run search and show 'no results' on load")

# 25r — renderMedSearch() searches name, dose, notes, frequency fields
for field in ['m.name', 'm.dose', 'm.notes', 'm.frequency']:
    if field in med_search_body:
        ok(f"renderMedSearch() searches {field} field")
    else:
        warn(f"renderMedSearch() missing {field}", f"Searching by {field} won't find results")

# 25s — prepareVisitPrep() uses T12:00:00 on appointment date
prep_body = fn_body('prepareVisitPrep')
if 'T12:00:00' in prep_body:
    ok("prepareVisitPrep() uses T12:00:00 — appointment date displays correctly in all timezones")
else:
    warn("prepareVisitPrep() timezone", "Appointment date may show as previous day in UTC-offset timezones on print")

# 25t — prepareVisitPrep() falls back to 'Patient' if no profile
if "'Patient'" in prep_body or '"Patient"' in prep_body:
    ok("prepareVisitPrep() falls back to 'Patient' label when no profile set — print never shows blank name")
else:
    warn("prepareVisitPrep() profile fallback", "Visit prep may show blank patient name when no profile saved")


# ════════════════════════════════════════
#  LAYER 26 — RENDER FUNCTIONS, LOAD/SAVE,
#  EMERGENCY CARD, MED TIME SORT,
#  DATA SUMMARY, GOOD DAYS WIDGET
# ════════════════════════════════════════

# 26a — load() has try/catch — bad JSON doesn't crash app
load_body = fn_body('load')
if 'try' in load_body and 'catch' in load_body and 'fallback' in load_body:
    ok("load() wraps JSON.parse in try/catch — corrupt localStorage doesn't crash app")
else:
    fail("load() missing try/catch", "Corrupt localStorage entry throws exception — entire app crashes on load")

# 26b — load() returns fallback when key is null
if 'return d ? JSON.parse(d) : fallback' in load_body or ('return' in load_body and 'fallback' in load_body):
    ok("load() returns fallback when key is null — first-run always works")
else:
    fail("load() no null check", "Missing localStorage key throws on JSON.parse(null)")

# 26c — renderMedications() shows empty state when no meds
med_body = fn_body('renderMedications')
if 'empty-state' in med_body and 'No medications' in html:
    ok("renderMedications() shows empty state — no blank panel on first load")
else:
    warn("renderMedications() empty state", "Blank panel shown when no medications added yet")

# 26d — renderMedications() shows 'no match' state when search has no results
if 'No medications match' in html or 'no.*match' in med_body.lower():
    ok("renderMedications() shows no-match state when search returns nothing")
else:
    warn("renderMedications() search empty state", "Blank panel shown when search returns no results")

# 26e — renderMedications() sorts alphabetically by name
if 'localeCompare' in med_body and 'a.name' in med_body:
    ok("renderMedications() sorts alphabetically by name — consistent list order")
else:
    warn("renderMedications() sort", "Medications not sorted — order changes on every add/edit")

# 26f — renderMedications() uses esc() on med name in buttons (XSS in aria-label)
if 'esc(m.name)' in med_body:
    ok("renderMedications() uses esc(m.name) — XSS prevented in aria-label and display")
else:
    fail("renderMedications() missing esc(m.name)", "Med name injected raw into aria-label — XSS risk")

# 26g — renderSymptomLog() shows empty state when no logs
log_body = fn_body('renderSymptomLog')
if 'empty-state' in log_body and 'No entries' in html:
    ok("renderSymptomLog() shows empty state — no blank panel on first load")
else:
    warn("renderSymptomLog() empty state", "Blank panel shown when no log entries exist")

# 26h — renderSymptomLog() supports mood filter and text search
if 'moodFilter' in log_body and 'query' in log_body:
    ok("renderSymptomLog() supports mood filter and text search — log is findable")
else:
    warn("renderSymptomLog() filtering", "No search/filter on symptom log — hard to find entries")

# 26i — renderSymptomLog() paginates results (PAGE constant)
if 'PAGE' in log_body and 'slice(0, PAGE)' in log_body:
    ok("renderSymptomLog() paginates at PAGE entries — no DOM overload with large logs")
else:
    warn("renderSymptomLog() pagination", "All entries rendered at once — hundreds of logs will slow DOM")

# 26j — renderCareTeam() shows empty state when no contacts
ct_body = fn_body('renderCareTeam')
if 'empty-state' in ct_body and 'No contacts' in html:
    ok("renderCareTeam() shows empty state — no blank panel on first load")
else:
    warn("renderCareTeam() empty state", "Blank panel shown when no care team contacts added")

# 26k — renderCareTeam() uses esc() on name, phone, email, notes
for field in ['esc(c.name)', 'esc(c.phone)', 'esc(c.email)', 'esc(c.notes)']:
    if field in ct_body:
        ok(f"renderCareTeam() uses {field} — XSS prevented")
    else:
        fail(f"renderCareTeam() missing {field}", "User-entered contact data injected raw into innerHTML — XSS risk")

# 26l — renderMemories() shows empty state when no memories
mem_body = fn_body('renderMemories')
if 'empty-state' in mem_body and 'memory box is empty' in html:
    ok("renderMemories() shows empty state — no blank panel on first load")
else:
    warn("renderMemories() empty state", "Blank panel shown when no memories added yet")

# 26m — renderMemories() missing esc() on title/text is a risk
if 'esc(m.title)' in mem_body or 'esc(m.text)' in mem_body:
    ok("renderMemories() uses esc() on memory title/text — XSS prevented")
else:
    # memories uses m.title and m.text directly — check raw injection
    if 'm.title' in mem_body and 'esc' not in mem_body:
        fail("renderMemories() missing esc()", "Memory title/text injected raw into innerHTML — XSS risk")
    else:
        warn("renderMemories() esc() check", "Verify memory title and text are sanitized before innerHTML injection")

# 26n — loadEmergencyCard() syncs name from profile (source of truth)
ec_load_body = fn_body('loadEmergencyCard')
if 'profile.name' in ec_load_body and 'ec-name' in ec_load_body:
    ok("loadEmergencyCard() syncs name from profile — emergency card always shows current name")
else:
    warn("loadEmergencyCard() name sync", "Emergency card name not synced from profile — may show stale name")

# 26o — loadEmergencyCard() auto-populates contact1 from care team when not saved
if 'contact1' in ec_load_body and ('team.find' in ec_load_body or 'careteam' in ec_load_body.lower()):
    ok("loadEmergencyCard() auto-populates contact1 from care team — less duplicate data entry")
else:
    warn("loadEmergencyCard() contact auto-fill", "Emergency contacts not pre-filled from care team")

# 26p — updateEmergencyCard() uses esc() on med name/dose/frequency (XSS in preview)
ec_update_body = fn_body('updateEmergencyCard')
if 'esc(m.name)' in ec_update_body and 'esc(m.dose)' in ec_update_body:
    ok("updateEmergencyCard() uses esc() on med fields — XSS prevented in print preview")
else:
    fail("updateEmergencyCard() missing esc()", "Medication names injected raw into emergency card preview — XSS risk")

# 26q — medTimeToMinutes() returns -1 for PRN meds (sorts to top)
mttm_body = fn_body('medTimeToMinutes')
if 'isPRN' in mttm_body and 'return -1' in mttm_body:
    ok("medTimeToMinutes() returns -1 for PRN meds — as-needed meds sort to top of schedule")
else:
    warn("medTimeToMinutes() PRN sort", "PRN meds not sorted separately — mixed into timed med schedule")

# 26r — medTimeToMinutes() parses 12h am/pm format correctly (handles 12am edge case)
if "ampm === 'am' && h === 12" in mttm_body and 'h = 0' in mttm_body:
    ok("medTimeToMinutes() handles 12:xx am → 0 hours (midnight) — 12h parsing correct")
else:
    fail("medTimeToMinutes() 12am edge case", "12:xx am parsed as noon (720 min) not midnight (0 min) — sort order wrong for midnight meds")

# 26s — renderDataSummary() counts all 7 data sections
ds_body = fn_body('renderDataSummary')
section_keys = ['medications', 'logs', 'appointments', 'careteam', 'handoff', 'memories', 'stress']
for key in section_keys:
    if key in ds_body:
        ok(f"renderDataSummary() includes {key} section count")
    else:
        warn(f"renderDataSummary() missing {key}", f"{key} not shown in data summary — user can't see backup completeness")

# 26t — renderGoodDaysWidget() streak loop guarded at 365
gdw_body = fn_body('renderGoodDaysWidget')
if 'streak < 365' in gdw_body or 'streak > 365' in gdw_body or 'streak >= 365' in gdw_body:
    ok("renderGoodDaysWidget() streak loop guarded at 365 — no infinite loop")
else:
    fail("renderGoodDaysWidget() streak loop unguarded", "while loop without exit guard could hang browser on corrupt data")

# 26u — renderGoodDaysWidget() shows empty state when no good days
if 'empty-state' in gdw_body and 'No good days' in html:
    ok("renderGoodDaysWidget() shows empty state — no blank panel when no happy entries")
else:
    warn("renderGoodDaysWidget() empty state", "Blank dashboard panel when no 😊 entries exist")

# 26v — toggleRecurringFields() shows/hides recurring fields based on checkbox
recur_toggle_body = fn_body('toggleRecurringFields')
if 'appt-recurring' in recur_toggle_body and 'appt-recurring-fields' in recur_toggle_body:
    ok("toggleRecurringFields() shows/hides recurring fields based on checkbox state")
else:
    fail("toggleRecurringFields() broken", "Recurring fields always shown or always hidden — checkbox has no effect")

# 26w — getMedTimesValue() converts 24h input to 12h am/pm display format
gmtv_body = fn_body('getMedTimesValue')
if 'ampm' in gmtv_body and ('am' in gmtv_body or 'pm' in gmtv_body):
    ok("getMedTimesValue() converts 24h browser input → 12h am/pm — stored times are human-readable")
else:
    warn("getMedTimesValue() time format", "Med times stored in 24h format — displayed as '14:00' not '2:00pm'")

# 26x — renderCharts() handles empty state (no logs or stress entries)
charts_body = fn_body('renderCharts')
if 'charts-empty' in charts_body and 'display' in charts_body:
    ok("renderCharts() shows empty state when no data — no broken chart on first load")
else:
    warn("renderCharts() empty state", "Charts may render empty/broken when no log or stress entries exist")


# ════════════════════════════════════════
#  LAYER 27 — UI STATE, PRINT GRIDS,
#  GREETING, PROFILE DISPLAY, MOOD SELECTORS
# ════════════════════════════════════════

# 27a — showLastSaved() clears after 8 seconds (no stale 'Saved' label)
sls_body = fn_body('showLastSaved')
if 'setTimeout' in sls_body and ('8000' in sls_body or "'' " in sls_body or "''" in sls_body):
    ok("showLastSaved() clears label after 8s — no stale 'Saved' shown permanently")
else:
    warn("showLastSaved() cleanup", "'✓ Saved' label may stay visible indefinitely after saving")

# 27b — showLastSaved() called by save() — every save shows confirmation
save_body = fn_body('save')
if 'showLastSaved' in save_body:
    ok("save() calls showLastSaved() — user sees confirmation on every data write")
else:
    warn("save() missing showLastSaved()", "No visual feedback when data is saved")

# 27c — setGreeting() uses time-of-day logic (morning/afternoon/evening)
greet_body = fn_body('setGreeting')
if 'Good morning' in greet_body and 'Good afternoon' in greet_body and 'Good evening' in greet_body:
    ok("setGreeting() shows correct time-of-day greeting (morning/afternoon/evening)")
else:
    warn("setGreeting() time logic", "Greeting doesn't vary by time of day")

# 27d — setGreeting() personalises with caregiver first name
if 'caregiver' in greet_body and 'split' in greet_body:
    ok("setGreeting() uses caregiver first name — personalised greeting on dashboard")
else:
    warn("setGreeting() personalisation", "Greeting not personalised with caregiver name from profile")

# 27e — updateProfileDisplay() updates both sidebar and hero name
upd_body = fn_body('updateProfileDisplay')
if 'sidebar-name' in upd_body and 'hero-name' in upd_body:
    ok("updateProfileDisplay() updates sidebar-name and hero-name — name shown in both places")
else:
    fail("updateProfileDisplay() incomplete", "Profile name update doesn't reach all display locations")

# 27f — toggleSidebar() opens and closes via classList (not style.display)
toggle_body = fn_body('toggleSidebar')
if 'classList' in toggle_body and ('open' in toggle_body) and 'closeSidebar' in toggle_body:
    ok("toggleSidebar() toggles via classList — consistent open/close state")
else:
    warn("toggleSidebar() implementation", "Sidebar toggle may not track open state reliably")

# 27g — closeSidebar() removes open class from sidebar, overlay, and hamburger button
close_body = fn_body('closeSidebar')
targets = ['sidebar', 'sidebar-overlay', 'hamburger-btn']
for t in targets:
    if t in close_body:
        ok(f"closeSidebar() resets {t} — no stuck-open state")
    else:
        warn(f"closeSidebar() missing {t} reset", f"{t} may stay visually open after close")

# 27h — selectMood() toggles selected class and updates selectedMood variable
mood_body = fn_body('selectMood')
if 'selectedMood' in mood_body and 'classList.toggle' in mood_body:
    ok("selectMood() updates selectedMood and toggles selected class — mood picker works")
else:
    warn("selectMood() state", "Mood selection may not update variable or visual state")

# 27i — selectMemMood() mirrors selectMood() pattern for memories
memmood_body = fn_body('selectMemMood')
if 'selectedMemMood' in memmood_body and 'classList.toggle' in memmood_body:
    ok("selectMemMood() updates selectedMemMood and toggles selected class — memory mood picker works")
else:
    warn("selectMemMood() state", "Memory mood selection may not update variable or visual state")

# 27j — selectStress() uses tiered CSS classes (selected-low/mid/high) not a single class
stress_sel_body = fn_body('selectStress')
if 'selected-low' in stress_sel_body and 'selected-mid' in stress_sel_body and 'selected-high' in stress_sel_body:
    ok("selectStress() applies tiered color classes (low/mid/high) — wellbeing score visually correct")
else:
    warn("selectStress() color tiers", "Stress button color doesn't reflect score level")

# 27k — toggleMedForm() clears form on both open and close
tmf_body = fn_body('toggleMedForm')
if 'clearMedForm' in tmf_body:
    count_clear = tmf_body.count('clearMedForm')
    if count_clear >= 1:
        ok("toggleMedForm() calls clearMedForm() — form never shows stale data")
    else:
        warn("toggleMedForm() form clear", "Form may retain previous values on re-open")
else:
    fail("toggleMedForm() missing clearMedForm()", "Add medication form shows previous entry data when reopened")

# 27l — toggleMedForm() scrolls form into view on open
if 'scrollIntoView' in tmf_body:
    ok("toggleMedForm() scrolls form into view on open — form visible without manual scroll")
else:
    warn("toggleMedForm() scroll", "Add medication form may open off-screen on mobile")

# 27m — updateMedTimeInputs() handles PRN meds (no time inputs shown)
umti_body = fn_body('updateMedTimeInputs')
if 'isPRN' in umti_body and 'as needed' in umti_body.lower():
    ok("updateMedTimeInputs() hides time inputs for PRN meds — 'as needed' meds need no schedule")
else:
    warn("updateMedTimeInputs() PRN handling", "PRN meds still show time input fields — confusing for caregivers")

# 27n — renderMedicationPrintTable() sorts alphabetically
med_print_body = fn_body('renderMedicationPrintTable')
if 'localeCompare' in med_print_body and 'a.name' in med_print_body:
    ok("renderMedicationPrintTable() sorts meds alphabetically — print list is organised")
else:
    warn("renderMedicationPrintTable() sort", "Print medication list not sorted — random order on printed sheet")

# 27o — renderMedicationPrintTable() uses esc() on name and notes (XSS in print view)
if 'esc(m.name)' in med_print_body and ('esc(nameExtra)' in med_print_body or 'esc(m.notes)' in med_print_body):
    ok("renderMedicationPrintTable() uses esc() — XSS prevented in print view")
else:
    fail("renderMedicationPrintTable() missing esc()", "Medication name/notes injected raw into print table — XSS risk")

# 27p — renderMedicationPrintTable() handles empty med list (no broken table)
if '!meds.length' in med_print_body or 'meds.length === 0' in med_print_body:
    ok("renderMedicationPrintTable() handles empty med list — no broken empty table on print")
else:
    warn("renderMedicationPrintTable() empty guard", "Print table may render empty <tbody> with no meds")

# 27q — renderCareTeamPrintGrid() uses esc() on all contact fields
ct_print_body = fn_body('renderCareTeamPrintGrid')
for field in ['esc(c.name)', 'esc(c.role)', 'esc(c.phone)', 'esc(c.email)', 'esc(c.notes)']:
    if field in ct_print_body:
        ok(f"renderCareTeamPrintGrid() uses {field} — XSS prevented in print view")
    else:
        fail(f"renderCareTeamPrintGrid() missing {field}", "Contact data injected raw into print grid — XSS risk")

# 27r — renderCareTeamPrintGrid() hides grid when no contacts
if '!contacts.length' in ct_print_body or "display = 'none'" in ct_print_body:
    ok("renderCareTeamPrintGrid() hides grid when no contacts — no blank grid on print")
else:
    warn("renderCareTeamPrintGrid() empty guard", "Empty care team grid shown on print — blank boxes on printed sheet")


# ════════════════════════════════════════
#  REPORT
# ════════════════════════════════════════
print()
print("═"*62)
print("  CARECOMPANION QA REPORT")
print("═"*62)
print(f"\n  PASSED ({len(passes)}):")
for p in passes: print(p)
if warns:
    print(f"\n  WARNINGS ({len(warns)}):")
    for w in warns: print(w)
if fails:
    print(f"\n  FAILURES ({len(fails)}):")
    for f in fails: print(f)
print()
print("═"*62)
if not fails:
    print(f"  RESULT: ✓ PASS — {len(passes)} checks passed, {len(warns)} warnings")
else:
    print(f"  RESULT: ✗ FAIL — {len(fails)} failures must be fixed before pushing")
print("═"*62)
print()
sys.exit(1 if fails else 0)
