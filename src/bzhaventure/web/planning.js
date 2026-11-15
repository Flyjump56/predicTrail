/** Calendrier personnel et assistant de préparation d’une course. */
const planningTypes = [
  ['PPG','Renforcement général',30], ['CAP','Course à pied',60],
  ['CUI','Renforcement en côtes ou en salle',40], ['ENP','Endurance portée',120],
  ['FRC','Fractionné',75], ['ISI','Bloc court course ou vélo',150],
  ['MID','Bloc moyen course ou vélo',210], ['MON','Bloc long course ou vélo',300],
  ['REC','Récupération',30]
];
const planningIcons = {PPG:'🏋️',CAP:'🏃',CUI:'⛰️',ENP:'🚴',FRC:'⏱️',ISI:'⚡',MID:'⚡',MON:'⚡',REC:'🌿'};
const planningTypeHues = {PPG:270,CAP:208,CUI:24,ENP:170,FRC:337,ISI:48,MID:4,MON:304,REC:112};

// Six créneaux des classeurs : lundi ou mardi, mercredi, jeudi, vendredi, samedi, dimanche.
// Le premier créneau est placé le mardi. Les durées absentes utilisent le catalogue.
const trailWeeks = [
  ['PPG','CAP:90 PPG','CUI','ENP:150 PPG','CAP:90','CAP:120'],
  ['PPG','CAP:90 PPG','FRC','ENP:180','CAP:60 ENP:120','ISI'],
  ['PPG','CAP:90 PPG','CUI','ENP:180 PPG','CAP:60','MID'],
  ['PPG','ENP:150','FRC','','','MID'],
  ['PPG','','CUI','PPG','CAP:90','ENP:240'],
  ['PPG','CAP:90 PPG','FRC','ENP:180','CAP:60 ENP:120','ENP:60 CAP:120'],
  ['PPG','CAP:60 PPG','CAP:75','ENP:180 PPG','CAP:60','MON'],
  ['PPG','ENP:150','FRC','','CAP:30','MON'],
  ['PPG','','ENP:90','PPG','CAP:90','ENP:180 CAP:30'],
  ['PPG','CAP:90','FRC','ENP:240 PPG','CAP:60 ENP:120','MON'],
  ['PPG','CAP:60 PPG','CAP:60','PPG','','ENP:180'],
  ['CAP:30','','CAP:30','','','']
];
const shortTrailWeeks = [
  ['', 'CAP:40', 'PPG:25', '', '', 'CAP:60'],
  ['', 'CAP:45', '', 'PPG:25', '', 'CAP:75'],
  ['', 'CAP:40', '', 'ENP:45', '', 'CAP:60'],
  ['CAP:25', '', 'CAP:20', '', '', '']
];

const planningForm = id => $(id).elements;
const planningISO = day => day.toISOString().slice(0,10);
const planningToday = () => {
  const now = new Date();
  return new Date(Date.UTC(now.getFullYear(),now.getMonth(),now.getDate()));
};
function planningDay(value) { return new Date(value+'T00:00:00Z'); }
function planningShift(day, offset) {
  const result = new Date(day);
  result.setUTCDate(result.getUTCDate()+offset);
  return result;
}
function planningMonday(day) {
  return planningShift(day,-((day.getUTCDay()+6)%7));
}
function planningWeekNumber(day) {
  const thursday = planningShift(planningMonday(day),3);
  const firstMonday = planningMonday(new Date(Date.UTC(thursday.getUTCFullYear(),0,4)));
  return 1+Math.round((planningMonday(day)-firstMonday)/604800000);
}
function planningMonthWeeks(first) {
  const nextMonth = new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,1));
  const weeks = [];
  for (let monday=planningMonday(first); monday<nextMonth; monday=planningShift(monday,7)) weeks.push(monday);
  return weeks;
}
const planningFormatDate = (day, options) => day.toLocaleDateString('fr-FR',{timeZone:'UTC',...options});
const planningMinutes = minutes => minutes < 60 ? minutes+' min' :
  Math.floor(minutes/60)+' h'+(minutes%60 ? ' '+String(minutes%60).padStart(2,'0') : '');

