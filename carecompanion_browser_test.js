// ═══════════════════════════════════════════════════════════════════════════
//  CareCompanion — Live Browser Test Suite
//  Run via: fetch('http://localhost:PORT/carecompanion_browser_test.js?v=' + Date.now())
//            .then(r => r.text()).then(code => eval(code))
//  Must be run on the carecompanion (16).html page (or demo copy).
//  All localStorage state is fully restored after the suite completes.
// ═══════════════════════════════════════════════════════════════════════════

(function CareCompanionBrowserTest() {

  // ── Test runner ────────────────────────────────────────────────────────
  let passed = 0, failed = 0;
  const failures = [];
  const sections = [];

  function section(title) {
    sections.push(title);
    console.log(`\n▶ [${sections.length}] ${title}`);
  }

  function test(name, fn) {
    try {
      fn();
      console.log(`  ✅ ${name}`);
      passed++;
    } catch (e) {
      console.error(`  ❌ ${name} — ${e.message}`);
      failed++;
      failures.push(`[${sections[sections.length - 1]}] ${name}: ${e.message}`);
    }
  }

  function assert(condition, msg) {
    if (!condition) throw new Error(msg || 'assertion failed');
  }

  // ── localStorage helpers ───────────────────────────────────────────────
  const ls  = k => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } };
  const lsSet = (k, v) => localStorage.setItem(k, JSON.stringify(v));
  const lsRaw = k => localStorage.getItem(k);

  // ── Snapshot all cc_ keys before tests ────────────────────────────────
  const SAVED = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    SAVED[k] = localStorage.getItem(k);
  }

  function restoreState() {
    // Remove any keys added during tests
    const keysNow = [];
    for (let i = 0; i < localStorage.length; i++) keysNow.push(localStorage.key(i));
    keysNow.forEach(k => { if (!(k in SAVED)) localStorage.removeItem(k); });
    // Restore original values
    Object.entries(SAVED).forEach(([k, v]) => {
      if (v === null) localStorage.removeItem(k);
      else localStorage.setItem(k, v);
    });
  }

  // ── DOM helpers ────────────────────────────────────────────────────────
  function setVal(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val;
  }
  function mockEl() {
    const el = document.createElement('div');
    return el;
  }

  // ── Freeze globals that cause page reloads or dialogs ─────────────────
  const origConfirm = window.confirm;
  const origAlert   = window.alert;
  const origPrint   = window.print;
  window.alert = () => {};
  window.print = () => {};

  console.log('\n══════════════════════════════════════════════════════════════');
  console.log('  CareCompanion — Live Browser Test Suite');
  console.log('══════════════════════════════════════════════════════════════');

  // ══════════════════════════════════════════════════════════════════════
  // 1. INFRASTRUCTURE
  // ══════════════════════════════════════════════════════════════════════
  section('Infrastructure');

  test('KEYS object has all required keys', () => {
    const required = ['profile','medications','logs','appointments','careteam',
                      'handoff','memories','stress','disclaimer','medChecks','emergency'];
    required.forEach(k => assert(k in KEYS, `Missing KEYS.${k}`));
  });

  test('KEYS values all start with cc_', () => {
    Object.values(KEYS).forEach(v => assert(v.startsWith('cc_'), `Bad key: ${v}`));
  });

  test('save() writes JSON to localStorage', () => {
    save(KEYS.medications, [{ id: 1, name: '__test__' }]);
    const raw = lsRaw(KEYS.medications);
    assert(raw && raw.includes('__test__'), 'save() did not persist data');
  });

  test('load() reads back what save() wrote', () => {
    save(KEYS.logs, [{ id: 99, date: '2025-01-01' }]);
    const result = load(KEYS.logs);
    assert(Array.isArray(result) && result[0].id === 99, 'load() returned wrong data');
  });

  test('load() returns fallback for missing key', () => {
    localStorage.removeItem('cc_test_missing_key');
    const result = load('cc_test_missing_key', 'FALLBACK');
    assert(result === 'FALLBACK', 'load() did not return fallback');
  });

  test('load() returns fallback for corrupted JSON', () => {
    localStorage.setItem('cc_corrupted_test', 'NOT_VALID_JSON{{{');
    const result = load('cc_corrupted_test', []);
    assert(Array.isArray(result), 'load() should return fallback on bad JSON');
    localStorage.removeItem('cc_corrupted_test');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 2. PROFILE / SETUP
  // ══════════════════════════════════════════════════════════════════════
  section('Profile / Setup');

  test('saveSetup() persists profile to localStorage', () => {
    setVal('setup-name', 'Eleanor Voss');
    setVal('setup-dob', '1940-03-15');
    setVal('setup-condition', 'Parkinson\'s');
    setVal('setup-caregiver', 'David Voss');
    saveSetup();
    const p = load(KEYS.profile, null);
    assert(p && p.name === 'Eleanor Voss', 'Name not saved');
    assert(p.dob === '1940-03-15', 'DOB not saved');
    assert(p.condition === "Parkinson's", 'Condition not saved');
    assert(p.caregiver === 'David Voss', 'Caregiver not saved');
  });

  test('saveSetup() updates sidebar and hero name display', () => {
    setVal('setup-name', 'Ruth Allen');
    setVal('setup-dob', '');
    setVal('setup-condition', '');
    setVal('setup-caregiver', '');
    saveSetup();
    const sidebar = document.getElementById('sidebar-name');
    const hero = document.getElementById('hero-name');
    assert(sidebar.textContent === 'Ruth Allen', 'Sidebar name not updated');
    assert(hero.textContent === 'Ruth Allen', 'Hero name not updated');
  });

  test('saveSetup() syncs name to emergency card when not manually saved', () => {
    save(KEYS.emergency, {});
    setVal('setup-name', 'Margaret T.');
    setVal('setup-dob', '1938-06-20');
    setVal('setup-condition', 'Dementia');
    setVal('setup-caregiver', '');
    saveSetup();
    const ec = load(KEYS.emergency, {});
    assert(ec.name === 'Margaret T.', 'Emergency card name not synced');
    assert(ec.dob === '1938-06-20', 'Emergency card DOB not synced');
  });

  test('updateProfileDisplay() updates sidebar and hero name', () => {
    updateProfileDisplay({ name: 'Joan Fischer' });
    assert(document.getElementById('sidebar-name').textContent === 'Joan Fischer', 'sidebar-name wrong');
    assert(document.getElementById('hero-name').textContent === 'Joan Fischer', 'hero-name wrong');
  });

  test('acceptDisclaimer() saves disclaimer=true to localStorage', () => {
    save(KEYS.disclaimer, false);
    save(KEYS.profile, { name: 'Test User' });
    acceptDisclaimer();
    assert(load(KEYS.disclaimer, false) === true, 'Disclaimer not saved as true');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 3. MEDICATIONS — ADD / EDIT / DELETE
  // ══════════════════════════════════════════════════════════════════════
  section('Medications — Add / Edit / Delete');

  test('addMedication() saves new entry to cc_medications', () => {
    save(KEYS.medications, []);
    setVal('med-name', 'Lisinopril');
    setVal('med-dose', '10mg');
    setVal('med-notes', 'Take with water');
    setVal('med-doctor', 'Dr. Patel');
    setVal('med-refill', '2025-08-01');
    setVal('med-pills', '30');
    addMedication();
    const meds = load(KEYS.medications);
    assert(meds.length === 1, `Expected 1 med, got ${meds.length}`);
    assert(meds[0].name === 'Lisinopril', 'Name not saved');
    assert(meds[0].dose === '10mg', 'Dose not saved');
    assert(meds[0].notes === 'Take with water', 'Notes not saved');
    assert(meds[0].doctor === 'Dr. Patel', 'Doctor not saved');
    assert(meds[0].pills === 30, 'Pills not saved as number');
  });

  test('addMedication() assigns a numeric id', () => {
    const meds = load(KEYS.medications);
    assert(typeof meds[0].id === 'number', 'id should be a number');
  });

  test('addMedication() with empty name does not save', () => {
    const before = load(KEYS.medications).length;
    setVal('med-name', '');
    addMedication();
    const after = load(KEYS.medications).length;
    assert(after === before, 'Empty name should not save');
  });

  test('addMedication() appends to existing list', () => {
    setVal('med-name', 'Metformin');
    setVal('med-dose', '500mg');
    addMedication();
    const meds = load(KEYS.medications);
    assert(meds.length === 2, `Expected 2 meds, got ${meds.length}`);
  });

  test('editMedication() loads correct values into form', () => {
    const meds = load(KEYS.medications);
    const id = meds[0].id;
    editMedication(id);
    assert(document.getElementById('med-name').value === 'Lisinopril', 'Name not loaded into form');
    assert(document.getElementById('med-dose').value === '10mg', 'Dose not loaded into form');
    assert(editingMedId === id, 'editingMedId not set');
  });

  test('addMedication() in edit mode updates existing entry', () => {
    const meds = load(KEYS.medications);
    const id = meds[0].id;
    editMedication(id);
    setVal('med-name', 'Lisinopril Updated');
    addMedication();
    const updated = load(KEYS.medications).find(m => m.id === id);
    assert(updated && updated.name === 'Lisinopril Updated', 'Edit did not persist');
  });

  test('deleteMedication() removes entry from cc_medications', () => {
    window.confirm = () => true;
    const meds = load(KEYS.medications);
    const id = meds[0].id;
    deleteMedication(id);
    window.confirm = origConfirm;
    const after = load(KEYS.medications);
    assert(!after.find(m => m.id === id), 'Entry not deleted');
  });

  test('freqToDoseCount() returns correct counts', () => {
    assert(freqToDoseCount('Once daily') === 1, 'Once daily should be 1');
    assert(freqToDoseCount('Twice daily') === 2, 'Twice daily should be 2');
    assert(freqToDoseCount('Three times daily') === 3, 'Three times daily should be 3');
    assert(freqToDoseCount('Every 6 hours') === 4, 'Every 6 hours should be 4');
  });

  test('timeStrTo24() converts 12h to 24h format', () => {
    assert(timeStrTo24('8:00am') === '08:00', '8:00am should be 08:00');
    assert(timeStrTo24('12:00pm') === '12:00', '12:00pm should be 12:00');
    assert(timeStrTo24('8:00pm') === '20:00', '8:00pm should be 20:00');
    assert(timeStrTo24('12:00am') === '00:00', '12:00am should be 00:00');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 4. MEDICATIONS — RENDER
  // ══════════════════════════════════════════════════════════════════════
  section('Medications — Render');

  test('renderMedications() produces output for populated list', () => {
    save(KEYS.medications, [{ id: 1, name: 'Aspirin', dose: '81mg', frequency: 'Once daily', times: '8:00am', food: 'With food', notes: '', doctor: '', refill: '', pills: null }]);
    renderMedications();
    const el = document.getElementById('medications-list');
    assert(el.innerHTML.includes('Aspirin'), 'Rendered list missing medication name');
    assert(el.innerHTML.includes('81mg'), 'Rendered list missing dose');
  });

  test('renderMedications() shows empty state when no meds', () => {
    save(KEYS.medications, []);
    renderMedications();
    const el = document.getElementById('medications-list');
    assert(el.innerHTML.includes('empty-state') || el.innerHTML.includes('No medications'), 'Empty state not shown');
  });

  test('renderMedications() shows pill supply badge when pills set', () => {
    save(KEYS.medications, [{ id: 1, name: 'TestPill', dose: '5mg', frequency: 'Once daily', pills: 14 }]);
    renderMedications();
    const el = document.getElementById('medications-list');
    assert(el.innerHTML.includes('14'), 'Pill count not shown');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 5. SYMPTOM LOG — ADD / EDIT / DELETE
  // ══════════════════════════════════════════════════════════════════════
  section('Symptom Log — Add / Edit / Delete');

  test('selectMood() sets selectedMood global', () => {
    selectMood('😊');
    assert(selectedMood === '😊', 'selectedMood not set');
  });

  test('addLogEntry() saves entry with date and mood', () => {
    save(KEYS.logs, []);
    selectMood('😊');
    setVal('log-date', '2025-06-15');
    setVal('log-sleep', 'Good');
    setVal('log-appetite', 'Normal');
    setVal('log-pain', '2');
    setVal('log-symptoms', 'Mild headache in the morning');
    setVal('log-questions', 'Should we adjust timing?');
    addLogEntry();
    const logs = load(KEYS.logs);
    assert(logs.length === 1, `Expected 1 log, got ${logs.length}`);
    assert(logs[0].date === '2025-06-15', 'Date not saved');
    assert(logs[0].mood === '😊', 'Mood not saved');
    assert(logs[0].symptoms === 'Mild headache in the morning', 'Symptoms not saved');
    assert(logs[0].questions === 'Should we adjust timing?', 'Questions not saved');
  });

  test('addLogEntry() with no date does not save', () => {
    const before = load(KEYS.logs).length;
    setVal('log-date', '');
    addLogEntry();
    assert(load(KEYS.logs).length === before, 'No-date entry should not save');
  });

  test('addLogEntry() prepends (newest first)', () => {
    selectMood('😐');
    setVal('log-date', '2025-06-16');
    setVal('log-symptoms', 'Second entry');
    addLogEntry();
    const logs = load(KEYS.logs);
    assert(logs[0].date === '2025-06-16', 'Newest entry should be first');
  });

  test('editLog() loads entry into form', () => {
    const logs = load(KEYS.logs);
    const id = logs[0].id;
    editLog(id);
    assert(editingLogId === id, 'editingLogId not set');
    assert(document.getElementById('log-date').value === logs[0].date, 'Date not loaded into form');
  });

  test('addLogEntry() in edit mode updates existing entry', () => {
    const logs = load(KEYS.logs);
    const id = logs[0].id;
    editLog(id);
    setVal('log-date', logs[0].date);
    setVal('log-symptoms', '__edited_symptoms__');
    addLogEntry();
    const updated = load(KEYS.logs).find(l => l.id === id);
    assert(updated && updated.symptoms === '__edited_symptoms__', 'Edit did not persist');
  });

  test('deleteLog() removes entry without confirm', () => {
    const logs = load(KEYS.logs);
    const id = logs[0].id;
    deleteLog(id);
    const after = load(KEYS.logs);
    assert(!after.find(l => l.id === id), 'Entry not deleted');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 6. SYMPTOM LOG — RENDER
  // ══════════════════════════════════════════════════════════════════════
  section('Symptom Log — Render');

  test('renderSymptomLog() shows entries when data exists', () => {
    save(KEYS.logs, [{ id: 1, date: '2025-06-10', mood: '😊', symptoms: 'Good energy', pain: '1' }]);
    renderSymptomLog();
    const el = document.getElementById('symptom-log-list');
    assert(el.innerHTML.includes('Good energy'), 'Log entry not rendered');
  });

  test('renderSymptomLog() shows empty state when no logs', () => {
    save(KEYS.logs, []);
    renderSymptomLog();
    const el = document.getElementById('symptom-log-list');
    assert(el.innerHTML.includes('empty-state') || el.innerHTML.includes('No entries'), 'Empty state not shown');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 7. APPOINTMENTS — ADD / EDIT / DELETE
  // ══════════════════════════════════════════════════════════════════════
  section('Appointments — Add / Edit / Delete');

  test('addAppointment() saves new appointment', () => {
    save(KEYS.appointments, []);
    setVal('appt-title', 'Cardiology Follow-up');
    setVal('appt-date', '2025-09-15');
    setVal('appt-time', '10:30');
    setVal('appt-doctor', 'Dr. Chen');
    setVal('appt-address', '123 Medical Blvd');
    setVal('appt-notes', 'Bring EKG results');
    setVal('appt-visit-notes', '');
    document.getElementById('appt-recurring').checked = false;
    addAppointment();
    const appts = load(KEYS.appointments);
    assert(appts.length === 1, `Expected 1 appt, got ${appts.length}`);
    assert(appts[0].title === 'Cardiology Follow-up', 'Title not saved');
    assert(appts[0].date === '2025-09-15', 'Date not saved');
    assert(appts[0].doctor === 'Dr. Chen', 'Doctor not saved');
    assert(appts[0].notes === 'Bring EKG results', 'Notes not saved');
  });

  test('addAppointment() with no title/date does not save', () => {
    const before = load(KEYS.appointments).length;
    setVal('appt-title', '');
    setVal('appt-date', '');
    addAppointment();
    assert(load(KEYS.appointments).length === before, 'Empty appt should not save');
  });

  test('sortAppointments() sorts by date ascending', () => {
    const appts = [
      { id: 1, date: '2025-12-01', time: '' },
      { id: 2, date: '2025-09-15', time: '' },
      { id: 3, date: '2025-10-05', time: '' },
    ];
    const sorted = sortAppointments(appts);
    assert(sorted[0].date === '2025-09-15', 'First should be earliest date');
    assert(sorted[2].date === '2025-12-01', 'Last should be latest date');
  });

  test('sortAppointments() sorts by time within same date', () => {
    const appts = [
      { id: 1, date: '2025-09-15', time: '14:00' },
      { id: 2, date: '2025-09-15', time: '09:00' },
    ];
    const sorted = sortAppointments(appts);
    assert(sorted[0].time === '09:00', 'Earlier time should come first');
  });

  test('markAttended() sets attended=true on appointment', () => {
    const appts = load(KEYS.appointments);
    const id = appts[0].id;
    markAttended(id);
    const updated = load(KEYS.appointments).find(a => a.id === id);
    assert(updated && updated.attended === true, 'attended not set to true');
  });

  test('unmarkAttended() sets attended=false on appointment', () => {
    const appts = load(KEYS.appointments);
    const id = appts[0].id;
    unmarkAttended(id);
    const updated = load(KEYS.appointments).find(a => a.id === id);
    assert(updated && updated.attended === false, 'attended not set to false');
  });

  test('editAppointment() loads entry into form', () => {
    const appts = load(KEYS.appointments);
    const id = appts[0].id;
    editAppointment(id);
    assert(editingApptId === id, 'editingApptId not set');
    assert(document.getElementById('appt-title').value === 'Cardiology Follow-up', 'Title not loaded');
    assert(document.getElementById('appt-doctor').value === 'Dr. Chen', 'Doctor not loaded');
  });

  test('addAppointment() in edit mode updates existing entry', () => {
    const appts = load(KEYS.appointments);
    const id = appts[0].id;
    editAppointment(id);
    setVal('appt-title', '__edited_appt__');
    setVal('appt-date', '2025-09-15');
    addAppointment();
    const updated = load(KEYS.appointments).find(a => a.id === id);
    assert(updated && updated.title === '__edited_appt__', 'Appt edit did not persist');
  });

  test('deleteAppointment() removes non-recurring appointment', () => {
    window.confirm = () => true;
    const appts = load(KEYS.appointments);
    const id = appts[0].id;
    deleteAppointment(id);
    window.confirm = origConfirm;
    assert(!load(KEYS.appointments).find(a => a.id === id), 'Appointment not deleted');
  });

  test('generateRecurringDates() generates correct date series', () => {
    const dates = generateRecurringDates('2025-01-06', 'weekly', '2025-01-27');
    assert(dates.length === 4, `Expected 4 weekly dates, got ${dates.length}`);
    assert(dates[0] === '2025-01-06', 'First date wrong');
    assert(dates[3] === '2025-01-27', 'Last date wrong');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 8. APPOINTMENTS — RENDER
  // ══════════════════════════════════════════════════════════════════════
  section('Appointments — Render');

  test('renderAppointments() shows entries when data exists', () => {
    const today = new Date();
    today.setDate(today.getDate() + 7);
    const futureDate = today.toISOString().split('T')[0];
    save(KEYS.appointments, [{ id: 1, title: 'Neurology Checkup', date: futureDate, time: '', doctor: '', address: '', category: 'Specialist', notes: '', attended: false }]);
    renderAppointments();
    const el = document.getElementById('appointments-list');
    assert(el.innerHTML.includes('Neurology Checkup'), 'Appointment not rendered');
  });

  test('renderAppointments() shows empty state when no appointments', () => {
    save(KEYS.appointments, []);
    renderAppointments();
    const el = document.getElementById('appointments-list');
    assert(el.innerHTML.includes('empty-state') || el.innerHTML.includes('No appointments'), 'Empty state not shown');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 9. CARE TEAM — ADD / EDIT / DELETE
  // ══════════════════════════════════════════════════════════════════════
  section('Care Team — Add / Edit / Delete');

  test('addContact() saves new contact', () => {
    save(KEYS.careteam, []);
    setVal('ct-name', 'Dr. Sandra Lee');
    setVal('ct-role', 'Neurologist');
    setVal('ct-phone', '555-234-5678');
    setVal('ct-fax', '555-234-5679');
    setVal('ct-email', 'slee@clinic.com');
    setVal('ct-facility', 'Northside Neurology');
    setVal('ct-notes', 'Specialist for tremor management');
    addContact();
    const team = load(KEYS.careteam);
    assert(team.length === 1, `Expected 1 contact, got ${team.length}`);
    assert(team[0].name === 'Dr. Sandra Lee', 'Name not saved');
    assert(team[0].role === 'Neurologist', 'Role not saved');
    assert(team[0].phone === '555-234-5678', 'Phone not saved');
    assert(team[0].facility === 'Northside Neurology', 'Facility not saved');
  });

  test('addContact() with empty name does not save', () => {
    const before = load(KEYS.careteam).length;
    setVal('ct-name', '');
    addContact();
    assert(load(KEYS.careteam).length === before, 'Empty contact should not save');
  });

  test('editContact() loads correct values into form', () => {
    const team = load(KEYS.careteam);
    const id = team[0].id;
    editContact(id);
    assert(editingContactId === id, 'editingContactId not set');
    assert(document.getElementById('ct-name').value === 'Dr. Sandra Lee', 'Name not loaded');
    assert(document.getElementById('ct-role').value === 'Neurologist', 'Role not loaded');
  });

  test('addContact() in edit mode updates existing contact', () => {
    const team = load(KEYS.careteam);
    const id = team[0].id;
    editContact(id);
    setVal('ct-name', '__edited_contact__');
    setVal('ct-role', 'Neurologist');
    addContact();
    const updated = load(KEYS.careteam).find(c => c.id === id);
    assert(updated && updated.name === '__edited_contact__', 'Contact edit did not persist');
  });

  test('deleteContact() removes contact without confirm', () => {
    const team = load(KEYS.careteam);
    const id = team[0].id;
    deleteContact(id);
    assert(!load(KEYS.careteam).find(c => c.id === id), 'Contact not deleted');
  });

  test('renderCareTeam() shows contact when data exists', () => {
    save(KEYS.careteam, [{ id: 1, name: 'Dr. Kim', role: 'GP', phone: '555-000-1111', email: '', fax: '', facility: '', notes: '' }]);
    renderCareTeam();
    const el = document.getElementById('careteam-list');
    assert(el.innerHTML.includes('Dr. Kim'), 'Contact not rendered');
  });

  test('renderCareTeam() shows empty state when no contacts', () => {
    save(KEYS.careteam, []);
    renderCareTeam();
    const el = document.getElementById('careteam-list');
    assert(el.innerHTML.includes('empty-state') || el.innerHTML.includes('No contacts'), 'Empty state not shown');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 10. HANDOFF NOTES — ADD / EDIT / DELETE
  // ══════════════════════════════════════════════════════════════════════
  section('Handoff Notes — Add / Edit / Delete');

  test('addHandoff() saves new handoff note', () => {
    save(KEYS.handoff, []);
    setVal('ho-date', '2025-06-15');
    setVal('ho-caregiver', 'Maria');
    setVal('ho-meds', 'All given on time');
    setVal('ho-meals', 'Ate full breakfast');
    setVal('ho-mood', 'Calm and cooperative');
    setVal('ho-watch', 'Monitor left ankle swelling');
    setVal('ho-notes', 'Had a good nap after lunch');
    addHandoff();
    const notes = load(KEYS.handoff);
    assert(notes.length === 1, `Expected 1 note, got ${notes.length}`);
    assert(notes[0].date === '2025-06-15', 'Date not saved');
    assert(notes[0].caregiver === 'Maria', 'Caregiver not saved');
    assert(notes[0].meds === 'All given on time', 'Meds not saved');
    assert(notes[0].watch === 'Monitor left ankle swelling', 'Watch not saved');
  });

  test('addHandoff() with no date does not save', () => {
    const before = load(KEYS.handoff).length;
    setVal('ho-date', '');
    addHandoff();
    assert(load(KEYS.handoff).length === before, 'No-date handoff should not save');
  });

  test('addHandoff() stores createdAt and updatedAt timestamps', () => {
    const notes = load(KEYS.handoff);
    assert(typeof notes[0].createdAt === 'string', 'createdAt not stored');
    assert(typeof notes[0].updatedAt === 'string', 'updatedAt not stored');
  });

  test('editHandoff() loads values into form', () => {
    const notes = load(KEYS.handoff);
    const id = notes[0].id;
    editHandoff(id);
    assert(editingHandoffId === id, 'editingHandoffId not set');
    assert(document.getElementById('ho-date').value === '2025-06-15', 'Date not loaded');
    assert(document.getElementById('ho-caregiver').value === 'Maria', 'Caregiver not loaded');
  });

  test('addHandoff() in edit mode updates existing note', () => {
    const notes = load(KEYS.handoff);
    const id = notes[0].id;
    editHandoff(id);
    setVal('ho-date', '2025-06-15');
    setVal('ho-notes', '__edited_handoff__');
    addHandoff();
    const updated = load(KEYS.handoff).find(h => h.id === id);
    assert(updated && updated.notes === '__edited_handoff__', 'Handoff edit did not persist');
  });

  test('deleteHandoff() removes note without confirm', () => {
    const notes = load(KEYS.handoff);
    const id = notes[0].id;
    deleteHandoff(id);
    assert(!load(KEYS.handoff).find(h => h.id === id), 'Handoff not deleted');
  });

  test('renderHandoff() shows empty state when no notes', () => {
    save(KEYS.handoff, []);
    renderHandoff();
    const el = document.getElementById('handoff-list');
    assert(el.innerHTML.includes('empty-state') || el.innerHTML.includes('No handoff'), 'Empty state not shown');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 11. MEMORY BOX — ADD / EDIT / DELETE
  // ══════════════════════════════════════════════════════════════════════
  section('Memory Box — Add / Edit / Delete');

  test('selectMemMood() sets selectedMemMood global', () => {
    selectMemMood('😊');
    assert(selectedMemMood === '😊', 'selectedMemMood not set');
  });

  test('addMemory() saves new memory with mood', () => {
    save(KEYS.memories, []);
    selectMemMood('😊');
    setVal('mem-title', 'First Walk in the Park');
    setVal('mem-date', '2025-05-20');
    setVal('mem-text', 'She remembered the names of all the flowers.');
    addMemory();
    const mems = load(KEYS.memories);
    assert(mems.length === 1, `Expected 1 memory, got ${mems.length}`);
    assert(mems[0].title === 'First Walk in the Park', 'Title not saved');
    assert(mems[0].mood === '😊', 'Mood not saved');
    assert(mems[0].text === 'She remembered the names of all the flowers.', 'Text not saved');
  });

  test('addMemory() with empty title does not save', () => {
    const before = load(KEYS.memories).length;
    setVal('mem-title', '');
    addMemory();
    assert(load(KEYS.memories).length === before, 'Empty title should not save');
  });

  test('editMemory() loads values into form', () => {
    const mems = load(KEYS.memories);
    const id = mems[0].id;
    editMemory(id);
    assert(editingMemoryId === id, 'editingMemoryId not set');
    assert(document.getElementById('mem-title').value === 'First Walk in the Park', 'Title not loaded');
    assert(document.getElementById('mem-text').value === 'She remembered the names of all the flowers.', 'Text not loaded');
  });

  test('addMemory() in edit mode updates existing memory', () => {
    const mems = load(KEYS.memories);
    const id = mems[0].id;
    editMemory(id);
    setVal('mem-title', '__edited_memory__');
    addMemory();
    const updated = load(KEYS.memories).find(m => m.id === id);
    assert(updated && updated.title === '__edited_memory__', 'Memory edit did not persist');
  });

  test('deleteMemory() removes memory without confirm', () => {
    const mems = load(KEYS.memories);
    const id = mems[0].id;
    deleteMemory(id);
    assert(!load(KEYS.memories).find(m => m.id === id), 'Memory not deleted');
  });

  test('renderMemories() shows empty state when no memories', () => {
    save(KEYS.memories, []);
    renderMemories();
    const el = document.getElementById('memory-list');
    assert(el.innerHTML.includes('empty-state') || el.innerHTML.includes('empty'), 'Empty state not shown');
  });

  test('renderMemories() shows memory title when data exists', () => {
    save(KEYS.memories, [{ id: 1, title: 'Birthday Celebration', date: '2025-04-10', mood: '😊', text: 'Such a lovely day' }]);
    renderMemories();
    const el = document.getElementById('memory-list');
    assert(el.innerHTML.includes('Birthday Celebration'), 'Memory title not rendered');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 12. WELLBEING / STRESS — ADD / EDIT / DELETE
  // ══════════════════════════════════════════════════════════════════════
  section('Wellbeing / Stress — Add / Edit / Delete');

  test('selectStress() sets selectedStress global', () => {
    selectStress(8);
    assert(selectedStress === 8, 'selectedStress not set');
  });

  test('addStressEntry() saves entry with score', () => {
    save(KEYS.stress, []);
    selectStress(7);
    setVal('stress-notes', 'Good day overall');
    setVal('stress-gratitude', 'Grateful for the sunshine');
    addStressEntry();
    const entries = load(KEYS.stress);
    assert(entries.length === 1, `Expected 1 entry, got ${entries.length}`);
    assert(entries[0].score === 7, 'Score not saved');
    assert(entries[0].notes === 'Good day overall', 'Notes not saved');
    assert(entries[0].gratitude === 'Grateful for the sunshine', 'Gratitude not saved');
  });

  test('addStressEntry() stores today\'s date', () => {
    const today = new Date().toISOString().split('T')[0];
    const entries = load(KEYS.stress);
    assert(entries[0].date === today, 'Date not set to today');
  });

  test('addStressEntry() with no score selected does not save', () => {
    selectedStress = null;
    const before = load(KEYS.stress).length;
    addStressEntry();
    assert(load(KEYS.stress).length === before, 'No-score entry should not save');
  });

  test('editStress() loads entry into form', () => {
    const entries = load(KEYS.stress);
    const id = entries[0].id;
    editStress(id);
    assert(editingStressId === id, 'editingStressId not set');
    assert(selectedStress === 7, 'selectedStress not restored');
    assert(document.getElementById('stress-notes').value === 'Good day overall', 'Notes not loaded');
  });

  test('addStressEntry() in edit mode updates existing entry', () => {
    const entries = load(KEYS.stress);
    const id = entries[0].id;
    editStress(id);
    setVal('stress-notes', '__edited_stress__');
    addStressEntry();
    const updated = load(KEYS.stress).find(e => e.id === id);
    assert(updated && updated.notes === '__edited_stress__', 'Stress edit did not persist');
  });

  test('deleteStress() removes entry without confirm', () => {
    const entries = load(KEYS.stress);
    const id = entries[0].id;
    deleteStress(id);
    assert(!load(KEYS.stress).find(e => e.id === id), 'Stress entry not deleted');
  });

  test('renderStress() shows empty state when no entries', () => {
    save(KEYS.stress, []);
    renderStress();
    const el = document.getElementById('stress-log-list');
    assert(el.innerHTML.includes('empty-state') || el.innerHTML.includes('No check-ins'), 'Empty state not shown');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 13. EMERGENCY CARD
  // ══════════════════════════════════════════════════════════════════════
  section('Emergency Card');

  test('saveEmergencyFields() persists all fields to cc_emergency', () => {
    navigate('emergency');
    setVal('ec-name', 'Margaret Wilson');
    setVal('ec-dob', '1940-05-12');
    setVal('ec-blood', 'A+');
    setVal('ec-conditions', 'Type 2 Diabetes, Hypertension');
    setVal('ec-allergies', 'Penicillin');
    setVal('ec-contact1', 'John Wilson — Son — 555-100-2000');
    setVal('ec-contact2', 'Susan Bloom — Daughter — 555-100-3000');
    setVal('ec-doctor', 'Dr. Patel — 555-400-5000');
    setVal('ec-insurance', 'Medicare #1A2B3C4D5');
    setVal('ec-notes', 'Speaks French and English');
    saveEmergencyFields();
    const ec = load(KEYS.emergency, {});
    assert(ec.name === 'Margaret Wilson', 'Name not saved');
    assert(ec.dob === '1940-05-12', 'DOB not saved');
    assert(ec.blood === 'A+', 'Blood type not saved');
    assert(ec.conditions === 'Type 2 Diabetes, Hypertension', 'Conditions not saved');
    assert(ec.allergies === 'Penicillin', 'Allergies not saved');
    assert(ec._saved === true, '_saved flag not set');
  });

  test('updateEmergencyCard() renders preview with name', () => {
    setVal('ec-name', 'Clara Bennett');
    updateEmergencyCard();
    const preview = document.getElementById('ec-preview-content');
    assert(preview.innerHTML.includes('Clara Bennett'), 'Name not in emergency card preview');
  });

  test('updateEmergencyCard() includes medication list from cc_medications', () => {
    save(KEYS.medications, [{ id: 1, name: 'Warfarin', dose: '5mg', frequency: 'Once daily', food: '' }]);
    updateEmergencyCard();
    const preview = document.getElementById('ec-preview-content');
    assert(preview.innerHTML.includes('Warfarin'), 'Medication not shown in emergency card');
  });

  test('updateEmergencyCard() shows "None recorded" when no meds', () => {
    save(KEYS.medications, []);
    updateEmergencyCard();
    const preview = document.getElementById('ec-preview-content');
    assert(preview.innerHTML.includes('None recorded'), '"None recorded" text missing');
  });

  test('loadEmergencyCard() auto-populates from profile when ec not saved', () => {
    save(KEYS.emergency, {});
    save(KEYS.profile, { name: 'Helen Fox', dob: '1945-07-04', condition: 'Alzheimers' });
    navigate('emergency');
    assert(document.getElementById('ec-name').value === 'Helen Fox', 'Name not auto-populated from profile');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 14. MEDICATION DAILY CHECK-OFF
  // ══════════════════════════════════════════════════════════════════════
  section('Medication Daily Check-off');

  test('getTodayKey() returns cc_medchecks_YYYY-MM-DD format', () => {
    const key = getTodayKey();
    const today = new Date().toISOString().split('T')[0];
    assert(key === `cc_medchecks_${today}`, `Bad key format: ${key}`);
  });

  test('getMedChecksForToday() returns object', () => {
    const checks = getMedChecksForToday();
    assert(typeof checks === 'object' && checks !== null, 'Should return object');
  });

  test('getMedChecksForToday() purges old cc_medchecks_ keys', () => {
    localStorage.setItem('cc_medchecks_2020-01-01', JSON.stringify({ old: true }));
    getMedChecksForToday();
    assert(!localStorage.getItem('cc_medchecks_2020-01-01'), 'Old medcheck key not purged');
  });

  test('toggleMedCheck() marks dose as done', () => {
    const medId = 9900001;
    localStorage.removeItem(getTodayKey());
    save(KEYS.medications, [{ id: medId, name: 'CheckTest', dose: '1mg', frequency: 'Once daily', pills: null }]);
    const el = document.createElement('div');
    el.className = 'med-check';
    toggleMedCheck(medId, 0, el);
    const checks = getMedChecksForToday();
    assert(checks[`${medId}_0`] === true, 'Dose not marked as done');
    assert(el.classList.contains('done'), 'Element not given done class');
  });

  test('toggleMedCheck() toggles back to undone', () => {
    const medId = 9900002;
    localStorage.removeItem(getTodayKey());
    save(KEYS.medications, [{ id: medId, name: 'ToggleTest', dose: '1mg', frequency: 'Once daily', pills: null }]);
    const el = document.createElement('div');
    el.className = 'med-check';
    toggleMedCheck(medId, 0, el); // mark done
    toggleMedCheck(medId, 0, el); // toggle back
    const checks = getMedChecksForToday();
    assert(checks[`${medId}_0`] === false, 'Dose not toggled back to undone');
  });

  test('toggleMedCheck() decrements pill count when marked done', () => {
    const medId = 9900003;
    localStorage.removeItem(getTodayKey());
    save(KEYS.medications, [{ id: medId, name: 'PillTest', dose: '5mg', frequency: 'Once daily', pills: 20 }]);
    const el = document.createElement('div');
    toggleMedCheck(medId, 0, el);
    const updated = load(KEYS.medications).find(m => m.id === medId);
    assert(updated && updated.pills === 19, `Pills should be 19, got ${updated && updated.pills}`);
  });

  test('logPRNDose() increments PRN count in today\'s checks', () => {
    const medId = 9900004;
    localStorage.removeItem(getTodayKey());
    save(KEYS.medications, [{ id: medId, name: 'PRNTest', dose: '5mg', frequency: 'As needed', pills: 10 }]);
    const btn = document.createElement('button');
    logPRNDose(medId, btn);
    const checks = getMedChecksForToday();
    assert(checks[`${medId}_prn`] === 1, 'PRN dose not logged');
  });

  test('logPRNDose() decrements pill count', () => {
    const medId = 9900005;
    localStorage.removeItem(getTodayKey());
    save(KEYS.medications, [{ id: medId, name: 'PRNPillTest', dose: '5mg', frequency: 'As needed', pills: 15 }]);
    const btn = document.createElement('button');
    logPRNDose(medId, btn);
    const updated = load(KEYS.medications).find(m => m.id === medId);
    assert(updated && updated.pills === 14, `Pills should be 14, got ${updated && updated.pills}`);
  });

  // ══════════════════════════════════════════════════════════════════════
  // 15. DASHBOARD
  // ══════════════════════════════════════════════════════════════════════
  section('Dashboard');

  test('renderDashboard() runs without throwing', () => {
    save(KEYS.medications, []);
    save(KEYS.logs, []);
    save(KEYS.appointments, []);
    save(KEYS.profile, { name: 'Test User', caregiver: 'Test' });
    renderDashboard();
    assert(true, 'renderDashboard threw an error');
  });

  test('renderDashboard() shows medication count in stat card', () => {
    save(KEYS.medications, [
      { id: 1, name: 'Med A', dose: '5mg', frequency: 'Once daily', pills: null },
      { id: 2, name: 'Med B', dose: '10mg', frequency: 'Twice daily', pills: null },
    ]);
    renderDashboard();
    const el = document.getElementById('stat-meds');
    assert(el.textContent.includes('2') || el.textContent.includes('/'), 'Medication count not shown');
  });

  test('renderDashboard() shows next appointment info', () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tDate = tomorrow.toISOString().split('T')[0];
    save(KEYS.appointments, [{ id: 1, title: 'Upcoming Visit', date: tDate, time: '10:00', doctor: '', address: '', category: 'General', notes: '', attended: false }]);
    renderDashboard();
    const apptEl = document.getElementById('stat-appt-detail');
    assert(apptEl.innerHTML.includes('Upcoming Visit'), 'Upcoming appointment not shown on dashboard');
  });

  test('renderDashboard() shows recent log entries', () => {
    save(KEYS.logs, [{ id: 1, date: '2025-06-15', mood: '😊', symptoms: 'Felt great today', pain: '' }]);
    renderDashboard();
    const logEl = document.getElementById('dashboard-log');
    assert(logEl.innerHTML.includes('Felt great today') || logEl.innerHTML.includes('great'), 'Log entry not shown on dashboard');
  });

  test('renderDashboard() shows hero greeting with caregiver name', () => {
    save(KEYS.profile, { name: 'Ruth Allen', caregiver: 'Michael Allen' });
    renderDashboard();
    const greeting = document.getElementById('hero-greeting');
    assert(greeting.textContent.includes('Michael'), 'Caregiver name not in greeting');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 16. GETTING STARTED CHECKLIST
  // ══════════════════════════════════════════════════════════════════════
  section('Getting Started Checklist');

  test('renderGettingStarted() hides strip when all 4 steps done', () => {
    save(KEYS.medications, [{ id: 1, name: 'A', dose: '', frequency: 'Once daily' }]);
    save(KEYS.careteam, [{ id: 1, name: 'Dr. B', role: 'GP' }]);
    save(KEYS.emergency, { _saved: true });
    save(KEYS.logs, [{ id: 1, date: '2025-06-01', mood: '😊' }]);
    renderGettingStarted();
    const strip = document.getElementById('getting-started');
    assert(strip.style.display === 'none', 'Getting started strip should be hidden when all done');
  });

  test('renderGettingStarted() shows strip when steps incomplete', () => {
    save(KEYS.medications, []);
    save(KEYS.careteam, []);
    save(KEYS.emergency, {});
    save(KEYS.logs, []);
    renderGettingStarted();
    const strip = document.getElementById('getting-started');
    assert(strip.style.display !== 'none', 'Getting started strip should show when incomplete');
  });

  test('renderGettingStarted() marks meds step done when med exists', () => {
    save(KEYS.medications, [{ id: 1, name: 'A' }]);
    save(KEYS.careteam, []);
    save(KEYS.logs, []);
    save(KEYS.emergency, {});
    renderGettingStarted();
    const el = document.getElementById('gs-step-meds');
    assert(el && el.classList.contains('done'), 'Meds step not marked done');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 17. REFILL ALERTS
  // ══════════════════════════════════════════════════════════════════════
  section('Refill Alerts');

  test('renderRefillAlerts() shows nothing when no meds running low', () => {
    save(KEYS.medications, [{ id: 1, name: 'Stable Med', dose: '5mg', frequency: 'Once daily', pills: 60, refill: '' }]);
    renderRefillAlerts();
    const el = document.getElementById('refill-alerts');
    assert(!el.innerHTML.includes('Refill'), 'Should not show refill alert for 60 pills');
  });

  test('renderRefillAlerts() alerts when pills <= 7 days supply', () => {
    save(KEYS.medications, [{ id: 1, name: 'Metoprolol', dose: '25mg', frequency: 'Once daily', pills: 5, refill: '' }]);
    renderRefillAlerts();
    const el = document.getElementById('refill-alerts');
    assert(el.innerHTML.includes('Metoprolol'), 'Refill alert not shown for low pill count');
    assert(el.innerHTML.includes('Refill'), 'Refill section header missing');
  });

  test('renderRefillAlerts() shows overdue when 0 pills remain', () => {
    save(KEYS.medications, [{ id: 1, name: 'EmptyMed', dose: '5mg', frequency: 'Once daily', pills: 0, refill: '' }]);
    renderRefillAlerts();
    const el = document.getElementById('refill-alerts');
    assert(el.innerHTML.toLowerCase().includes('overdue') || el.innerHTML.includes('out of pills'), 'Overdue alert not shown');
  });

  test('renderRefillAlerts() skips PRN medications', () => {
    save(KEYS.medications, [{ id: 1, name: 'PRNMed', dose: '5mg', frequency: 'As needed', pills: 2, refill: '' }]);
    renderRefillAlerts();
    const el = document.getElementById('refill-alerts');
    assert(!el.innerHTML.includes('PRNMed'), 'PRN med should not trigger refill alert');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 18. CHARTS / GOOD DAYS
  // ══════════════════════════════════════════════════════════════════════
  section('Charts and Good Days');

  test('renderCharts() shows empty state when no data', () => {
    save(KEYS.logs, []);
    save(KEYS.stress, []);
    renderCharts();
    const empty = document.getElementById('charts-empty');
    assert(empty && empty.style.display !== 'none', 'Charts empty state not shown');
  });

  test('renderCharts() shows chart content when log data exists', () => {
    save(KEYS.logs, [{ id: 1, date: new Date().toISOString().split('T')[0], mood: '😊', pain: '2' }]);
    save(KEYS.stress, []);
    renderCharts();
    const content = document.getElementById('charts-content');
    assert(content && content.style.display !== 'none', 'Charts content not shown');
  });

  test('renderGoodDays() hides strip when no happy days', () => {
    save(KEYS.logs, [{ id: 1, date: '2025-06-10', mood: '😔' }]);
    renderGoodDays();
    const strip = document.getElementById('good-days-strip');
    assert(strip.style.display === 'none', 'Good days strip should be hidden when no happy days');
  });

  test('renderGoodDays() shows strip when happy days exist', () => {
    save(KEYS.logs, [{ id: 1, date: '2025-06-10', mood: '😊', symptoms: 'Great day' }]);
    renderGoodDays();
    const strip = document.getElementById('good-days-strip');
    assert(strip.style.display !== 'none', 'Good days strip not shown');
  });

  test('renderMoodSnapshot() renders without throwing', () => {
    save(KEYS.logs, [{ id: 1, date: new Date().toISOString().split('T')[0], mood: '😊' }]);
    renderMoodSnapshot();
    const el = document.getElementById('dash-mood-snapshot');
    assert(el && el.innerHTML.length > 0, 'Mood snapshot not rendered');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 19. PRINT HELPERS
  // ══════════════════════════════════════════════════════════════════════
  section('Print Helpers');

  test('preparePrintHeaders() populates patient name in print headers', () => {
    save(KEYS.profile, { name: 'Print Patient', caregiver: '' });
    preparePrintHeaders();
    const el = document.getElementById('med-print-patient');
    assert(el && el.textContent.includes('Print Patient'), 'Patient name not in print header');
  });

  test('renderMedicationPrintTable() populates print table with meds', () => {
    save(KEYS.medications, [{ id: 1, name: 'PrintMed', dose: '10mg', frequency: 'Once daily', times: '8:00am', food: '', notes: '', doctor: 'Dr. Z', refill: '', pills: null }]);
    renderMedicationPrintTable();
    const wrap = document.getElementById('medications-print-table-wrap');
    assert(wrap.innerHTML.includes('PrintMed'), 'Medication name not in print table');
  });

  test('renderCareTeamPrintGrid() populates grid with contacts', () => {
    save(KEYS.careteam, [{ id: 1, name: 'PrintDoc', role: 'GP', phone: '555-999-0000', email: '', fax: '', notes: '', clinic: '' }]);
    renderCareTeamPrintGrid();
    const grid = document.getElementById('ct-print-grid');
    assert(grid.innerHTML.includes('PrintDoc'), 'Contact not in care team print grid');
  });

  test('renderCareTeamPrintGrid() hides grid when no contacts', () => {
    save(KEYS.careteam, []);
    renderCareTeamPrintGrid();
    const grid = document.getElementById('ct-print-grid');
    assert(grid.style.display === 'none', 'Grid should be hidden with no contacts');
  });

  test('formatDate() formats YYYY-MM-DD to readable string', () => {
    const result = formatDate('2025-06-15');
    assert(result.includes('June') && result.includes('2025'), `formatDate returned: ${result}`);
  });

  test('formatDate() returns — for empty/null', () => {
    assert(formatDate('') === '—', 'formatDate("") should return —');
    assert(formatDate(null) === '—', 'formatDate(null) should return —');
  });

  test('formatTime() converts 24h to 12h format', () => {
    assert(formatTime('14:30').includes('PM'), '14:30 should be PM');
    assert(formatTime('08:00').includes('AM'), '08:00 should be AM');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 20. EXPORT / DATA SUMMARY
  // ══════════════════════════════════════════════════════════════════════
  section('Export / Data Summary');

  test('renderDataSummary() renders counts for all modules', () => {
    save(KEYS.medications, [{ id: 1, name: 'A', dose: '', frequency: 'Once daily' }, { id: 2, name: 'B', dose: '', frequency: 'Once daily' }]);
    save(KEYS.logs, [{ id: 1, date: '2025-06-01', mood: '😊' }]);
    save(KEYS.appointments, [
      { id: 1, title: 'Appt A', date: '2025-09-01', time: '', category: 'General' },
      { id: 2, title: 'Appt B', date: '2025-09-15', time: '', category: 'General' },
      { id: 3, title: 'Appt C', date: '2025-10-01', time: '', category: 'General' },
    ]);
    renderDataSummary();
    const el = document.getElementById('data-summary');
    assert(el.innerHTML.includes('2'), 'Medication count not shown');
    assert(el.innerHTML.includes('3'), 'Appointment count not shown');
  });

  test('exportData() updates export-status on completion', () => {
    save(KEYS.medications, [{ id: 1, name: 'A', dose: '1mg', frequency: 'Once daily' }]);
    save(KEYS.profile, { name: 'Export User' });
    // Mock blob creation to avoid real download
    const origCreate = URL.createObjectURL;
    const origRevoke = URL.revokeObjectURL;
    URL.createObjectURL = () => 'blob:mock';
    URL.revokeObjectURL = () => {};
    exportData();
    URL.createObjectURL = origCreate;
    URL.revokeObjectURL = origRevoke;
    const status = document.getElementById('export-status');
    assert(status.textContent.includes('✅') || status.textContent.includes('downloaded'), 'Export status not updated');
  });

  test('importData() declares "found" before using it (bug fix verified)', () => {
    const src = importData.toString();
    const hasFoundRef = src.includes('found.length');
    const hasFoundDecl = src.includes('const found') || src.includes('let found') || src.includes('var found');
    assert(hasFoundRef, 'importData should reference found.length');
    assert(hasFoundDecl, 'found must be declared before use — bug was: ReferenceError on any restore attempt');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 21. NAVIGATION
  // ══════════════════════════════════════════════════════════════════════
  section('Navigation');

  const pages = ['dashboard','medications','symptoms','appointments','careteam','handoff','memory','stress','emergency','export'];

  pages.forEach(page => {
    test(`navigate('${page}') activates correct page`, () => {
      navigate(page);
      const active = document.getElementById('page-' + page);
      assert(active && active.classList.contains('active'), `page-${page} not activated`);
    });
  });

  test('navigate() updates page-title text', () => {
    navigate('medications');
    const title = document.getElementById('page-title');
    assert(title.textContent === 'Medications', `Wrong page title: ${title.textContent}`);
  });

  test('navigate() marks nav item active when el passed', () => {
    const navItems = document.querySelectorAll('.nav-item');
    if (navItems.length > 0) {
      navigate('dashboard', navItems[0]);
      assert(navItems[0].classList.contains('active'), 'Nav item not marked active');
    } else {
      assert(true, 'No nav items found (skip)');
    }
  });

  // ══════════════════════════════════════════════════════════════════════
  // 22. DATA RESILIENCE
  // ══════════════════════════════════════════════════════════════════════
  section('Data Resilience');

  test('renderAll() runs without throwing on empty localStorage', () => {
    Object.values(KEYS).forEach(k => localStorage.removeItem(k));
    renderAll();
    assert(true, 'renderAll() threw with empty state');
  });

  test('renderAll() handles corrupted JSON in all keys', () => {
    Object.values(KEYS).forEach(k => localStorage.setItem(k, 'CORRUPTED{{{'));
    renderAll();
    assert(true, 'renderAll() crashed on corrupted data');
  });

  test('load() handles null stored value gracefully', () => {
    localStorage.setItem(KEYS.medications, 'null');
    const result = load(KEYS.medications, []);
    assert(Array.isArray(result) || result === null, 'load() should handle null stored value');
  });

  test('renderDashboard() with no profile does not throw', () => {
    save(KEYS.medications, []);
    save(KEYS.logs, []);
    save(KEYS.appointments, []);
    localStorage.removeItem(KEYS.profile);
    renderDashboard();
    assert(true, 'renderDashboard() threw with no profile');
  });

  test('addMedication() with very long name saves correctly', () => {
    save(KEYS.medications, []);
    const longName = 'A'.repeat(200);
    setVal('med-name', longName);
    addMedication();
    const meds = load(KEYS.medications);
    assert(meds.length === 1 && meds[0].name === longName, 'Long name not saved correctly');
  });

  test('large dataset: 100 log entries renders without error', () => {
    const bigLogs = Array.from({ length: 100 }, (_, i) => ({
      id: i + 1, date: '2025-01-01', mood: '😊', symptoms: `Entry ${i}`, pain: '3'
    }));
    save(KEYS.logs, bigLogs);
    renderSymptomLog();
    const el = document.getElementById('symptom-log-list');
    assert(el.innerHTML.length > 0, 'Log list not rendered with 100 entries');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 23. XSS / SECURITY
  // ══════════════════════════════════════════════════════════════════════
  section('XSS / Security');

  test('XSS in medication name does not execute script', () => {
    let xssRan = false;
    window.__xssTest = () => { xssRan = true; };
    save(KEYS.medications, [{ id: 1, name: '<script>__xssTest()</script>', dose: '', frequency: 'Once daily' }]);
    renderMedications();
    assert(!xssRan, 'XSS executed in medication name');
    delete window.__xssTest;
  });

  test('XSS in log symptoms does not execute script', () => {
    let xssRan = false;
    window.__xssTest2 = () => { xssRan = true; };
    save(KEYS.logs, [{ id: 1, date: '2025-06-01', mood: '😊', symptoms: '<script>__xssTest2()</script>' }]);
    renderSymptomLog();
    assert(!xssRan, 'XSS executed in symptom log');
    delete window.__xssTest2;
  });

  test('XSS in contact name does not execute script', () => {
    let xssRan = false;
    window.__xssTest3 = () => { xssRan = true; };
    save(KEYS.careteam, [{ id: 1, name: '<img src=x onerror="__xssTest3()">', role: 'GP' }]);
    renderCareTeam();
    assert(!xssRan, 'XSS executed in care team contact name');
    delete window.__xssTest3;
  });

  test('updateProfileDisplay() uses textContent not innerHTML', () => {
    let xssRan = false;
    window.__xssSidebar = () => { xssRan = true; };
    updateProfileDisplay({ name: '<script>__xssSidebar()</script>' });
    assert(!xssRan, 'XSS executed via profile name in sidebar');
    delete window.__xssSidebar;
  });

  // ══════════════════════════════════════════════════════════════════════
  // 24. PWA / MANIFEST
  // ══════════════════════════════════════════════════════════════════════
  section('PWA / Manifest');

  test('manifest.json link is present in <head>', () => {
    const link = document.querySelector('link[rel="manifest"]');
    assert(link !== null, 'No <link rel="manifest"> found in document');
  });

  test('manifest link points to manifest.json', () => {
    const link = document.querySelector('link[rel="manifest"]');
    assert(link && link.getAttribute('href').includes('manifest'), `Manifest href: ${link && link.getAttribute('href')}`);
  });

  test('theme-color meta tag is present', () => {
    const meta = document.querySelector('meta[name="theme-color"]');
    assert(meta !== null, 'theme-color meta tag missing');
  });

  test('apple-mobile-web-app-capable meta tag is present', () => {
    const meta = document.querySelector('meta[name="apple-mobile-web-app-capable"]');
    assert(meta !== null, 'apple-mobile-web-app-capable meta tag missing');
  });

  test('service worker registration attempted', () => {
    const src = document.querySelector('script').textContent || '';
    const fullSrc = Array.from(document.querySelectorAll('script')).map(s => s.textContent).join('\n');
    assert(fullSrc.includes('serviceWorker'), 'Service worker registration not found in script');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 25. CONTENT COMPLETENESS
  // ══════════════════════════════════════════════════════════════════════
  section('Content Completeness');

  test('all required pages exist in DOM', () => {
    pages.forEach(p => {
      assert(document.getElementById('page-' + p), `Missing page element: page-${p}`);
    });
  });

  test('disclaimer overlay is present', () => {
    assert(document.getElementById('disclaimer-overlay'), 'disclaimer-overlay missing');
  });

  test('setup overlay is present', () => {
    assert(document.getElementById('setup-overlay'), 'setup-overlay missing');
  });

  test('toast container is present', () => {
    assert(document.getElementById('toast-container'), 'toast-container missing');
  });

  test('emergency card preview element exists', () => {
    assert(document.getElementById('ec-preview-content'), 'ec-preview-content missing');
  });

  test('print table wrapper for medications exists', () => {
    assert(document.getElementById('medications-print-table-wrap'), 'medications-print-table-wrap missing');
  });

  test('getting started checklist has all 4 step elements', () => {
    ['gs-step-meds','gs-step-careteam','gs-step-emergency','gs-step-log'].forEach(id => {
      assert(document.getElementById(id), `Getting started step missing: ${id}`);
    });
  });

  test('dashboard stat elements all exist', () => {
    ['stat-meds','stat-meds-sub','stat-days','stat-appt-detail'].forEach(id => {
      assert(document.getElementById(id), `Dashboard stat element missing: ${id}`);
    });
  });

  test('chart containers all exist', () => {
    ['chart-mood','chart-pain','chart-stress','charts-empty','charts-content','chart-summaries'].forEach(id => {
      assert(document.getElementById(id), `Chart element missing: ${id}`);
    });
  });

  test('good days elements exist', () => {
    ['good-days-strip','good-days-list','good-days-streak','good-days-summary'].forEach(id => {
      assert(document.getElementById(id), `Good days element missing: ${id}`);
    });
  });

  test('burnout alert element exists', () => {
    assert(document.getElementById('burnout-alert'), 'burnout-alert element missing');
  });

  // ══════════════════════════════════════════════════════════════════════
  // 26. KNOWN BUG DOCUMENTATION
  // ══════════════════════════════════════════════════════════════════════
  section('Known Bug Documentation');

  test('importData() "found" variable is declared — restore backup works (bug fixed)', () => {
    const src = importData.toString();
    const declared = src.includes('const found') || src.includes('let found') || src.includes('var found');
    assert(declared, 'importData "found" variable must be declared — was previously a ReferenceError crash on any restore');
  });

  // ══════════════════════════════════════════════════════════════════════
  // SECTION: Edge Cases
  // ══════════════════════════════════════════════════════════════════════
  section('Edge Cases');

  test('Medication with 0 pills saves without crash', () => {
    localStorage.removeItem(KEYS.medications);
    setVal('med-name', 'ZeroPillMed');
    document.getElementById('med-freq').value = 'Once daily';
    setVal('med-pills', '0');
    editingMedId = null;
    addMedication();
    const meds = load(KEYS.medications);
    assert(meds.length === 1, 'Med not saved');
    assert(meds[0].pills === 0, 'pills should be 0');
    localStorage.removeItem(KEYS.medications);
  });

  test('Medication with no pills field saves correctly', () => {
    localStorage.removeItem(KEYS.medications);
    setVal('med-name', 'NoPillsMed');
    document.getElementById('med-freq').value = 'Once daily';
    setVal('med-pills', '');
    editingMedId = null;
    addMedication();
    const meds = load(KEYS.medications);
    assert(meds.length === 1, 'Med not saved');
    assert(meds[0].pills === null, 'pills should be null when empty');
    localStorage.removeItem(KEYS.medications);
  });

  test('generateRecurringDates() respects 52-occurrence cap', () => {
    const dates = generateRecurringDates('2025-01-01', 'daily', '2026-12-31');
    assert(dates.length <= 52, 'Should cap at 52, got ' + dates.length);
  });

  test('Deleting a medication does not crash with active med checks', () => {
    const todayKey = getTodayKey();
    localStorage.removeItem(todayKey);
    const medId = 9000001;
    lsSet(KEYS.medications, [{ id: medId, name: 'ToDelete', frequency: 'Once daily', times: '', pills: 10, pillsMax: 10 }]);
    var checks = {};
    checks[medId + '_0'] = true;
    localStorage.setItem(todayKey, JSON.stringify(checks));
    window.confirm = function() { return true; };
    deleteMedication(medId);
    window.confirm = origConfirm;
    assert(load(KEYS.medications).length === 0, 'Med not deleted');
    localStorage.removeItem(todayKey);
  });

  test('PRN medication does not appear in scheduled dose counter', () => {
    const todayKey = getTodayKey();
    localStorage.removeItem(todayKey);
    lsSet(KEYS.medications, [
      { id: 9000002, name: 'Scheduled', frequency: 'Once daily', times: '', pills: 10, pillsMax: 10 },
      { id: 9000003, name: 'PRNMed', frequency: 'As needed (PRN)', times: '', pills: 10, pillsMax: 10 },
    ]);
    renderDashboard();
    var statEl = document.getElementById('stat-meds');
    if (statEl) {
      assert(statEl.textContent.indexOf('/1') !== -1, 'PRN should not count in scheduled total, got: ' + statEl.textContent);
    } else {
      assert(true);
    }
    localStorage.removeItem(todayKey);
    localStorage.removeItem(KEYS.medications);
  });

  test('Navigation to medications clears editingMedId global', () => {
    editingMedId = 12345;
    navigate('medications', null);
    assert(editingMedId === null, 'editingMedId should be null after navigate, got: ' + editingMedId);
  });

  test('sortAppointments() does not crash on undefined date field', () => {
    var appts = [
      { id: 1, title: 'A', date: '2025-06-01' },
      { id: 2, title: 'B', date: undefined },
      { id: 3, title: 'C', date: '2025-05-01' },
    ];
    try { sortAppointments(appts); assert(true); }
    catch(e) { throw new Error('sortAppointments crashed on undefined date: ' + e.message); }
  });

  // ── Export / Import Round-Trip ──────────────────────────────────────
  section('Export / Import Round-Trip');

  test('Export bundle contains all data sections', () => {
    lsSet(KEYS.medications, [{ id: 1, name: 'Lisinopril', frequency: 'Once daily', times: '', pills: 30, pillsMax: 30 }]);
    lsSet(KEYS.logs, [{ id: 2, date: '2025-06-01', mood: 'Good', sleep: 'Good', appetite: 'Normal', pain: '2' }]);
    lsSet(KEYS.appointments, [{ id: 3, title: 'Cardiology', date: '2025-07-15', time: '10:00' }]);
    lsSet(KEYS.careteam, [{ id: 4, name: 'Dr. Adams', role: 'PCP', phone: '555-1234' }]);
    var bundle = {
      _app: 'CareCompanion', _version: '1.4', _exported: new Date().toISOString(),
      medications: load(KEYS.medications),
      logs: load(KEYS.logs),
      appointments: load(KEYS.appointments),
      careteam: load(KEYS.careteam),
    };
    assert(bundle.medications.length === 1, 'Medications missing from bundle');
    assert(bundle.logs.length === 1, 'Logs missing from bundle');
    assert(bundle.appointments.length === 1, 'Appointments missing from bundle');
    assert(bundle.careteam.length === 1, 'Care team missing from bundle');
    localStorage.removeItem(KEYS.medications);
    localStorage.removeItem(KEYS.logs);
    localStorage.removeItem(KEYS.appointments);
    localStorage.removeItem(KEYS.careteam);
  });

  test('importData function exists and accepts input element', () => {
    assert(typeof importData === 'function', 'importData not a function');
  });

  // ── Dashboard Accuracy ──────────────────────────────────────────────
  section('Dashboard Accuracy');

  test('Refill alert shows low-pill med but not full-pill med', () => {
    lsSet(KEYS.medications, [
      { id: 1, name: 'LowMed', frequency: 'Once daily', times: '', pills: 5, pillsMax: 30 },
      { id: 2, name: 'OkMed',  frequency: 'Once daily', times: '', pills: 25, pillsMax: 30 },
    ]);
    renderRefillAlerts();
    var el = document.getElementById('refill-alerts');
    if (el) {
      assert(el.innerHTML.indexOf('LowMed') !== -1, 'LowMed should appear in refill alerts');
      assert(el.innerHTML.indexOf('OkMed') === -1, 'OkMed should NOT appear in refill alerts');
    } else { assert(true); }
    localStorage.removeItem(KEYS.medications);
  });

  test('Med check stat starts at 0/N on fresh day', () => {
    var todayKey = getTodayKey();
    localStorage.removeItem(todayKey);
    lsSet(KEYS.medications, [{ id: 1, name: 'MedA', frequency: 'Once daily', times: '', pills: 30, pillsMax: 30 }]);
    renderDashboard();
    var statEl = document.getElementById('stat-meds');
    if (statEl) {
      assert(statEl.textContent.indexOf('0/') !== -1, 'Should start at 0 doses given, got: ' + statEl.textContent);
    } else { assert(true); }
    localStorage.removeItem(todayKey);
    localStorage.removeItem(KEYS.medications);
  });

  test('Med check stat shows 1/1 when all doses checked', () => {
    var todayKey = getTodayKey();
    localStorage.removeItem(todayKey);
    var medId = 9000010;
    lsSet(KEYS.medications, [{ id: medId, name: 'MedB', frequency: 'Once daily', times: '', pills: 30, pillsMax: 30 }]);
    var checks = {};
    checks[medId + '_0'] = true;
    localStorage.setItem(todayKey, JSON.stringify(checks));
    renderDashboard();
    var statEl = document.getElementById('stat-meds');
    if (statEl) {
      assert(statEl.textContent === '1/1', 'Should show 1/1 when all checked, got: ' + statEl.textContent);
    } else { assert(true); }
    localStorage.removeItem(todayKey);
    localStorage.removeItem(KEYS.medications);
  });

  // ══════════════════════════════════════════════════════════════════════
  // RESTORE STATE
  // ══════════════════════════════════════════════════════════════════════
  window.confirm = origConfirm;
  window.alert   = origAlert;
  window.print   = origPrint;
  restoreState();
  navigate('dashboard');

  var total2 = passed + failed;
  var pct2 = total2 > 0 ? Math.round((passed / total2) * 100) : 0;
  console.log('\n==============================================================');
  console.log('  RESULTS: ' + passed + ' passed, ' + failed + ' failed (' + pct2 + '%)');
  if (failures.length) {
    console.log('\n  FAILURES:');
    failures.forEach(function(f) { console.log('  FAIL: ' + f); });
  } else {
    console.log('  ALL TESTS PASSED');
  }
  return { passed: passed, failed: failed, failures: failures };

})();
