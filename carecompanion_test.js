#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════
//  CareCompanion v1.2 — Full Functional Test Suite
//  Run: node carecompanion_test.js
// ═══════════════════════════════════════════════════════════════
'use strict';

const fs   = require('fs');
const path = require('path');

const FILE = path.join(__dirname, 'mnt/Care Companion/carecompanion (16).html');
const html = fs.readFileSync(FILE, 'utf8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
const styleMatch  = html.match(/<style>([\s\S]*?)<\/style>/);
const js  = scriptMatch ? scriptMatch[1] : '';
const css = styleMatch  ? styleMatch[1]  : '';

let passed = 0, failed = 0, warned = 0;
const failures = [], warnings = [], sections = [];

function check(name, ok, detail = '') {
  if (ok)  { console.log(`  ✅ ${name}`); passed++; }
  else     { console.log(`  ❌ ${name}${detail ? ' — ' + detail : ''}`); failed++; failures.push(name + (detail ? ': ' + detail : '')); }
}
function warn(name, detail = '') {
  console.log(`  ⚠️  ${name}${detail ? ' — ' + detail : ''}`); warned++;
  warnings.push(name + (detail ? ': ' + detail : ''));
}
function section(title) {
  console.log(`\n[ ${sections.length + 1} ] ${title}`);
  sections.push(title);
}

const jsNoComments = js.replace(/\/\/[^\n]*/g, '').replace(/\/\*[\s\S]*?\*\//g, '');
const allHtmlIds   = Array.from(html.matchAll(/\bid=["']([^"']+)["']/g), m => m[1]);
const htmlIdSet    = new Set(allHtmlIds);

console.log('\n══════════════════════════════════════════════════');
console.log('  CareCompanion v1.2 — Full Functional Test Suite');
console.log('══════════════════════════════════════════════════');

// ─────────────────────────────────────────────────────────────
// 1. CODE INTEGRITY
// ─────────────────────────────────────────────────────────────
section('Code Integrity');

// JS syntax
try   { new Function(js); check('JS parses without errors', true); }
catch (e) { check('JS parses without errors', false, e.message.replace(/\n/g,' ').slice(0,120)); }

// No debug artifacts
check('No console.log statements', !jsNoComments.includes('console.log('));
check('No TODO comments in JS', !js.includes('// TODO'));
check('No location.reload() calls', !jsNoComments.includes('location.reload()'));

// Version consistency
check('Version v1.2 in sidebar footer', html.includes('CareCompanion v1.2'));
check('_version: 1.2 in exportData', js.includes("_version: '1.2'"));
check('App title correct', html.includes('CareCompanion — Your Personal Caregiving Assistant'));

// Duplicate IDs
const idCounts = Object.create(null);
allHtmlIds.forEach(id => { idCounts[id] = (idCounts[id] || 0) + 1; });
const dupeIds = Object.entries(idCounts).filter(([, c]) => c > 1);
if (dupeIds.length === 0) check('No duplicate HTML IDs', true);
else dupeIds.forEach(([id, c]) => check(`No duplicate ID: ${id}`, false, `appears ${c} times`));

// getElementById targets exist
const jsIdRefs   = Array.from(js.matchAll(/getElementById\(["']([^"']+)["']\)/g), m => m[1]);
const missingIds = [...new Set(jsIdRefs)].filter(id => !htmlIdSet.has(id));
if (missingIds.length === 0) check('All getElementById targets exist in HTML', true);
else missingIds.forEach(id => check(`getElementById('${id}') exists`, false, 'missing from HTML'));

// ─────────────────────────────────────────────────────────────
// 2. FUNCTION COMPLETENESS
// ─────────────────────────────────────────────────────────────
section('Function Completeness');

const requiredFunctions = [
  // Core
  'acceptDisclaimer','openSetup','saveSetup','updateProfileDisplay',
  'toggleSidebar','closeSidebar','navigate','setGreeting','renderAll','showToast','showLastSaved',
  // Medications
  'addMedication','editMedication','deleteMedication','renderMedications',
  'getDoseCount','getDoseLabels','getMedTimesValue','updateMedTimeInputs',
  'toggleMedCheck','logPRNDose','updatePillDaysLeft','getMedChecksForToday','getTodayKey',
  // Symptom Log
  'selectMood','addLogEntry','editLog','deleteLog','renderSymptomLog',
  // Appointments
  'addAppointment','editAppointment','deleteAppointment','renderAppointments',
  'sortAppointments','markAttended','unmarkAttended','navigateToAppointment',
  'toggleRecurringFields','generateRecurringDates',
  // Care Team
  'addContact','editContact','deleteContact','renderCareTeam',
  // Handoff
  'addHandoff','editHandoff','deleteHandoff','renderHandoff',
  // Memory Box
  'selectMemMood','addMemory','editMemory','deleteMemory','renderMemories',
  // Stress
  'selectStress','addStressEntry','editStress','deleteStress','renderStress',
  // Emergency
  'loadEmergencyCard','saveEmergencyFields','updateEmergencyCard',
  // Dashboard & Charts
  'renderDashboard','renderGettingStarted','renderRefillAlerts',
  'renderCharts','renderGoodDays','renderMoodSnapshot','renderGoodDaysWidget',
  // Dashboard widgets
  'renderMedSearch','printVisitPrep',
  // Print
  'preparePrintHeaders','printMedicationList','renderCareTeamPrintGrid',
  // Data
  'exportData','importData','clearAllData','renderDataSummary',
  // Tooltips
  'startTooltips','showTooltip','nextTooltip','skipTooltips',
  // Utilities
  'formatDate','formatTime','freqToDoseCount','timeStrTo24',
];

requiredFunctions.forEach(fn => check(`${fn}() defined`, js.includes(`function ${fn}(`)));

// ─────────────────────────────────────────────────────────────
// 3. DATA MODEL — localStorage KEYS
// ─────────────────────────────────────────────────────────────
section('Data Model — localStorage Keys');

const keysMatch = js.match(/const KEYS = \{([\s\S]*?)\};/);
const keysBody  = keysMatch ? keysMatch[1] : '';
['profile','medications','logs','appointments','careteam','handoff',
 'memories','stress','disclaimer','medChecks','emergency',
].forEach(k => check(`KEYS.${k} defined`, keysBody.includes(k + ':')));

// ─────────────────────────────────────────────────────────────
// 4. MEDICATIONS MODULE
// ─────────────────────────────────────────────────────────────
section('Medications Module');

check('Med form: name field', html.includes('id="med-name"'));
check('Med form: dose field', html.includes('id="med-dose"'));
check('Med form: frequency field', html.includes('id="med-freq"'));
check('Med form: pills-left field', html.includes('id="med-pills"'));
check('Med form: food field', html.includes('id="med-food"'));
check('Med form: notes field', html.includes('id="med-notes"'));
check('Med form: times field present', html.includes('id="med-times-container"') || html.includes('id="med-times"'));
check('Med checklist rendered in dashboard', html.includes('id="dashboard-meds"'));
check('Medication print table exists', html.includes('id="medications-print-table-wrap"'));
check('Refill alert threshold logic', js.includes('pillsLeft') || js.includes('pills_left') || js.includes('refill'));
check('PRN dose logging', js.includes('logPRNDose'));
check('Med check toggle saves to localStorage', js.includes('function toggleMedCheck') && /toggleMedCheck[\s\S]{0,300}localStorage\.setItem/.test(js));
check('Pill days left calculation', js.includes('function updatePillDaysLeft'));
check('Dose label generation (multiple doses/day)', js.includes('function getDoseLabels'));

// ─────────────────────────────────────────────────────────────
// 5. SYMPTOM LOG MODULE
// ─────────────────────────────────────────────────────────────
section('Symptom Log Module');

check('Log form: date field', html.includes('id="log-date"'));
check('Log form: mood selector', html.includes('id="mood-selector"'));
check('Log form: symptoms field', html.includes('id="log-symptoms"'));
check('Log form: sleep field', html.includes('id="log-sleep"'));
check('Mood emojis defined', js.includes("'😊'") && js.includes("'😔'") && js.includes("'😐'"));
check('Show all / show less toggle', js.includes('logShowAll = false') && js.includes('logShowAll=true'));
check('logShowAll reset on new entry', /function addLogEntry\b[\s\S]{0,1200}logShowAll\s*=\s*false/.test(js));
check('Log entries sorted newest first', js.includes('function renderSymptomLog') && /logs[\s\S]{0,100}sort|sort[\s\S]{0,100}date\.localeCompare/.test(js));
check('Log search/filter exists', html.includes('id="log-search"') || html.includes('id="log-filter"') || js.includes('isFiltering'));

// ─────────────────────────────────────────────────────────────
// 6. APPOINTMENTS MODULE
// ─────────────────────────────────────────────────────────────
section('Appointments Module');

check('Appt form: title field', html.includes('id="appt-title"'));
check('Appt form: date field', html.includes('id="appt-date"'));
check('Appt form: time field', html.includes('id="appt-time"'));
check('Appt form: doctor field', html.includes('id="appt-doctor"'));
check('Appt form: address field', html.includes('id="appt-address"'));
check('Appt form: category select', html.includes('id="appt-category"'));
check('Appt form: notes field', html.includes('id="appt-notes"'));
check('Visit notes row (post-visit)', html.includes('id="appt-visit-notes-row"'));
check('Mark attended button logic', js.includes('markAttended'));
check('Undo attended logic', js.includes('unmarkAttended'));
check('Appointments sorted by date', /function sortAppointments/.test(js));
check('Past vs upcoming split in render', /past[\s\S]{0,200}upcoming|upcoming[\s\S]{0,200}past/.test(js));

// Recurring
check('Recurring checkbox in form', html.includes('id="appt-recurring"'));
check('Recurring frequency dropdown', html.includes('id="appt-recur-freq"'));
check('Recurring end date field', html.includes('id="appt-recur-end"'));
check('generateRecurringDates handles weekly', /weekly[\s\S]{0,100}7/.test(js));
check('generateRecurringDates handles monthly', /monthly[\s\S]{0,100}setMonth/.test(js));
check('generateRecurringDates caps at 52', js.includes('52'));
check('Recurring groupId assigned on save', js.includes('recurringGroupId'));
check('Delete recurring: prompts single vs series', /recurringGroupId[\s\S]{0,400}confirm/.test(js));
check('Recurring badge shown on card', js.includes('🔁 Repeating'));

// Doctor visit prep
check('Print visit prep function exists', js.includes('function printVisitPrep('));
check('Visit prep includes med table', /printVisitPrep[\s\S]{0,1500}medRows/.test(js));
check('Visit prep includes recent logs', /printVisitPrep[\s\S]{0,1500}logItems/.test(js));
check('Visit prep includes questions section', js.includes('Questions to Ask'));
check('Prep button on upcoming appointments', js.includes("printVisitPrep(${a.id})"));

// ─────────────────────────────────────────────────────────────
// 7. CARE TEAM MODULE
// ─────────────────────────────────────────────────────────────
section('Care Team Module');

check('Care team form: name field', html.includes('id="ct-name"'));
check('Care team form: role field', html.includes('id="ct-role"'));
check('Care team form: phone field', html.includes('id="ct-phone"'));
check('Care team form: fax field', html.includes('id="ct-fax"'));
check('Care team form: facility field', html.includes('id="ct-facility"'));
check('Care team form: email field', html.includes('id="ct-email"'));
check('Care team form: notes field', html.includes('id="ct-notes"'));
check('Care team list container', html.includes('id="careteam-list"'));
check('Print grid container', html.includes('id="ct-print-grid"'));
check('renderCareTeamPrintGrid generates cards', /function renderCareTeamPrintGrid[\s\S]{0,600}ct-print-card/.test(js));

// ─────────────────────────────────────────────────────────────
// 8. HANDOFF NOTES MODULE
// ─────────────────────────────────────────────────────────────
section('Handoff Notes Module');

check('Handoff form: date field', html.includes('id="ho-date"'));
check('Handoff form: shift select', html.includes('id="ho-shift"'));
check('Handoff form: caregiver field', html.includes('id="ho-caregiver"'));
check('Handoff form: meds given field', html.includes('id="ho-meds"'));
check('Handoff form: meals field', html.includes('id="ho-meals"'));
check('Handoff form: mood field', html.includes('id="ho-mood"'));
check('Handoff form: watch-for field', html.includes('id="ho-watch"'));
check('Handoff form: notes field', html.includes('id="ho-notes"'));
check('Handoff list container', html.includes('id="handoff-list"'));
check('Shift options: Morning/Afternoon/Overnight/Full Day',
  html.includes('Morning (6am') && html.includes('Afternoon (2pm') && html.includes('Overnight (10pm') && html.includes('Full Day'));

// ─────────────────────────────────────────────────────────────
// 9. MEMORY BOX MODULE
// ─────────────────────────────────────────────────────────────
section('Memory Box Module');

check('Memory form: title field', html.includes('id="mem-title"'));
check('Memory form: date field', html.includes('id="mem-date"'));
check('Memory form: text field', html.includes('id="mem-text"'));
check('Memory mood selector', html.includes('id="mem-mood-selector"'));
check('Memory mood emojis', html.includes("selectMemMood('💛')") && html.includes("selectMemMood('😂')"));
check('Memories list container', html.includes('id="memory-list"') || html.includes('id="memories-list"'));

// ─────────────────────────────────────────────────────────────
// 10. STRESS TRACKER MODULE
// ─────────────────────────────────────────────────────────────
section('Stress Tracker Module');

check('Stress level selector', js.includes('function selectStress'));
check('Stress form: notes field', html.includes('id="stress-notes"') || html.includes('id="stress-note"'));
check('Stress list renders entries', js.includes('function renderStress'));
check('Stress delete works', js.includes('function deleteStress'));

// ─────────────────────────────────────────────────────────────
// 11. EMERGENCY CARD MODULE
// ─────────────────────────────────────────────────────────────
section('Emergency Card Module');

check('Emergency page exists', html.includes('id="page-emergency"'));
check('Emergency card preview', html.includes('emergency-preview') || html.includes('class="emergency'));
check('Save emergency fields function', js.includes('function saveEmergencyFields'));
check('Emergency card auto-populates from profile', /loadEmergencyCard[\s\S]{0,400}profile/.test(js));
check('Emergency card auto-populates meds', /loadEmergencyCard[\s\S]{0,800}medication/.test(js));
check('Emergency card auto-populates contacts', /loadEmergencyCard[\s\S]{0,800}careteam|contact/.test(js));

// ─────────────────────────────────────────────────────────────
// 12. DASHBOARD MODULE
// ─────────────────────────────────────────────────────────────
section('Dashboard Module');

check('Dashboard hero greeting', html.includes('id="hero-greeting"'));
check('Dashboard hero patient name', html.includes('id="hero-name"'));
check('Stat: medications today', html.includes('id="stat-meds"'));
check('Stat: next appointment', html.includes('id="stat-appt-card"'));
check('Stat: days logged', html.includes('id="stat-days"'));
check('Refill alerts container', html.includes('id="refill-alerts"'));
check('Today meds list', html.includes('id="dashboard-meds"'));
check('Recent log preview', html.includes('id="dashboard-log"'));
check('Upcoming appointments preview', html.includes('id="dashboard-appts"'));
check('Mood snapshot widget', html.includes('id="dash-mood-snapshot"'));
check('Good days widget', html.includes('id="dash-gooddays-content"'));
check('Medication search widget', html.includes('id="dash-med-search"'));
check('Medication search results', html.includes('id="dash-med-results"'));
check('Getting started checklist', html.includes('id="getting-started"'));
check('Getting started progress bar', html.includes('id="gs-progress-fill"'));
check('renderDashboard calls renderRefillAlerts', /function renderDashboard[\s\S]{0,8000}renderRefillAlerts\(\)/.test(js));
check('renderDashboard calls renderCharts', /function renderDashboard[\s\S]{0,8000}renderCharts\(\)/.test(js));
check('renderDashboard calls renderGoodDays', /function renderDashboard[\s\S]{0,8000}renderGoodDays\(\)/.test(js));
check('renderDashboard calls renderMoodSnapshot', /function renderDashboard[\s\S]{0,8000}renderMoodSnapshot\(\)/.test(js));
check('renderDashboard calls renderGoodDaysWidget', /function renderDashboard[\s\S]{0,8000}renderGoodDaysWidget\(\)/.test(js));
check('setGreeting changes by time of day', /morning|afternoon|evening/.test(js));

// ─────────────────────────────────────────────────────────────
// 13. TREND CHARTS
// ─────────────────────────────────────────────────────────────
section('Trend Charts');

check('Mood chart container', html.includes('id="chart-mood"'));
check('Chart empty state', html.includes('id="charts-empty"'));
check('Chart content container', html.includes('id="charts-content"'));
check('Chart renders 14-day window', /14/.test(js));
check('Chart summaries rendered', html.includes('id="chart-summaries"'));

// ─────────────────────────────────────────────────────────────
// 14. GOOD DAYS
// ─────────────────────────────────────────────────────────────
section('Good Days');

check('Good days strip container', html.includes('id="good-days-strip"'));
check('Good days list', html.includes('id="good-days-list"'));
check('Good days streak badge', html.includes('id="good-days-streak"'));
check('Good days summary text', html.includes('id="good-days-summary"'));
check('Streak calculation logic', /streak[\s\S]{0,200}setDate/.test(js));
check('Last 30 days count', js.includes('last30Count') || js.includes('last30'));
check('Good days filtered by 😊 mood', js.includes("mood === '😊'"));

// ─────────────────────────────────────────────────────────────
// 15. REFILL ALERTS
// ─────────────────────────────────────────────────────────────
section('Refill Alerts');

check('Refill alerts rendered in renderDashboard',
  /function renderDashboard\b[\s\S]{0,10000}renderRefillAlerts\(\)/.test(js));
check('Refill alerts rendered in renderAll',
  /function renderAll\b[\s\S]{0,1000}renderRefillAlerts\(\)/.test(js));
check('Refill alert checks pill count', /pillsLeft|pills.*left|refill/i.test(js));

// ─────────────────────────────────────────────────────────────
// 16. NAVIGATION
// ─────────────────────────────────────────────────────────────
section('Navigation');

check('navigate() scrolls to top', js.includes('scrollTo') && js.includes('top: 0'));
check('navigate() re-renders careteam', /navigate[\s\S]{0,2000}careteam.*renderCareTeam|renderCareTeam[\s\S]{0,200}careteam/.test(js));
check('navigate() re-renders symptoms', /page === 'symptoms'[\s\S]{0,100}renderSymptomLog/.test(js));
check('navigate() re-renders medications', /page === 'medications'[\s\S]{0,100}renderMedications/.test(js));
check('navigate() re-renders handoff', /page === 'handoff'[\s\S]{0,100}renderHandoff/.test(js));
check('navigate() re-renders memories', /page === 'memories'[\s\S]{0,100}renderMemories/.test(js));
check('navigate() re-renders stress', /page === 'stress'[\s\S]{0,100}renderStress/.test(js));
check('navigate() re-renders dashboard', /page === 'dashboard'[\s\S]{0,100}renderDashboard/.test(js));
check('navigate() closes sidebar on mobile', js.includes('closeSidebar'));
check('All nav pages have matching page div',
  ['dashboard','medications','symptoms','appointments','careteam',
   'handoff','memory','stress','emergency','export'].every(p => html.includes(`id="page-${p}"`)));

// ─────────────────────────────────────────────────────────────
// 17. EXPORT / IMPORT / CLEAR
// ─────────────────────────────────────────────────────────────
section('Export / Import / Clear Data');

check('Export builds all KEYS', /exportData[\s\S]{0,400}Object\.values\(KEYS\)/.test(js));
check('Export includes _version', /exportData[\s\S]{0,300}_version/.test(js));
check('Export includes _app tag', /exportData[\s\S]{0,300}_app.*CareCompanion|CareCompanion.*_app/.test(js));
check('Import validates _app field', /importData[\s\S]{0,400}_app.*CareCompanion/.test(js));
check('Import validates _version field', /importData[\s\S]{0,400}_version/.test(js));
check('clearAllData removes all keys', /clearAllData[\s\S]{0,400}Object\.values\(KEYS\)|KEYS\.\w+.*remove|removeItem/.test(js));
check('Data summary page renders', js.includes('function renderDataSummary'));
check('Export status feedback element', html.includes('id="export-status"'));
check('Import filename display', html.includes('id="import-filename"'));

// ─────────────────────────────────────────────────────────────
// 18. PRINT SYSTEM
// ─────────────────────────────────────────────────────────────
section('Print System');

check('preparePrintHeaders populates all 4 headers',
  /preparePrintHeaders[\s\S]{0,600}med-print-header[\s\S]{0,200}ct-print-header[\s\S]{0,200}handoff-print-header[\s\S]{0,200}ec-print-header/.test(js));
check('beforeprint event listener', js.includes("addEventListener('beforeprint'") || js.includes('addEventListener("beforeprint"'));
check('beforeprint calls preparePrintHeaders', /beforeprint[\s\S]{0,200}preparePrintHeaders/.test(js));
check('beforeprint calls printMedicationList', /beforeprint[\s\S]{0,200}printMedicationList/.test(js));
check('beforeprint calls renderCareTeamPrintGrid', /beforeprint[\s\S]{0,200}renderCareTeamPrintGrid/.test(js));
check('Medication print table has thead', css.includes('medications-print-table thead') || /printMedicationList[\s\S]{0,1500}thead/.test(js));
check('@media print hides screen elements', css.includes('@media print'));
check('.page.active shown on print', css.includes('.page.active { display: block !important;'));
check('Handoff print rule', css.includes('#page-handoff.active'));
check('Emergency print rule', css.includes('#page-emergency.active'));
check('Card overflow reset for print', css.includes('overflow: visible !important'));
check('Visit prep print page', html.includes('id="page-visit-prep"'));

// ─────────────────────────────────────────────────────────────
// 19. DISCLAIMER & SETUP
// ─────────────────────────────────────────────────────────────
section('Disclaimer & Setup Flow');

check('Disclaimer overlay exists', html.includes('id="disclaimer-overlay"'));
check('Disclaimer checkbox', html.includes('id="disclaimer-check"') || html.includes('type="checkbox"'));
check('Disclaimer accept button', html.includes('id="disclaimer-accept"'));
check('acceptDisclaimer saves to localStorage', /acceptDisclaimer[\s\S]{0,300}save\(|localStorage/.test(js));
check('Setup modal exists', html.includes('id="setup-modal"') || html.includes('id="setup-overlay"') || js.includes('openSetup'));
check('Setup saves profile data', /saveSetup[\s\S]{0,300}profile/.test(js));
check('Profile name shown in sidebar', html.includes('id="sidebar-name"'));

// ─────────────────────────────────────────────────────────────
// 20. ONBOARDING TOOLTIPS
// ─────────────────────────────────────────────────────────────
section('Onboarding Tooltips');

const navItemCount = (html.match(/class="nav-item"/g) || []).length;
const tooltipNavItems = Array.from(js.matchAll(/navItem:\s*(\d+)/g), m => parseInt(m[1]));
check('Tooltip system defined', js.includes('const TOOLTIPS = ['));
check('startTooltips function exists', js.includes('function startTooltips('));
check('Tooltip overlay exists', html.includes('id="tooltip-overlay"') || html.includes('id="tooltip-box"') || html.includes('tooltip'));
tooltipNavItems.forEach((idx, i) => {
  if (idx !== null) check(`Tooltip ${i} navItem ${idx} in range (0–${navItemCount-1})`, idx < navItemCount);
});

// ─────────────────────────────────────────────────────────────
// 21. CSS & RESPONSIVE
// ─────────────────────────────────────────────────────────────
section('CSS & Responsive Design');

check('CSS variables defined (:root)', css.includes(':root'));
check('Mobile breakpoint defined', css.includes('@media') && (css.includes('768px') || css.includes('600px')));
check('Sidebar collapses on mobile', css.includes('.sidebar') && css.includes('transform'));
check('fadeIn animation defined', css.includes('@keyframes fadeIn'));
check('.page.active uses animation', css.includes('.page.active'));
check('Toast notification CSS', css.includes('.toast'));
check('Card styles defined', css.includes('.card'));
check('Button styles defined', css.includes('.btn'));
check('Grid layouts defined', css.includes('.grid-2') || css.includes('.grid-3'));
check('Stat card styles', css.includes('.stat-card'));
check('Print color adjust', css.includes('print-color-adjust'));
check('No orphaned animation', (() => {
  const lines = css.split('\n');
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes('animation: fadeIn')) {
      const ctx = lines.slice(Math.max(0, i - 3), i).join('\n');
      if (!ctx.includes('.page.active')) return false;
    }
  }
  return true;
})());

// ─────────────────────────────────────────────────────────────
// 22. PWA META TAGS
// ─────────────────────────────────────────────────────────────
section('PWA & Mobile Meta Tags');

check('Viewport meta tag', html.includes('name="viewport"'));
check('Theme color meta tag', html.includes('name="theme-color"'));
check('Apple mobile web app capable', html.includes('apple-mobile-web-app-capable'));
check('Apple status bar style', html.includes('apple-mobile-web-app-status-bar-style'));
check('Apple mobile title', html.includes('apple-mobile-web-app-title'));
check('Apple touch icon link', html.includes('rel="apple-touch-icon"'));
check('Manifest link present', html.includes('rel="manifest"'));
check('Favicon defined', html.includes('rel="icon"'));
check('Lang attribute on html', html.includes('lang="en"'));
check('Charset UTF-8', html.includes('charset="UTF-8"'));

// PWA Install Infrastructure
check('initPWA function defined', js.includes('function initPWA') || js.includes('initPWA()'));
check('Service worker registration', js.includes("serviceWorker' in navigator") || js.includes('"serviceWorker" in navigator'));
check('Manifest blob created', js.includes('application/json') && js.includes('createObjectURL'));
check('beforeinstallprompt handled', js.includes('beforeinstallprompt'));
check('iOS detection present', js.includes('iphone|ipad|ipod') || js.includes('iphone') && js.includes('ipad'));
check('Standalone mode check', js.includes('display-mode: standalone') || js.includes('standalone'));
check('PWA banner in HTML', html.includes('id="pwa-banner"'));
check('PWA install button', html.includes('pwa-btn-install'));
check('PWA dismiss button', html.includes('pwa-btn-dismiss'));
check('PWA dismissed flag in localStorage', js.includes('cc_pwa_dismissed'));
check('Banner hidden when already installed', js.includes('isStandalone') || js.includes('display-mode: standalone'));
check('PWA banner excluded from print', css.includes('#pwa-banner') && css.includes('@media print'));

// ─────────────────────────────────────────────────────────────
// 23. ACCESSIBILITY
// ─────────────────────────────────────────────────────────────
section('Accessibility');

const ariaLabels = (html.match(/aria-label=/g) || []).length;
check(`aria-label attributes present (${ariaLabels} found)`, ariaLabels >= 8);
check('Edit buttons have aria-label', html.includes('aria-label="Edit'));
check('Delete buttons have aria-label', html.includes('aria-label="Delete'));
check('Mood buttons have accessible text', html.includes('aria-label') || html.includes('title='));
check('Form labels present', (html.match(/<label>/g) || []).length > 10);
check('Input placeholders present', (html.match(/placeholder=/g) || []).length > 10);

// Font size check
const fontSizes = Array.from(css.matchAll(/font-size:\s*([\d.]+)(px|rem)/g), m => ({
  size: parseFloat(m[1]), unit: m[2]
}));
const smallFonts = fontSizes.filter(f => (f.unit === 'px' && f.size < 11) || (f.unit === 'rem' && f.size < 0.7));
if (smallFonts.length === 0) check('No critically small fonts (<11px)', true);
else warn(`${smallFonts.length} very small font sizes found`, 'may be hard to read on mobile');

check('Body font size ≥ 16px', /body[\s\S]{0,200}font-size:\s*1[6-9]px|font-size:\s*[2-9]\d+px|font-size:\s*1[89]px|font-size:\s*18px/.test(css));

// ─────────────────────────────────────────────────────────────
// 24. RENDERALL WIRING
// ─────────────────────────────────────────────────────────────
section('renderAll() Wiring');

const renderAllBody = (() => {
  const m = js.match(/function renderAll\(\)\s*\{([\s\S]*?)\n\}/);
  return m ? m[1] : '';
})();

[
  'renderDashboard','renderMedications','renderSymptomLog',
  'renderAppointments','renderCareTeam','renderHandoff',
  'renderMemories','renderStress','renderDataSummary',
  'renderCharts','renderGoodDays','renderRefillAlerts',
].forEach(fn => check(`renderAll calls ${fn}`, renderAllBody.includes(fn + '()')));

// ─────────────────────────────────────────────────────────────
// 25. NO DUPLICATE FUNCTION DEFINITIONS
// ─────────────────────────────────────────────────────────────
section('No Duplicate Function Definitions');

[
  'renderDashboard','renderMedications','renderSymptomLog','renderAppointments',
  'renderCareTeam','renderHandoff','renderMemories','renderStress',
  'renderCharts','renderGoodDays','renderRefillAlerts','addAppointment',
  'addMedication','addLogEntry','addContact','addHandoff','addMemory',
].forEach(fn => {
  const count = (js.match(new RegExp(`^function ${fn}\\(`, 'mg')) || []).length;
  check(`No duplicate ${fn}()`, count <= 1, count > 1 ? `found ${count} definitions` : '');
});

// ─────────────────────────────────────────────────────────────
// SUMMARY
// ─────────────────────────────────────────────────────────────
console.log('\n══════════════════════════════════════════════════');
console.log(`  RESULT: ${passed} passed, ${failed} failed, ${warned} warnings`);
console.log('══════════════════════════════════════════════════');

if (failures.length) {
  console.log('\n🚨 FAILURES (must fix):');
  failures.forEach((f, i) => console.log(`  ${i+1}. ${f}`));
}
if (warnings.length) {
  console.log('\n⚠️  WARNINGS (review):');
  warnings.forEach((w, i) => console.log(`  ${i+1}. ${w}`));
}

const score = Math.round((passed / (passed + failed)) * 100);
const rating = failed === 0 ? '✅ READY' : failed <= 3 ? '⚠️  NEEDS WORK' : '🚫 NOT READY';
console.log(`\n  SCORE: ${score}%  |  MARKETING READINESS: ${rating}`);
console.log('══════════════════════════════════════════════════\n');

process.exit(failed > 0 ? 1 : 0);