let planning = null, planningRevision = null, planningBusy = false, planningPreview = [];
let planningMonth = planningToday(), planningSelected = planningISO(planningToday()), planningEdit = null;
let planningView = 'month';
let planningReferences = [], planningReferenceRequest = 0;

function planningStatus(message) { $('planning-status').textContent = message; }
function planningLock(value) {
  planningBusy = value;
  $('planning-reload').disabled = value;
  $('planning-controls').disabled = value || !planning;
}
function resetPlanningPreview() {
  planningPreview = [];
  $('planning-preview').textContent = '';
  $('planning-apply-template').disabled = true;
}
function formOptions(select, values) {
  select.replaceChildren();
  for (const [value,label] of values) {
    const option = element('option',label);
    option.value = value;
    select.append(option);
  }
}
function planningTraceLink(goal, label) {
  const link = element('a',label);
  link.href = apiUrl('/api/source?id='+encodeURIComponent(goal.sourceId));
  link.download = goal.filename || 'objectif.gpx';
  return link;
}
function resetPlanningForms() {
  const goal = planningForm('planning-goal'), session = planningForm('planning-session');
  const type = planningForm('planning-type');
  goal.namedItem('name').value = planning.goal?.name || '';
  goal.date.value = planning.goal?.date || '';
  goal.trace.value = '';
  goal.removeTrace.checked = false;
  goal.removeTrace.disabled = !planning.goal?.sourceId;
  const info = $('planning-goal-info');
  info.replaceChildren();
  if (planning.goal?.sourceId) {
    info.append(planningTraceLink(planning.goal,planning.goal.filename || 'Télécharger le GPX'));
  }
  $('planning-delete-goal').disabled = !planning.goal;
  $('planning-jump-goal').disabled = !planning.goal;
  const types = planning.types.map(item=>[item.name,item.name]);
  formOptions(session.type,types);
  formOptions(type.existing,[['','Nouveau type'],...types]);
  type.namedItem('name').value = '';
  type.minutes.value = '';
  selectPlanningDate(planningSelected);
}
function renderPlanning() {
  const first = new Date(planningMonth);
  first.setUTCDate(1);
  const yearly = planningView === 'year';
  $('planning-view-month').setAttribute('aria-pressed',String(!yearly));
  $('planning-view-year').setAttribute('aria-pressed',String(yearly));
  $('planning-month-view').hidden = yearly;
  $('planning-year-view').hidden = !yearly;
  $('planning-year-legend').hidden = !yearly;
  const period = yearly ? 'Année' : 'Mois';
  $('planning-prev').textContent = '‹ '+period+(yearly ? ' précédente' : ' précédent');
  $('planning-next').textContent = period+(yearly ? ' suivante ›' : ' suivant ›');
  if (yearly) renderPlanningYear(first.getUTCFullYear());
  else renderPlanningMonth(first);
  renderSelectedPlanningDay();
}
function renderPlanningYear(year) {
  $('planning-month').textContent = String(year);
  const view = $('planning-year-view');
  view.replaceChildren();
  const monthly = Array.from({length:12},()=>({count:0,minutes:0,references:0}));
  for (const session of planning.sessions) {
    if (Number(session.date.slice(0,4)) !== year) continue;
    const month = monthly[Number(session.date.slice(5,7))-1];
    month.count++;
    month.minutes += session.minutes;
  }
  for (const reference of planningReferences) {
    if (Number(reference.date.slice(0,4)) === year) monthly[Number(reference.date.slice(5,7))-1].references++;
  }
  const trainingDates = new Map();
  for (const {date,type} of planning.sessions) {
    if (!trainingDates.has(date)) trainingDates.set(date,new Set());
    trainingDates.get(date).add(type);
  }
  const referenceDates = new Set(planningReferences.map(reference=>reference.date));
  for (const [index,month] of monthly.entries()) {
    const first = new Date(Date.UTC(year,index,1));
    const key = planningISO(first).slice(0,7);
    const goal = planning.goal?.date.startsWith(key) ? planning.goal : null;
    const card = element('div','');
    card.className = 'planning-year-month';
    const button = element('button',planningFormatDate(first,{month:'long'}));
    button.type = 'button';
    button.className = 'planning-year-month-title';
    const openMonth = (date)=>{
      planningView = 'month';
      planningMonth = first;
      selectPlanningDate(date);
    };
    button.addEventListener('click',()=>openMonth(goal?.date || planningISO(first)));
    card.append(button,element('span',month.count+' séance(s) · '+planningMinutes(month.minutes)));
    if (month.references) card.append(element('span',month.references+' course(s) de référence'));
    if (goal) card.append(element('span','🏁 '+goal.name+' · '+planningFormatDate(planningDay(goal.date),{dateStyle:'short'})));
    const table = element('table','');
    table.className = 'planning-mini-calendar';
    table.setAttribute('aria-label',planningFormatDate(first,{month:'long',year:'numeric'}));
    const header = table.createTHead().insertRow();
    for (const label of ['Sem.','L','M','M','J','V','S','D']) {
      const cell = element('th',label);
      cell.scope = 'col';
      header.append(cell);
    }
    const body = table.createTBody();
    for (const monday of planningMonthWeeks(first)) {
      const row = body.insertRow();
      appendPlanningWeek(row,monday);
      for (let weekday=0; weekday<7; weekday++) {
        const day = planningShift(monday,weekday), cell = row.insertCell();
        if (day.getUTCMonth() !== index) continue;
        const key = planningISO(day);
        const marker = element('button',String(day.getUTCDate()));
        marker.type = 'button';
        const labels = [planningFormatDate(day,{dateStyle:'full'})];
        const types = trainingDates.get(key);
        if (types) {
          const indicators = element('span','');
          indicators.className = 'planning-mini-types';
          indicators.setAttribute('aria-hidden','true');
          for (const type of types) {
            const dot = element('span','');
            dot.className = 'planning-type-dot';
            applyPlanningTypeColor(dot,type);
            indicators.append(dot);
          }
          marker.append(indicators);
          labels.push(...types);
        }
        if (referenceDates.has(key)) { marker.classList.add('mini-reference'); labels.push('course de référence'); }
        if (key === goal?.date) { marker.classList.add('mini-goal'); labels.push(goal.name); }
        marker.setAttribute('aria-label',labels.join(' · '));
        marker.title = labels.join(' · ');
        marker.addEventListener('click',()=>openMonth(key));
        cell.append(marker);
      }
    }
    card.append(table);
    view.append(card);
  }
}
function appendPlanningWeek(row,monday) {
  const number = element('th',String(planningWeekNumber(monday)));
  number.scope = 'row';
  number.className = 'planning-week-number';
  row.append(number);
}
function planningTypeCode(name) {
  return planning.types.find(type=>type.name===name)?.code ||
    planningTypes.find(type=>type[1]===name)?.[0];
}
function planningSessionLabel(name) {
  return (planningIcons[planningTypeCode(name)] || '◆')+' '+name;
}
function applyPlanningTypeColor(node,name) {
  const fallbackHue = Array.from(name.toLowerCase()).reduce(
    (hash,letter)=>(hash*31+letter.codePointAt(0))%360,0);
  const hue = planningTypeHues[planningTypeCode(name)] ?? fallbackHue;
  node.style.setProperty('--planning-type-hue',String(hue));
}
function planningReferenceButton(reference, detailed = false) {
  const minutes = Math.round(reference.duration/60);
  const stats = detailed ? ' · '+km(reference.distance)+' · '+minutes+' min ('+
    Math.floor(minutes/60)+' h '+String(minutes%60).padStart(2,'0')+' min)' : '';
  const button = element('button','📍 '+reference.name+stats);
  button.type = 'button';
  button.className = 'planning-reference';
  button.title = 'Course de référence · afficher sur la carte';
  button.setAttribute('aria-label','Afficher '+reference.name+' sur la Carte des références');
  button.addEventListener('click',()=>openOwnReferenceOnMap(reference.key));
  return button;
}
function renderPlanningMonth(first) {
  $('planning-month').textContent = planningFormatDate(first,{month:'long',year:'numeric'});
  const body = $('planning-days');
  body.replaceChildren();
  const byDay = new Map();
  planning.sessions.forEach((session,index) => {
    if (!byDay.has(session.date)) byDay.set(session.date,[]);
    byDay.get(session.date).push([session,index]);
  });
  const referencesByDay = new Map();
  for (const reference of planningReferences) {
    if (!referencesByDay.has(reference.date)) referencesByDay.set(reference.date,[]);
    referencesByDay.get(reference.date).push(reference);
  }
  for (const monday of planningMonthWeeks(first)) {
    const row = body.insertRow();
    appendPlanningWeek(row,monday);
    for (let weekday=0; weekday<7; weekday++) {
      const day = planningShift(monday,weekday);
      const key = planningISO(day), cell = row.insertCell();
      if (day.getUTCMonth() !== first.getUTCMonth()) cell.classList.add('planning-other-month');
      if (key === planningSelected) cell.classList.add('planning-selected');
      const button = element('button',String(day.getUTCDate()));
      button.type = 'button';
      button.setAttribute('aria-label',planningFormatDate(day,{dateStyle:'full'}));
      button.addEventListener('click',()=>selectPlanningDate(key));
      cell.append(button);
      if (key === planning.goal?.date) {
        cell.append(element('strong','🏁 '+planning.goal.name));
        if (planning.goal.sourceId) cell.append(planningTraceLink(planning.goal,'Trace GPX'));
      }
      for (const [session,index] of byDay.get(key) || []) {
        const entry = element('button',planningSessionLabel(session.type)+' · '+planningMinutes(session.minutes));
        entry.type = 'button';
        entry.className = 'planning-entry';
        if (session.note) entry.title = session.note;
        applyPlanningTypeColor(entry,session.type);
        entry.addEventListener('click',()=>editPlanningSession(index));
        cell.append(entry);
      }
      for (const reference of referencesByDay.get(key) || []) {
        cell.append(planningReferenceButton(reference));
      }
    }
  }
}
function editPlanningSession(index) {
  selectPlanningDate(planning.sessions[index].date,index);
  $('planning-session-details').open = true;
  planningForm('planning-session').date.focus?.();
}
function removePlanningSession(index) {
  if (!planning || planningBusy || !planning.sessions[index] || !window.confirm('Supprimer cette séance ?')) return;
  const sessions = planning.sessions.filter((_,position)=>position!==index);
  return changePlanning(()=>({...planning,sessions}),'Séance supprimée.');
}
function renderSelectedPlanningDay() {
  const selected = planningDay(planningSelected);
  const monday = planningMonday(selected);
  const lastDay = planningISO(planningShift(monday,6));
  const week = planning.sessions.filter(item=>item.date >= planningISO(monday) && item.date <= lastDay);
  $('planning-delete-week').disabled = !week.length;
  $('planning-week').textContent = 'Semaine '+planningWeekNumber(monday)+' · du '+planningFormatDate(monday,{dateStyle:'short'})+
    ' · '+week.length+' séance(s) · '+planningMinutes(week.reduce((sum,item)=>sum+item.minutes,0));
  $('planning-selected-day').textContent = 'Séances du '+planningFormatDate(selected,{dateStyle:'full'});
  const shortcuts = $('planning-quick-types');
  shortcuts.replaceChildren();
  for (const {name,minutes} of planning.types) {
    const button = element('button','+ '+planningSessionLabel(name)+' · '+planningMinutes(minutes));
    button.type = 'button';
    button.className = 'button planning-type-shortcut';
    applyPlanningTypeColor(button,name);
    button.addEventListener('click',()=>{
      const session = {date:planningSelected,type:name,minutes,note:''};
      return changePlanning(()=>({...planning,sessions:[...planning.sessions,session]}),'Séance ajoutée.');
    });
    shortcuts.append(button);
  }
  const list = $('planning-selected-sessions');
  list.replaceChildren();
  for (const [index,session] of planning.sessions.entries()) {
    if (session.date !== planningSelected) continue;
    const row = element('li','');
    const name = planningSessionLabel(session.type)+' · '+planningMinutes(session.minutes);
    const edit = element('button','Modifier');
    const remove = element('button','Supprimer');
    edit.type = remove.type = 'button';
    edit.setAttribute('aria-label','Modifier '+name);
    remove.setAttribute('aria-label','Supprimer '+name);
    edit.addEventListener('click',()=>editPlanningSession(index));
    remove.addEventListener('click',()=>removePlanningSession(index));
    const label = element('span',name);
    label.className = 'planning-type-label';
    applyPlanningTypeColor(label,session.type);
    row.append(label,edit,remove);
    if (session.note) {
      const instructions = element('p',session.note);
      instructions.className = 'planning-session-instructions';
      row.append(instructions);
    }
    list.append(row);
  }
  for (const reference of planningReferences) {
    if (reference.date !== planningSelected) continue;
    const row = element('li','');
    row.append(planningReferenceButton(reference,true));
    list.append(row);
  }
  $('planning-delete-all').disabled = !planning.sessions.length;
}
function selectPlanningDate(date, index = null) {
  planningSelected = date;
  planningEdit = index;
  const form = planningForm('planning-session');
  const selected = index === null ? null : planning.sessions[index];
  form.date.value = date;
  form.type.value = selected?.type || planning.types[0]?.name || '';
  form.minutes.value = selected?.minutes ?? planning.types[0]?.minutes ?? 0;
  form.note.value = selected?.note || '';
  form.repeat.value = 1;
  form.repeat.disabled = index !== null;
  $('planning-delete-session').hidden = index === null;
  renderPlanning();
}
async function loadPlanning(jump = true) {
  if (planningBusy) return;
  planningLock(true);
  try {
    const result = await requestJSON('/api/planning');
    planning = result.planning || {types:planningTypes.map(([code,name,minutes])=>({code,name,minutes})),sessions:[],goal:null};
    planningRevision = result.revision;
    if (jump && planning.goal) {
      planningSelected = planning.goal.date;
      planningMonth = planningDay(planningSelected);
    }
    resetPlanningPreview();
    resetPlanningForms();
    planningStatus('');
    loadPlanningReferences();
  } catch (error) { planningStatus(error.message); }
  finally { planningLock(false); }
}
async function loadPlanningReferences() {
  const version = ++planningReferenceRequest;
  const status = $('planning-reference-status');
  status.textContent = 'Chargement des courses de référence…';
  try {
    const data = await requestJSON('/api/planning/references');
    if (version !== planningReferenceRequest) return;
    planningReferences = data.courses.flatMap(course=>{
      const start = new Date(course.recordedStart);
      if (!Number.isFinite(start.getTime())) return [];
      const date = new Date(Date.UTC(start.getFullYear(),start.getMonth(),start.getDate()));
      return [{...course,date:planningISO(date)}];
    });
    status.textContent = (planningReferences.length ? '📍 Course de référence · cliquez sur son nom pour ouvrir sa fiche sur la carte.' : 'Aucune course de référence à afficher.')+
      (data.skipped.length ? ' '+data.skipped.length+' référence(s) non exploitable(s).' : '');
    renderPlanning();
  } catch (error) {
    if (version === planningReferenceRequest) status.textContent = 'Courses de référence indisponibles · '+error.message;
  }
}
async function changePlanning(build, success, jump) {
  if (!planning || planningBusy) return;
  planningLock(true);
  try {
    const next = await build();
    const result = await postJSON('/api/planning',{planning:next,revision:planningRevision});
    planning = result.planning;
    planningRevision = result.revision;
    if (jump) {
      planningSelected = jump;
      planningMonth = planningDay(jump);
    }
    resetPlanningPreview();
    resetPlanningForms();
    planningStatus(success);
  } catch (error) { planningStatus(error.message); }
  finally { planningLock(false); }
}

