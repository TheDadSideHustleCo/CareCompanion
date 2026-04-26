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
