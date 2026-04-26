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

for k in ['profile','medications','logs','appointments','careteam','handoff','memories','stress','disclaimer','medChecks','emergency']:
    if k in html: ok(f"KEYS.{k} present")
    else: fail(f"KEYS.{k}", "Missing from KEYS object")


# ════════════════════════════════════════
#  LAYER 2 — PWA READINESS
# ════════════════════════════════════════

if has("serviceWorker.register"): ok("Service worker registered")
else: fail("Service worker", "No registration call found")

sw_v = find(r"carecompanion-v(\d+)")
if sw_v: ok(f"SW cache versioned (v{sw_v.group(1)})")
else: warn("SW cache version", "Not found in HTML")

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
    ('addStressEntry', r"if\s*\(!.*date\)|alert.*date"),
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