$('planning-reload').addEventListener('click',()=>loadPlanning(false));
const planningReportZone = new Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
const planningReportQuery = '?zone='+encodeURIComponent(planningReportZone)+'&offset='+(-new Date().getTimezoneOffset());
$('planning-export').href = apiUrl('/api/planning/export'+planningReportQuery);
const planningPrintForm = $('planning-print-form');
planningPrintForm.action = apiUrl('/api/planning/print');
planningPrintForm.elements.zone.value = planningReportZone;
planningPrintForm.elements.offset.value = -new Date().getTimezoneOffset();
let planningPrintRequest = 0;
planningPrintForm.addEventListener('submit',async event=>{
  event.preventDefault();
  const request = ++planningPrintRequest;
  const {start,end,layout} = planningPrintForm.elements;
  const days = (planningDay(end.value)-planningDay(start.value))/86400000;
  let error = '';
  if (!Number.isFinite(days) || days < 0) error = 'Choisissez une date de début et une date de fin dans l’ordre.';
  else if (layout.value === 'calendar' && days >= 366) error = 'Choisissez au maximum 366 jours pour la vue calendrier.';
  $('planning-print-error').textContent = error;
  if (error) return;
  const preview = $('planning-print-preview');
  const frame = $('planning-print-frame');
  preview.hidden = true;
  frame.srcdoc = '';
  $('planning-print-error').textContent = 'Préparation de l’aperçu…';
  const query = new URLSearchParams({start:start.value,end:end.value,layout:layout.value || 'list',
    zone:planningReportZone,offset:String(-new Date().getTimezoneOffset()),embedded:'1'});
  try {
    const response = await apiFetch('/api/planning/print?'+query);
    if (!response.ok) {
      const details = await response.json().catch(()=>({}));
      throw Error(details.error || 'L’aperçu est indisponible.');
    }
    const html = await response.text();
    if (request !== planningPrintRequest) return;
    preview.hidden = false;
    frame.srcdoc = html;
    $('planning-print-error').textContent = '';
  } catch (error) {
    if (request === planningPrintRequest) $('planning-print-error').textContent = error.message;
  }
});
$('planning-print-close').addEventListener('click',()=>{
  planningPrintRequest++;
  $('planning-print-frame').srcdoc = '';
  $('planning-print-preview').hidden = true;
});
for (const view of ['month','year']) {
  $('planning-view-'+view).addEventListener('click',()=>{
    planningView = view;
    if (planning) renderPlanning();
  });
}
for (const [id,step] of [['planning-prev',-1],['planning-next',1]]) {
  $(id).addEventListener('click',()=>{
    planningMonth.setUTCDate(1);
    if (planningView === 'year') planningMonth.setUTCFullYear(planningMonth.getUTCFullYear()+step);
    else planningMonth.setUTCMonth(planningMonth.getUTCMonth()+step);
    selectPlanningDate(planningISO(planningMonth));
  });
}
$('planning-today').addEventListener('click',()=>{
  planningMonth = planningToday();
  selectPlanningDate(planningISO(planningMonth));
});
$('planning-jump-goal').addEventListener('click',()=>{
  if (!planning?.goal) return;
  planningView = 'month';
  planningMonth = planningDay(planning.goal.date);
  selectPlanningDate(planning.goal.date);
});
$('planning-goal').addEventListener('submit',event=>{
  event.preventDefault();
  const form = planningForm('planning-goal');
  const name = form.namedItem('name').value, date = form.date.value, file = form.trace.files[0], remove = form.removeTrace.checked;
  changePlanning(async()=>{
    let sourceId = remove ? '' : planning.goal?.sourceId || '';
    let filename = remove ? '' : planning.goal?.filename || '';
    if (file) {
      if (remove) throw Error('Choisissez une nouvelle trace ou détachez la trace actuelle.');
      planningStatus('Préparation de la trace GPX…');
      const gpx = await readGpx(file,'compact');
      const trace = await postJSON('/api/planning/trace',{gpx});
      sourceId = trace.sourceId;
      filename = file.name;
    }
    const sessions = date === planning.goal?.date ? planning.sessions : planning.sessions.map(session=>
      session.goalOffset === undefined ? session :
        {...session,date:planningISO(planningShift(planningDay(date),session.goalOffset))});
    return {...planning,sessions,goal:{name,date,sourceId,filename}};
  },'Course objectif enregistrée.',date);
});
$('planning-delete-goal').addEventListener('click',()=>{
  if (window.confirm('Retirer la course objectif du calendrier ?')) {
    changePlanning(()=>({...planning,goal:null,sessions:planning.sessions.map(({goalOffset,...session})=>session)}),
      'Course objectif retirée.');
  }
});
$('planning-session').addEventListener('submit',event=>{
  event.preventDefault();
  const form = planningForm('planning-session');
  const {date,type,minutes,repeat,note} = form;
  const session = {date:date.value,type:type.value,minutes:Number(minutes.value),note:note.value};
  const sessions = [...planning.sessions];
  if (planningEdit === null) {
    for (let week=0; week<Number(repeat.value); week++) {
      sessions.push({...session,date:planningISO(planningShift(planningDay(session.date),week*7))});
    }
  } else {
    const previous = sessions[planningEdit];
    if (session.date === previous.date && previous.goalOffset !== undefined) session.goalOffset = previous.goalOffset;
    sessions[planningEdit] = session;
  }
  changePlanning(()=>({...planning,sessions}),'Séance enregistrée.',session.date);
});
planningForm('planning-session').type.addEventListener('change',()=>{
  const form = planningForm('planning-session');
  form.minutes.value = planning.types.find(item=>item.name===form.type.value)?.minutes ?? 0;
});
$('planning-new-session').addEventListener('click',()=>selectPlanningDate(planningSelected));
$('planning-delete-session').addEventListener('click',()=>{
  if (planningEdit !== null) return removePlanningSession(planningEdit);
});
$('planning-delete-week').addEventListener('click',()=>{
  if (!planning || planningBusy) return;
  const monday = planningMonday(planningDay(planningSelected));
  const start = planningISO(monday), end = planningISO(planningShift(monday,7));
  const sessions = planning.sessions.filter(session=>session.date<start || session.date>=end);
  const removed = planning.sessions.length-sessions.length;
  if (!removed || !window.confirm('Supprimer '+removed+' entraînement(s) de la semaine '+planningWeekNumber(monday)+' ?')) return;
  return changePlanning(()=>({...planning,sessions}),removed+' entraînement(s) supprimé(s) de la semaine.');
});
$('planning-delete-all').addEventListener('click',()=>{
  if (planning?.sessions.length && window.confirm('Supprimer les '+planning.sessions.length+
    ' entraînement(s) de tout le calendrier ? La course objectif et les types de séances seront conservés.')) {
    return changePlanning(()=>({...planning,sessions:[]}),'Tous les entraînements ont été supprimés.');
  }
});
planningForm('planning-type').existing.addEventListener('change',()=>{
  const form = planningForm('planning-type');
  const existing = planning.types.find(item=>item.name===form.existing.value);
  form.namedItem('name').value = existing?.name || '';
  form.minutes.value = existing?.minutes ?? '';
});
$('planning-type').addEventListener('submit',event=>{
  event.preventDefault();
  const form = planningForm('planning-type');
  const before = form.existing.value, name = form.namedItem('name').value.trim(), minutes = Number(form.minutes.value);
  const entry = {...planning.types.find(item=>item.name===before),name,minutes};
  const types = before ? planning.types.map(item=>item.name===before ? entry : item) : [...planning.types,entry];
  const sessions = before ? planning.sessions.map(item=>item.type===before ? {...item,type:name} : item) : planning.sessions;
  changePlanning(()=>({...planning,types,sessions}),'Type enregistré.');
});

function generatePreparation(goalDate, weeks, scale, types) {
  const goal = planningDay(goalDate);
  const sessions = [];
  // Ces écarts en jours reprennent la trame source, calée sur une course le samedi.
  const offsetsFromSaturday = [-4,-3,-2,-1,0,1];
  weeks.forEach((week,index)=>week.forEach((slot,day)=>{
    const offset = offsetsFromSaturday[day] - (weeks.length-1-index)*7;
    if (offset >= 0) return;
    for (const code of slot.split(' ').filter(Boolean)) {
      const [key,minutes] = code.split(':');
      const [,defaultName,defaultMinutes] = planningTypes.find(item=>item[0]===key);
      const custom = types.find(item=>item.code===key) || types.find(item=>item.name.toLowerCase()===defaultName.toLowerCase());
      const type = custom?.name || defaultName;
      const base = minutes ? Number(minutes) : custom?.minutes ?? defaultMinutes;
      sessions.push({date:planningISO(planningShift(goal,offset)),type,minutes:Math.round(base*scale),note:'',goalOffset:offset});
    }
  }));
  return sessions;
}
$('planning-template').addEventListener('change',resetPlanningPreview);
$('planning-template').addEventListener('submit',event=>{
  event.preventDefault();
  resetPlanningPreview();
  const form = planningForm('planning-template'), value = form.template.value;
  const preview = $('planning-preview');
  if (value === '0') {
    preview.textContent = 'Le planning libre se remplit avec le formulaire Séance et répétition.';
    return;
  }
  if (!planning?.goal) {
    preview.textContent = 'Enregistrez d’abord la date de la course objectif.';
    return;
  }
  const weeks = value === '12' ? trailWeeks : shortTrailWeeks;
  planningPreview = generatePreparation(planning.goal.date,weeks,Number(form.scale.value),planning.types);
  const total = planningMinutes(planningPreview.reduce((sum,item)=>sum+item.minutes,0));
  preview.textContent = 'Jour J · '+planningFormatDate(planningDay(planning.goal.date),{dateStyle:'long'})+
    ' · '+planningPreview.length+' séances · '+total+' · du '+
    planningFormatDate(planningDay(planningPreview[0].date),{dateStyle:'short'})+' au '+
    planningFormatDate(planningDay(planningPreview[planningPreview.length-1].date),{dateStyle:'short'});
  const summary = new Map();
  for (const session of planningPreview) {
    const offset = Math.ceil(-session.goalOffset/7);
    summary.set(offset,(summary.get(offset) || 0)+session.minutes);
  }
  const detail = element('small',[...summary].map(([weeks,minutes]) =>
    'J−'+(weeks*7)+' à J−'+((weeks-1)*7+1)+' · '+planningMinutes(minutes)).join(' / '));
  preview.append(element('br',''),detail);
  $('planning-apply-template').disabled = false;
});
$('planning-apply-template').addEventListener('click',()=>{
  if (!planningPreview.length) return;
  const key = item => JSON.stringify([item.date,item.type,item.minutes,item.note]);
  const saved = new Set(planning.sessions.map(key));
  const added = planningPreview.filter(item=>!saved.has(key(item)));
  if (!added.length) { planningStatus('Ces séances figurent déjà au calendrier.'); return; }
  const types = [...planning.types];
  for (const [code,name,minutes] of planningTypes) {
    if (added.some(item=>item.type===name) && !types.some(item=>item.name.toLowerCase()===name.toLowerCase())) {
      types.push({code,name,minutes});
    }
  }
  changePlanning(()=>({...planning,types,sessions:[...planning.sessions,...added]}),
    added.length+' séance(s) ajoutée(s).',added[0].date);
});
