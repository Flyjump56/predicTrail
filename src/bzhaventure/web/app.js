/**
 * Tableau de bord BZHAventure UltraTrail.
 * Les durées sont exprimées en secondes et les distances en mètres.
 * Les dates civiles sont calculées dans le fuseau de l'appareil.
 */
// Accès au document et formatage des unités de l'interface.
const $ = id => document.getElementById(id);
const PROFILE_ICONS={flat:'▱',mountain:'▲',sawtooth:'⋀⋀',mixed:'∿'};
const profileLabel = c => (PROFILE_ICONS[c.profile] || '◇')+' '+(c.profileLabel || c.profile || 'Inconnu').replace(/Dent de scie/g,'Dents de scie');
const RELIEF_PROFILES=['flat','mountain','sawtooth','mixed'];
const DISTANCE_IDS=['very_short','short','medium','long','ultra'];
const number = (value, digits=0) => value.toLocaleString('fr-FR', {minimumFractionDigits:digits, maximumFractionDigits:digits});
const km = meters => number(meters / 1000, 2) + ' km';
const meters = value => number(value) + ' m';
function time(seconds) {
  const total = Math.round(seconds);
  return [Math.floor(total / 3600), Math.floor(total / 60) % 60, total % 60]
    .map(part => String(part).padStart(2, '0')).join(':');
}
// Calendrier local. Les secondes prédites sont ajoutées à un instant absolu,
// ce qui conserve les passages à minuit et les changements d'heure.
const localZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
$('departure-zone').textContent = 'Fuseau horaire de cet appareil · '+localZone;
function departureDate(id='departure') {
  const input = $(id);
  input.setCustomValidity('');
  if (!input.value) return null;
  const date = new Date(input.value);
  const parts = input.value.split(/\D/).map(Number);
  const actual = [date.getFullYear(),date.getMonth()+1,date.getDate(),date.getHours(),date.getMinutes()];
  if (!Number.isFinite(date.getTime()) || actual.some((value,index) => value !== parts[index])) {
    input.setCustomValidity('Choisissez une date et une heure valides dans le fuseau '+localZone+'.');
    return null;
  }
  return date;
}
function passageDate(departure,seconds) {
  if (!departure) return '—';
  return new Date(departure.getTime()+Math.round(seconds)*1000).toLocaleString('fr-FR',{
    year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'
  });
}
function updateSchedule() {
  const departure = departureDate();
  scheduledDeparture = departure;
  $('departure-summary').textContent = departure ?
    'Départ prévu · '+passageDate(departure,0)+' · '+localZone : '';
  if (!routeData) return;
  $('arrival-estimate').textContent = departure ? passageDate(departure,routeData.duration) : 'Départ à renseigner';
  for (const [index,row] of Array.from($('marks').rows).entries()) {
    row.cells[3].textContent = passageDate(departure,routeData.marks[index][1]);
  }
  updateCheckpointTimes();
  positionPlayback(playbackTime);
}
$('departure').addEventListener('input',updateSchedule);
$('departure').addEventListener('change',() => {
  updateSchedule();
  $('departure').reportValidity();
});
$('recalculate').addEventListener('click',() => {
  updateSchedule();
  if (!$('departure').reportValidity()) return;
  $('status').textContent = 'Horaires de passage recalculés.';
});
function element(tag, content) {
  const node = document.createElement(tag);
  node.textContent = content;
  return node;
}
function metrics(container, values) {
  container.replaceChildren(...values.map(([label,value]) => {
    const tile = element('div', '');
    tile.className = 'metric';
    tile.append(element('small',label), element('strong',value));
    return tile;
  }));
}
// Profils SVG. La projection retournée sert aussi au marqueur de lecture.
function profile(container, title, data) {
  let min = Infinity, max = -Infinity;
  for (const segment of data.profile) {
    for (const [,elevation] of segment) {
      min = Math.min(min,elevation);
      max = Math.max(max,elevation);
    }
  }
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 760 145');
  svg.setAttribute('aria-hidden','true');
  const project = (distance,elevation) =>
    [5+750*distance/data.distance,135-125*(elevation-min)/Math.max(1,max-min)];
  const paths = data.sections ? data.sections.map(section => ({
    points:[[section.distance,section.start[2]],[section.endDistance,section.end[2]]],
    color:sectionColor(section)
  })) : data.profile.map(points => ({points,color:'#21677d'}));
  for (const path of paths) {
    const line = document.createElementNS(ns,'polyline');
    line.setAttribute('points',path.points.map(([distance,elevation]) =>
      project(distance,elevation).map(value => value.toFixed(1)).join(',')).join(' '));
    line.setAttribute('fill','none');
    line.setAttribute('stroke',path.color);
    line.setAttribute('stroke-width','2');
    svg.append(line);
  }
  container.replaceChildren(element('figcaption',title), svg,
    element('small', km(data.distance) + ' · Altitude de ' + meters(min) + ' à ' + meters(max)));
  const guide = svgElement('line',{y1:5,y2:140,stroke:'#bd5228','stroke-width':1,'stroke-dasharray':'3 3'});
  const dot = svgElement('circle',{r:4,fill:'#bd5228',stroke:'#fff','stroke-width':1});
  guide.classList.add('playback-marker');
  dot.classList.add('playback-marker');
  if (container.id === 'result-profile') svg.append(guide,dot);
  return {guide,dot,project};
}
function showTerrain(container, data, timed=false) {
  const table = element('table','');
  table.createCaption().textContent = 'Distance, temps et allure par type de terrain';
  const header = table.createTHead().insertRow();
  const labels = ['Terrain','Distance','Part du parcours'];
  if (timed) labels.push('Temps GPX','Allure GPX');
  labels.push('Temps estimé','Allure estimée');
  for (const label of labels) {
    const cell = element('th',label);
    cell.scope = 'col';
    header.append(cell);
  }
  const body = table.createTBody();
  for (const {name,distance,actual,estimated} of data.terrain) {
    const row = body.insertRow();
    const label = element('th',name);
    label.scope = 'row';
    row.append(label);
    const values = [km(distance),number(distance / data.distance * 100,1)+' %'];
    const timing = seconds => seconds === null || !distance ? ['—','—'] :
      [time(seconds),time(seconds * 1000 / distance).replace(/^00:/,'')+' / km'];
    if (timed) values.push(...timing(actual));
    values.push(...timing(estimated));
    for (const value of values) row.insertCell().textContent = value;
  }
  const note = element('p','Montée au-dessus de +3 %, descente sous −3 %, plat entre les deux. Les pentes sont calculées sur les portions de l’échantillonnage adapté au profil.');
  note.className = 'muted notice';
  container.replaceChildren(table,note);
  if (timed && data.unassigned >= 1) {
    container.append(element('small','Temps GPX hors portions classées · '+time(data.unassigned)));
  }
}
function svgElement(tag, attributes={}) {
  const node = document.createElementNS('http://www.w3.org/2000/svg',tag);
  for (const [key,value] of Object.entries(attributes)) node.setAttribute(key,value);
  return node;
}
// Courbes des modèles retenus et candidats, puis comparaison des validations.
function drawModel(model, container=$('model-chart'), info=$('model-info')) {
  const points = [...model.curve,...model.observations,...(model.candidateCurve || [])];
  const minGrade = Math.min(...points.map(point => point.grade));
  const maxGrade = Math.max(...points.map(point => point.grade));
  const maxSpeed = Math.max(...points.map(point => point.speed)) * 1.1;
  const x = grade => 60 + (grade-minGrade) / Math.max(1,maxGrade-minGrade) * 650;
  const y = speed => 260 - speed / maxSpeed * 230;
  const svg = svgElement('svg',{viewBox:'0 0 760 315',class:'chart',role:'img',
    'aria-label':'Vitesse prédite et vitesse médiane observée en fonction de la pente'});
  function text(label,px,py,anchor='middle') {
    const node = svgElement('text',{x:px,y:py,'text-anchor':anchor});
    node.textContent = label;
    svg.append(node);
  }
  for (let i=0;i<=5;i++) {
    const speed = maxSpeed*i/5;
    svg.append(svgElement('line',{x1:60,x2:710,y1:y(speed),y2:y(speed),stroke:'#dce7e3'}));
    text(number(speed,1),50,y(speed)+4,'end');
    const grade = minGrade+(maxGrade-minGrade)*i/5;
    text(number(grade,0)+' %',x(grade),282);
  }
  text('Vitesse (km/h)',60,16,'start');
  text('Pente · descente ← → montée',385,307);
  svg.append(svgElement('polyline',{points:model.curve.map(p => x(p.grade)+','+y(p.speed)).join(' '),
    fill:'none',stroke:'#21677d','stroke-width':3}));
  if (model.candidateCurve?.length) {
    svg.append(svgElement('polyline',{points:model.candidateCurve.map(p => x(p.grade)+','+y(p.speed)).join(' '),
      fill:'none',stroke:'#8c639d','stroke-width':2,'stroke-dasharray':'5 4'}));
  }
  for (const point of model.observations) {
    const dot = svgElement('circle',{cx:x(point.grade),cy:y(point.speed),r:4,fill:'#bd5228'});
    const title = svgElement('title');
    title.textContent = number(point.grade)+' % · '+number(point.speed,2)+' km/h · '+point.count+' portions';
    dot.append(title);
    svg.append(dot);
  }
  const legend = element('p','');
  for (const [label,style] of [['Modèle prédictif',''],['Médianes observées',' observed']]) {
    const swatch = element('span','');
    swatch.className = 'swatch'+style;
    legend.append(swatch,document.createTextNode(label+'   '));
  }
  if (model.candidateCurve?.length) legend.append(document.createTextNode(' · Pointillés violets : modèle de groupe candidat'));
  container.replaceChildren(svg,legend);
  info.textContent = number(model.samples)+' portions dans les classes de pente retenues. '+
    (model.scope === 'segmented' ? model.exactCount+' référence(s) du groupe et '+model.count+
      ' du même profil. Contribution du profil : '+number(model.localWeight*100,0)+' %. '+model.status+'. ' : '')+
    (model.candidateError !== null && model.candidateError !== undefined ?
      'Validation interne sur '+model.validationCount+' courses : erreur moyenne du modèle de groupe '+
      number(model.candidateError,1)+' %, modèle global '+number(model.fallbackError,1)+' %. ' : '')+
    'Chaque classe de pente retenue couvre au moins 300 m et contient 10 portions. Les vitesses sont limitées aux valeurs de bord hors des pentes apprises.';
  if (model.references?.length) info.textContent += ' Courses du groupe : '+model.references.join(', ')+'.';
  if (model.morphologyWeighted && model.localWeight > 0) info.textContent += ' Pondération par densité de D+, fréquence, longueur et amplitude des ascensions, et répartition du relief.';
  if (model.scope === 'manual') info.textContent = model.status+' · progression à allure constante sur la distance du parcours.';
}
function showSegmentation(container, classification) {
  const shares=classification.climbShares || {small:0,intermediate:0,large:classification.longReliefShare || 0};
  metrics(container,[
    ['Profil de relief',profileLabel(classification)],
    ['Classe de distance',classification.distanceLabel],
    ['D+ lissé par km',number(classification.ascentDensity ?? classification.reliefDensity/2,1)+' m/km'],
    ['Petites / moyennes / grandes ascensions',
      [shares.small,shares.intermediate,shares.large].map(v=>number(v*100,0)+' %').join(' / ')+' du D+'],
    ['Ascensions par 10 km',number(classification.climbsPer10Km || 0,1)],
    ['Gain médian des ascensions',meters(classification.medianClimbGain || 0)],
    ['Longueur médiane des ascensions',km(classification.medianClimbLength || 0)],
    ['Part des portions au-delà de ±3 %',number((classification.steepDistanceShare || 0)*100,0)+' %'],
    ['Échantillonnage cible',classification.sampling+' m']
  ]);
  if (classification.classificationReason) container.append(element('p',classification.classificationReason));
  container.classList.add('metrics');
}
// Catalogue affiché et sélection explicite du modèle d'analyse.
let availableModels;
function showModelCatalog(data) {
  const previousPrediction = $('prediction-model').value;
  availableModels = [data.model,...data.models,data.inclinationModel];
  $('model-groups').replaceChildren();
  $('model-select').replaceChildren();
  const globalOption = element('option','Toutes les références · modèle global');
  globalOption.value = 'global';
  $('model-select').append(globalOption);
  $('prediction-model').replaceChildren();
  for (const [value,label] of [['auto','Sélection automatique selon le parcours'],
    ['global','Modèle global · toutes les références'],
    ['inclination','Test · classes d’inclinaison en montée et descente']]) {
    const option = element('option',label);
    option.value = value;
    $('prediction-model').append(option);
  }
  data.models.forEach((model,index) => {
    const option = element('option',profileLabel(model)+' · '+model.distanceLabel+' · '+model.exactCount+' référence(s)');
    option.value = String(index+1);
    $('model-select').append(option);
    const predictionOption = element('option',profileLabel(model)+' · '+model.distanceLabel+
      ' · '+model.exactCount+' référence(s) du groupe');
    predictionOption.value = model.profile+':'+model.distanceClass;
    $('prediction-model').append(predictionOption);
    const row = $('model-groups').insertRow();
    const button = element('button',profileLabel(model));
    button.type = 'button';
    button.addEventListener('click',() => {
      $('model-select').value = String(index+1);
      selectDisplayedModel();
    });
    row.insertCell().append(button);
    for (const value of [model.distanceLabel,model.exactCount,model.sampling+' m',
      model.error === null ? '—' : number(model.error,1)+' % (n='+model.exactCount+')',model.status]) {
      row.insertCell().textContent = value;
    }
  });
  if (Array.from($('prediction-model').options).some(option => option.value === previousPrediction)) {
    $('prediction-model').value = previousPrediction;
  }
  const inclinationOption = element('option','Test · classes d’inclinaison en montée et descente');
  inclinationOption.value = 'inclination';
  $('model-select').append(inclinationOption);
  metrics($('validation-comparison'),[
    ['Référence historique à 100 m · erreur médiane',data.baselineError === null ? '—' : number(data.baselineError,1)+' %'],
    ['Modèle courant · erreur médiane',data.error === null ? '—' : number(data.error,1)+' %'],
    ['Référence historique à 100 m · erreur moyenne',data.baselineMeanError === null ? '—' : number(data.baselineMeanError,1)+' %'],
    ['Modèle courant · erreur moyenne',data.meanError === null ? '—' : number(data.meanError,1)+' %']
  ]);
  $('validation-note').textContent = 'La référence historique à 100 m est le modèle initial, pas la version 1.3. Validation sur courses exclues de l’apprentissage : chaque course est prédite avec toutes les autres. Le choix entre modèle de groupe et modèle global est lui-même validé sur les seules références d’apprentissage. Le modèle de groupe doit réduire l’erreur moyenne au-delà d’une marge égale à une erreur standard des écarts appariés. Avec moins de trois références du profil, le modèle de groupe reste fortement régularisé. La comparaison inclut la modification de l’échantillonnage. Les groupes peu représentés ont une estimation d’erreur fragile ; un groupe vide utilise un modèle de repli.';
  drawModel(data.model);
  const experiment = data.inclinationTest;
  metrics($('inclination-test-metrics'),[
    ['Modèle actuel · erreur médiane',data.error === null ? '—' : number(data.error,1)+' %'],
    ['Candidat inclinaison · erreur médiane',experiment.medianError === null ? '—' : number(experiment.medianError,1)+' %'],
    ['Modèle actuel · erreur moyenne',data.meanError === null ? '—' : number(data.meanError,1)+' %'],
    ['Candidat inclinaison · erreur moyenne',experiment.meanError === null ? '—' : number(experiment.meanError,1)+' %']
  ]);
  $('inclination-test-note').textContent = 'Chaque résultat est calculé sur une course exclue de l’apprentissage ('+
    experiment.courseCount+' courses testées). Les écarts par pente comparent les temps cumulés sur les portions horodatées. '+
    'Des erreurs de sens opposé peuvent se compenser dans ces cumuls. Les pauses restent comprises dans les temps.';
  $('inclination-test-bands').replaceChildren();
  for (const band of experiment.bands) {
    const row = $('inclination-test-bands').insertRow();
    for (const value of [band.label,km(band.distance),number(band.count),
      band.currentError === null ? '—' : number(band.currentError,1)+' %',
      band.experimentalError === null ? '—' : number(band.experimentalError,1)+' %']) {
      row.insertCell().textContent = value;
    }
  }
}
function selectDisplayedModel() {
  const value = $('model-select').value;
  const index = value === 'inclination' ? availableModels.length-1 : value === 'global' ? 0 : Number(value);
  if (availableModels) drawModel(availableModels[index]);
  Array.from($('model-groups').rows).forEach((row,i)=>{ row.hidden = index > 0 && index < availableModels.length-1 && i !== index-1; });
}
$('model-select').addEventListener('change',selectDisplayedModel);
// Arborescence des références et résultats calculés au démarrage.
// Classements indépendants : aucune comparaison de rang entre deux groupes.
function rankReferenceGroups(courses, sort) {
    const performance = c => c.actual/(c.distance/1000+c.ascent/100);
    const fitError = c => c.groupEstimated == null ? Infinity : Math.abs(c.groupEstimated/c.actual-1);
    const groups = new Map();
    for (const course of courses) {
      const key = course.classification.profile+':'+course.classification.distanceClass;
      if (!groups.has(key)) groups.set(key,[]);
      groups.get(key).push(course);
    }
    const rank = new Map(), closest = new Set();
    for (const peers of groups.values()) {
      [...peers].sort((a,b)=>performance(a)-performance(b)).forEach((c,i)=>rank.set(c,i+1));
      [...peers].filter(c=>c.groupEstimated != null).sort((a,b)=>fitError(a)-fitError(b)).slice(0,3).forEach(c=>closest.add(c));
    }
    const groupOrder = c => RELIEF_PROFILES.indexOf(c.classification.profile)*DISTANCE_IDS.length+
      DISTANCE_IDS.indexOf(c.classification.distanceClass);

    courses.sort((a,b)=>groupOrder(a)-groupOrder(b) || (sort==='fit' ? fitError(a)-fitError(b) : sort==='name' ? a.name.localeCompare(b.name,'fr') : sort==='distance' ? a.distance-b.distance : performance(a)-performance(b)));
    return {groups,rank,closest,performance};
}

let referenceCourses=[], referenceRows=[], referenceHeaders=[], histogramFilter=null;
let histogramCourses=[], histogramBars=[];
async function showReferences() {
  try {
    const response = await fetch('/api/references');
    if (!response.ok) throw Error('Chargement des références impossible.');
    const data = await response.json();
    referenceCourses=data.courses; referenceRows=[]; referenceHeaders=[];
    const {groups,rank,closest,performance}=rankReferenceGroups(data.courses,$('reference-sort').value);
    $('cache-info').textContent = data.cache ?
      (data.cache.restored ? 'Modèles restaurés du cache local. ' : 'Modèles recalculés. ')+
      data.cache.reused+' / '+data.cache.total+' références réutilisées sans nouvelle analyse.' : '';
    $('courses').replaceChildren();
    const groupErrors=data.courses.filter(c=>c.groupEstimated != null).map(c=>Math.abs(c.groupEstimated/c.actual-1)*100).sort((a,b)=>a-b);
    const mid=Math.floor(groupErrors.length/2);
    const groupMedian=groupErrors.length ? (groupErrors.length%2 ? groupErrors[mid] : (groupErrors[mid-1]+groupErrors[mid])/2) : null;
    metrics($('reference-metrics'), [
      ['Courses analysées',data.courses.length],
      ['Distance totale',km(data.courses.reduce((sum,c) => sum+c.distance,0))],
      ['Erreur médiane · groupes',groupMedian === null ? '—' : number(groupMedian,1)+' %'],
      ['Pauses estimées au total',time(data.courses.reduce((sum,c) => sum+c.pauses.duration,0))]
    ]);
    $('reference-status').textContent = data.skipped.length ? 'Fichiers écartés · '+data.skipped.join(' · ') : '';
    let previousGroup;
    for (const [index,course] of data.courses.entries()) {
      const group = course.classification.profile+':'+course.classification.distanceClass;
      if (group !== previousGroup) {
        const header = $('courses').insertRow(); header.className='reference-group';
        const title = header.insertCell(); title.colSpan=8;
        title.textContent=profileLabel(course.classification)+' · '+course.classification.distanceLabel+
          ' · '+groups.get(group).length+' course(s)';
        referenceHeaders.push({row:header,group});
        previousGroup=group;
      }
      const row = $('courses').insertRow();
      if (closest.has(course)) row.classList.add('closest-reference');
      const position = rank.get(course);
      const badge = closest.has(course) ? ' ★ Proche du modèle du groupe' : '';
      const button = element('button',course.name);
      button.type = 'button';
      button.setAttribute('aria-expanded','false');
      button.setAttribute('aria-controls','course-detail-'+index);
      button.textContent = '▸ #'+position+' '+course.name+badge;
      const branch = document.createElement('tr');
      branch.id = 'course-detail-'+index;
      branch.className = 'branch';
      branch.hidden = true;
      const cell = branch.insertCell();
      cell.colSpan = 8;
      const profileDetails = element('details','');
      profileDetails.open = true;
      profileDetails.append(element('summary','Profil et dénivelé'));
      const figure = element('figure','');
      profileDetails.append(figure);
      const terrainDetails = element('details','');
      terrainDetails.open = true;
      terrainDetails.append(element('summary','Montée, plat et descente'));
      const terrain = element('div','');
      terrain.className = 'scroll';
      terrainDetails.append(terrain);
      const pauseDetails = element('details','');
      pauseDetails.append(element('summary','Pauses et enregistrement GPX'));
      const pauseMetrics = element('div','');
      pauseMetrics.className = 'metrics';
      metrics(pauseMetrics,[
        ['Temps de pause estimé',time(course.pauses.duration)],
        ['Pauses détectées',course.pauses.count],
        ['Interruptions d’enregistrement',time(course.pauses.unobserved)]
      ]);
      const pauseNote = element('p','Pauses estimées sur les points GPX d’origine : vitesse inférieure ou égale à 0,5 km/h pendant au moins une minute. Les intervalles de plus de cinq minutes et les coupures entre segments sont comptés comme interruptions d’enregistrement.');
      pauseNote.className = 'muted notice';
      pauseDetails.append(pauseMetrics,pauseNote);
      cell.append(profileDetails,terrainDetails,pauseDetails);
      const classificationDetails = element('details','');
      classificationDetails.append(element('summary','Segmentation et échantillonnage'));
      const classification = element('div','');
      showSegmentation(classification,course.classification);
      classificationDetails.append(classification,
        element('p',course.model ? course.model.status+' · '+course.model.exactCount+
          ' référence(s) du groupe disponibles pour cette validation.' : 'Validation indisponible.'));
      if (course.inclinationEstimated !== null) {
        classificationDetails.append(element('p','Test par inclinaison · '+time(course.inclinationEstimated)+
          ' · écart '+number((course.inclinationEstimated/course.actual-1)*100,1)+' %'));
      }
      cell.append(classificationDetails);
      const entry={row,branch,course,expanded:false};
      let loaded = false;
      const setExpanded = value => {
        entry.expanded=value; branch.hidden=!value;
        button.setAttribute('aria-expanded',String(!branch.hidden));
        button.textContent = (branch.hidden ? '▸ ' : '▾ ')+'#'+position+' '+course.name+badge;
        if (!loaded) {
          profile(figure,course.name+' · Profil altimétrique',course);
          showTerrain(terrain,course,true);
          loaded = true;
        }
      };
      button.addEventListener('click',()=>setExpanded(!entry.expanded));
      entry.expand=()=>{setExpanded(true);row.scrollIntoView?.({behavior:'smooth',block:'center'});};
      referenceRows.push(entry);
      const nameCell=row.insertCell(); nameCell.setAttribute('data-label','Classement / course'); nameCell.append(button);
      const error = course.groupEstimated == null ? null : (course.groupEstimated/course.actual-1)*100;
      for (const value of [km(course.distance),meters(course.ascent),meters(course.descent),time(course.actual),time(course.pauses.duration),
        error === null ? 'Indisponible · groupe sans autre référence exploitable' : time(course.groupEstimated),(error === null ? '—' : (error > 0 ? '+' : '')+number(error,1)+' %')+' · '+time(performance(course))+'/km-effort']) {
        const cell=row.insertCell(); cell.textContent=value;
        cell.setAttribute('data-label',['Distance','D+','D−','Temps GPX','Pauses estimées','Estimé · groupe','Écart / performance'][row.cells.length-2]);
      }
      $('courses').append(branch);
    }
    $('reference-table').hidden = false;
    showModelCatalog(data);
    drawReferenceHistogram(data.courses);
    applyHistogramSelection();
    const previousSimulationModel=$('simulation-model').value;
    $('simulation-model').replaceChildren();
    for (const source of $('prediction-model').options) {
      const option=element('option',source.textContent); option.value=source.value;
      $('simulation-model').append(option);
    }
    if (Array.from($('simulation-model').options).some(o=>o.value===previousSimulationModel)) {
      $('simulation-model').value=previousSimulationModel;
    }
    if(typeof restoreDeferredChoices==='function')restoreDeferredChoices();
    await refreshSelection();
    return true;
  } catch (error) {
    $('reference-status').textContent = error.message;
    return false;
  }
}
// État du parcours actif. La chronologie est commune aux deux représentations.
let map, layer, routeData, runner, offlineRunner, offlineProject, routeRenderer, tileLayer;
let profileTracking, printView;
let scheduledDeparture = null, checkpointBindings = [];
let playbackTime = 0, animation = null, lastFrame = null;
let colorMin = 0, colorMax = 1;
// Carte et profil partagent ces fonctions afin d'utiliser la même échelle de couleurs.
function sectionValue(section) {
  const mode = $('color-mode').value;
  return mode === 'elevation' ? (section.start[2]+section.end[2])/2 : section[mode];
}
function sectionColor(section) {
  const fraction = (sectionValue(section)-colorMin) / Math.max(1e-9,colorMax-colorMin);
  return 'hsl('+(235-230*fraction)+',80%,43%)';
}
function updateLegend(data) {
  colorMin = Infinity;
  colorMax = -Infinity;
  for (const section of data.sections) {
    const value = sectionValue(section);
    colorMin = Math.min(colorMin,value);
    colorMax = Math.max(colorMax,value);
  }
  const unit = {grade:' %',speed:' km/h',elevation:' m'}[$('color-mode').value];
  $('color-low').textContent = number(colorMin,1)+unit;
  $('color-high').textContent = number(colorMax,1)+unit;
}
function updateCheckpointTimes() {
  for (const {mark,info,clock,marker} of checkpointBindings) {
    const [distance,seconds,,,,label] = mark;
    const date = scheduledDeparture ? passageDate(scheduledDeparture,seconds) : '';
    info.textContent = label+' · '+km(distance)+' · '+time(seconds)+(date ? ' · '+date : '');
    clock.textContent = date;
    if (marker) marker.getTooltip().update();
  }
}
function customWaypoint(mark, data) {
  return (data.customWaypoints || []).find(point => Math.abs(point.km*1000-mark[0])<1e-5);
}
function drawOfflineTrace(data) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 760 360');
  const latitudes = data.trace.flat().map(point => point[0]);
  const latitude = latitudes.reduce((sum,value) => sum + value,0) / latitudes.length;
  const longitudeScale = Math.cos(latitude * Math.PI / 180);
  let west = Infinity, east = -Infinity, south = Infinity, north = -Infinity;
  for (const segment of data.trace) {
    for (const [lat,lon] of segment) {
      west = Math.min(west,lon);
      east = Math.max(east,lon);
      south = Math.min(south,lat);
      north = Math.max(north,lat);
    }
  }
  const scale = Math.min(720 / Math.max(1e-9,(east-west)*longitudeScale),
    320 / Math.max(1e-9,north-south));
  const project = ([lat,lon]) => [
    380 + (lon-(east+west)/2)*longitudeScale*scale,
    180 - (lat-(north+south)/2)*scale
  ];
  offlineProject = project;
  for (const section of data.sections) {
    const line = document.createElementNS(ns,'polyline');
    line.setAttribute('points',[section.start,section.end].map(point => project(point).join(',')).join(' '));
    line.setAttribute('fill','none');
    line.setAttribute('stroke',sectionColor(section));
    line.setAttribute('stroke-width','3');
    svg.append(line);
  }
  for (const mark of data.marks) {
    const [distance,seconds,lat,lon,,label] = mark;
    const [x,y] = project([lat,lon]);
    const pin = document.createElementNS(ns,'circle');
    pin.setAttribute('cx',x);
    pin.setAttribute('cy',y);
    pin.setAttribute('r','4');
    pin.setAttribute('fill','#bd5228');
    const title = document.createElementNS(ns,'title');
    pin.append(title);
    svg.append(pin);
    const labelNode = svgElement('text',{x:x+6,y:y-6,'font-size':10,fill:'#152d2a',
      stroke:'#fff','stroke-width':3,'paint-order':'stroke'});
    labelNode.textContent = km(distance);
    const custom = customWaypoint(mark,data);
    if (custom?.comment) labelNode.textContent += ' · '+custom.comment;
    svg.append(labelNode);
    const clock = svgElement('text',{x:x+6,y:y+7,'font-size':9,fill:'#152d2a',
      stroke:'#fff','stroke-width':3,'paint-order':'stroke',class:'passage-clock'});
    svg.append(clock);
    checkpointBindings.push({mark,info:title,clock});
  }
  offlineRunner = svgElement('circle',{r:7,fill:'#182d32',stroke:'#fff','stroke-width':3,class:'playback-marker'});
  svg.append(offlineRunner);
  $('map').replaceChildren(element('p','Trace GPX · fond cartographique indisponible'),svg);
}
function drawMap(data, fitBounds=true) {
  updateLegend(data);
  checkpointBindings = [];
  if (!window.L) {
    drawOfflineTrace(data);
    updateCheckpointTimes();
    return;
  }
  if (!map) {
    map = L.map('map');
    routeRenderer = L.svg({padding:0.3});
    tileLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
      maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);
  }
  if (layer) layer.remove();
  layer = L.layerGroup().addTo(map);
  const line = L.polyline(data.trace,{color:'#fff',weight:9,opacity:1,renderer:routeRenderer,
    interactive:false}).addTo(layer);
  for (const section of data.sections) {
    L.polyline([section.start.slice(0,2),section.end.slice(0,2)],{
      color:sectionColor(section),weight:5,opacity:1,renderer:routeRenderer
    }).addTo(layer).bindTooltip(element('span',
      'Pente '+number(section.grade,1)+' % · Vitesse '+number(section.speed,2)+' km/h'));
  }
  for (const mark of data.marks) {
    const [distance,seconds,lat,lon,,label] = mark;
    const tooltip = element('div','');
    const clock = element('span','');
    clock.className = 'passage-clock';
    tooltip.append(element('span',km(distance)),clock);
    const custom = customWaypoint(mark,data);
    if (custom?.comment) {
      const comment = element('span',custom.comment);
      comment.className = 'checkpoint-comment';
      tooltip.append(comment);
    }
    const info = element('span','');
    const marker = L.circleMarker([lat,lon],{radius:6,color:'#fff',fillColor:'#bd5228',fillOpacity:1,
      renderer:routeRenderer})
      .addTo(layer).bindTooltip(tooltip,
        {permanent:true,direction:label === 'Départ' ? 'bottom' : 'top',className:'checkpoint-label'})
      .bindPopup(info);
    checkpointBindings.push({mark,info,clock,marker});
  }
  runner = L.circleMarker(data.sections[0].start.slice(0,2),{
    radius:8,color:'#fff',weight:3,fillColor:'#182d32',fillOpacity:1,
    renderer:routeRenderer,className:'playback-marker',interactive:false
  }).addTo(layer);
  updateCheckpointTimes();
  map.invalidateSize();
  if (fitBounds) map.fitBounds(line.getBounds(),{padding:[22,22],maxZoom:16});
}
function pausePlayback() {
  if (animation !== null) cancelAnimationFrame(animation);
  animation = null;
  lastFrame = null;
  $('play').textContent = '▶ Lire la trace';
}
// Une recherche dans la chronologie détermine à la fois position, altitude et date.
function positionPlayback(seconds) {
  if (!routeData) return;
  playbackTime = Math.max(0,Math.min(routeData.duration,seconds));
  const sections = routeData.sections;
  let low = 0, high = sections.length-1;
  while (low < high) {
    const middle = Math.floor((low+high)/2);
    if (sections[middle].endTime <= playbackTime) low = middle+1;
    else high = middle;
  }
  const section = sections[low];
  const fraction = Math.max(0,Math.min(1,
    (playbackTime-section.time) / (section.endTime-section.time)));
  const position = section.start.map((value,i) => value+(section.end[i]-value)*fraction);
  if (runner) runner.setLatLng(position.slice(0,2));
  if (offlineRunner && offlineProject) {
    const [x,y] = offlineProject(position);
    offlineRunner.setAttribute('cx',x);
    offlineRunner.setAttribute('cy',y);
  }
  $('progress').value = playbackTime/routeData.duration*1000;
  const distance = section.distance+(section.endDistance-section.distance)*fraction;
  if (profileTracking) {
    const [x,y] = profileTracking.project(distance,position[2]);
    profileTracking.guide.setAttribute('x1',x);
    profileTracking.guide.setAttribute('x2',x);
    profileTracking.dot.setAttribute('cx',x);
    profileTracking.dot.setAttribute('cy',y);
  }
  $('play-position').textContent = time(playbackTime)+' / '+time(routeData.duration)+
    ' · '+km(distance)+' · '+meters(position[2])+' · '+number(section.speed,2)+' km/h'+
    (scheduledDeparture ? ' · '+passageDate(scheduledDeparture,playbackTime) : '');
}
function dominantTerrain(start,end,sections) {
  if (end <= start) return '—';
  const distances = {Plat:0,Montée:0,Descente:0};
  for (const section of sections) {
    const overlap = Math.max(0,Math.min(end,section.endDistance)-Math.max(start,section.distance));
    const terrain = section.grade > 3 ? 'Montée' : section.grade < -3 ? 'Descente' : 'Plat';
    distances[terrain] += overlap;
  }
  const dominant = Object.keys(distances).reduce((best,name) =>
    distances[name] > distances[best]+1e-6 ? name : best,'Plat');
  return {Montée:'↗ Montée',Plat:'→ Plat',Descente:'↘ Descente'}[dominant];
}
function refreshMapSize() {
  requestAnimationFrame(() => {
    if (map) {
      map.invalidateSize({animate:false});
      if (routeData) map.fitBounds(L.latLngBounds(routeData.trace.flat()),
        {padding:[35,35],maxZoom:16,animate:false});
    }
  });
}
function updateFullscreen() {
  const expanded = document.fullscreenElement === $('map-panel') || $('map-panel').classList.contains('expanded');
  $('fullscreen').textContent = expanded ? '⛶ Quitter le plein écran' : '⛶ Carte en plein écran';
  $('fullscreen').setAttribute('aria-pressed',String(expanded));
  refreshMapSize();
}
$('fullscreen').addEventListener('click',async () => {
  const panel = $('map-panel');
  if (document.fullscreenElement === panel) await document.exitFullscreen();
  else if (panel.classList.contains('expanded')) panel.classList.remove('expanded');
  else {
    try { await panel.requestFullscreen(); }
    catch { panel.classList.add('expanded'); }
  }
  updateFullscreen();
});
document.addEventListener('fullscreenchange',updateFullscreen);
document.addEventListener('keydown',event => {
  if (event.key === 'Escape' && $('map-panel').classList.contains('expanded')) {
    $('map-panel').classList.remove('expanded');
    updateFullscreen();
  }
});
// L'impression sauvegarde le cadrage, ajuste la carte, puis restaure la vue.
function preparePrint() {
  if (!routeData) return;
  pausePlayback();
  if (!printView) {
    printView = map ? {center:map.getCenter(),zoom:map.getZoom()} : {};
    $('print-info').textContent = 'État de prédiction · '+new Date().toLocaleString('fr-FR')+
      ' · Repères tous les '+$('spacing').value+' km · Coloration : '+
      $('color-mode').selectedOptions[0].textContent;
  }
  document.body.classList.add('print-preparing');
  if (map) {
    map.invalidateSize({pan:false});
    map.fitBounds(L.latLngBounds(routeData.trace.flat()),{padding:[35,35],maxZoom:16,animate:false});
  }
}
function restorePrint() {
  document.body.classList.remove('print-preparing');
  if (map && printView?.center) {
    map.invalidateSize({pan:false});
    map.setView(printView.center,printView.zoom,{animate:false});
  }
  printView = null;
}
window.addEventListener('beforeprint',preparePrint);
window.addEventListener('afterprint',restorePrint);
$('print').addEventListener('click',async () => {
  if (!routeData) return;
  updateSchedule();
  if (!$('departure').reportValidity()) return;
  $('print').disabled = true;
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    $('map-panel').classList.remove('expanded');
    updateFullscreen();
    preparePrint();
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    if (tileLayer?.isLoading()) {
      await new Promise(resolve => {
        const finish = () => { clearTimeout(timeout); tileLayer.off('load',finish); resolve(); };
        const timeout = setTimeout(finish,3000);
        tileLayer.once('load',finish);
      });
    }
    window.print();
  } catch (error) {
    $('status').textContent = 'Impression impossible. '+error.message;
  } finally {
    restorePrint();
    $('print').disabled = false;
  }
});
// L'animation utilise le temps écoulé réel entre images et le multiplicateur choisi.
function playbackFrame(timestamp) {
  if (lastFrame !== null) positionPlayback(playbackTime+
    (timestamp-lastFrame)/1000*Number($('play-speed').value));
  lastFrame = timestamp;
  if (playbackTime >= routeData.duration) {
    pausePlayback();
    return;
  }
  animation = requestAnimationFrame(playbackFrame);
}
$('color-mode').addEventListener('change',() => {
  if (routeData) {
    drawMap(routeData,false);
    profileTracking = profile($('result-profile'),'Profil altimétrique',routeData);
    positionPlayback(playbackTime);
  }
});
$('play').addEventListener('click',() => {
  if (!routeData) return;
  if (animation !== null) {
    pausePlayback();
    return;
  }
  if (playbackTime >= routeData.duration) positionPlayback(0);
  $('play').textContent = 'Ⅱ Pause';
  animation = requestAnimationFrame(playbackFrame);
});
$('progress').addEventListener('input',() => {
  pausePlayback();
  if (routeData) positionPlayback(Number($('progress').value)/1000*routeData.duration);
});
$('play-speed').addEventListener('input',() => {
  $('play-speed-value').value = '×'+$('play-speed').value;
});
$('select').addEventListener('click',() => $('file').click());
let selectedFile;
$('file').addEventListener('change',() => {
  const file = $('file').files[0];
  if (!file) return;
  if (selectedFile && (selectedFile.name !== file.name || selectedFile.size !== file.size)) {
    customPoints = [];
    renderWaypoints();
  }
  selectedFile = file;
  $('calculate-route').disabled = false;
  $('file').value = '';
  analyze(file);
});
$('spacing').addEventListener('input',() => {
  $('spacing-value').value = $('spacing').value + ' km';
});
$('spacing').addEventListener('change',() => {
  if (selectedFile) analyze(selectedFile);
});
$('prediction-model').addEventListener('change',() => {
  if (selectedFile) analyze(selectedFile);
});
let startupReady = false;
let customPoints = [];
function parseClock(value, total=false) {
  const pattern = total ? /^(\d+):([0-5]\d)(?::([0-5]\d))?$/ : /^(\d+):([0-5]\d)$/;
  const match = value.trim().match(pattern);
  if (!match) throw Error(total ? 'Durée attendue au format heures:minutes:secondes.' : 'Allure attendue au format minutes:secondes par km.');
  const seconds = total ? Number(match[1])*3600+Number(match[2])*60+Number(match[3] || 0) :
    Number(match[1])*60+Number(match[2]);
  if (!Number.isFinite(seconds) || seconds <= 0) throw Error('La durée ou l’allure doit être positive.');
  return seconds;
}
function readGpxSource(file) {
  return new Promise((resolve,reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(Error('Lecture du fichier GPX impossible.'));
    reader.readAsDataURL(file);
  });
}
const gpxImportMetadata = new WeakMap();
async function readGpx(file) {
  const mode = $('gpx-conversion').value || 'compact';
  const panel = $('gpx-import-reports');
  const row = document.createElement('p');
  row.textContent = file.name+' · contrôle et conversion en cours…';
  panel.append(row);
  while (panel.children.length > 20) {
    const old = panel.firstChild.querySelector('a'); if(old) URL.revokeObjectURL(old.href);
    panel.removeChild(panel.firstChild);
  }
  try {
    if (file.size > 100 * 1024 * 1024) throw Error('Source GPX limitée à 100 Mio.');
    const converted = await postJSON('/api/gpx/convert',{gpx:await readGpxSource(file),mode,preview:!$('screen-conversion').hidden});
    const r = converted.report;
    gpxImportMetadata.set(file,r);
    if (converted.preview) showConversionPreview(converted.preview,file,r);
    const size = value => (value / (1024*1024)).toFixed(2)+' Mio';
    row.textContent = file.name+' · '+size(r.originalBytes)+' → '+size(r.convertedBytes)+
      ' · gain '+r.gainPercent+' % · '+r.pointCount+' points · '+
      (r.optimized ? 'Optimisé' : r.optimizable ? 'Optimisation disponible avec le traitement choisi' : 'Déjà compact pour ce traitement')+
      ' · '+(r.recordedCompatible ? 'Compatible avec les temps enregistrés' : 'Temps enregistrés indisponibles : '+r.recordedError)+
      (r.removedExtensions ? ' · extensions des capteurs retirées' : '');
    const link = document.createElement('a');
    link.textContent = ' Télécharger le GPX préparé';
    link.href = URL.createObjectURL(new Blob([Uint8Array.from(atob(converted.gpx),c=>c.charCodeAt(0))],{type:'application/gpx+xml'}));
    link.download = file.name.replace(/\.gpx$/i,'')+'-'+mode+'.gpx';
    row.append(link);
    if (!r.importable) throw Error('Le résultat dépasse encore 20 Mio. Essayez le mode allégé pour le simulateur.');
    return converted.gpx;
  } catch (error) {
    row.append(document.createTextNode(' · '+error.message));
    throw error;
  }
}
$('convert-gpx-files').addEventListener('click',() => $('conversion-files').click());
$('conversion-files').addEventListener('change',async() => {
  const files = Array.from($('conversion-files').files);
  $('conversion-files').value = '';
  $('convert-gpx-files').disabled = true;
  try {
    for (const file of files) {
      try { await readGpx(file); } catch (_) { /* Le bilan individuel affiche l’erreur. */ }
    }
  } finally { $('convert-gpx-files').disabled = false; }
});
function updatePredictionMode() {
  const mode = $('prediction-mode').value;
  $('model-fields').hidden = mode !== 'model';
  $('manual-total-fields').hidden = mode !== 'total';
  $('manual-pace-fields').hidden = mode !== 'pace';
  $('select').disabled = mode === 'model' && !startupReady;
}
$('prediction-mode').addEventListener('change',() => {
  updatePredictionMode();
  const mode = $('prediction-mode').value;
  const supplied = mode === 'model' || (mode === 'total' ? $('manual-total').value : $('manual-pace').value).trim();
  if (selectedFile && supplied) analyze(selectedFile);
});
for (const id of ['manual-total','manual-pace']) {
  $(id).addEventListener('change',() => { if (selectedFile) analyze(selectedFile); });
}
$('calculate-route').addEventListener('click',() => { if (selectedFile) analyze(selectedFile); });
function renderWaypoints() {
  $('waypoint-list').replaceChildren();
  customPoints.sort((a,b) => a.km-b.km);
  customPoints.forEach((point,index) => {
    const row = $('waypoint-list').insertRow();
    row.insertCell().textContent = number(point.km,3);
    row.insertCell().textContent = point.comment;
    const remove = element('button','Retirer');
    remove.type = 'button';
    remove.addEventListener('click',() => {
      customPoints.splice(index,1);
      renderWaypoints();
      if (selectedFile) analyze(selectedFile);
    });
    row.insertCell().append(remove);
  });
}
$('add-waypoint').addEventListener('click',() => {
  const value = $('waypoint-km').value;
  const distance = Number(value);
  if (!value || !Number.isFinite(distance) || distance < 0 ||
    (routeData && distance*1000 > routeData.distance+1e-6)) {
    $('status').textContent = 'Saisissez une distance située sur le parcours.';
    return;
  }
  const point = {km:distance,comment:$('waypoint-comment').value.trim()};
  const existing = customPoints.findIndex(item => Math.abs(item.km-distance)<1e-9);
  if (existing>=0) customPoints[existing] = point;
  else customPoints.push(point);
  renderWaypoints();
  if (selectedFile) analyze(selectedFile);
});
// Une réponse d'analyse contient toutes les données nécessaires à la carte,
// au profil, aux horaires et au tableau. Les commandes sont bloquées pendant l'appel.
let analysisVersion = 0;
function analysisBusy(value) {
  $('select').disabled = value;
  $('spacing').disabled = value;
  $('prediction-model').disabled = value || !startupReady;
  $('prediction-mode').disabled = value;
  $('analysis-strategy-fields').disabled = value;
  $('calculate-route').disabled = value || !selectedFile;
  $('recalculate').disabled = value || !routeData;
  if (!value) updatePredictionMode();
}
function analysisStrategy() {
  const strategy={split:$('analysis-split').value || 'even'};
  for(const [key,id,min,max] of [['adjustmentPercent','analysis-adjustment',-50,100],
    ['splitPercent','analysis-split-percent',0,40],['climbPercent','analysis-climb',-50,100]]) {
    const input=$(id),value=Number(input.value || 0);
    if(!Number.isFinite(value) || value<min || value>max)throw Error('Vérifiez les pourcentages de la stratégie d’allure.');
    strategy[key]=value;
  }
  return strategy;
}
for(const id of ['analysis-adjustment','analysis-split','analysis-split-percent','analysis-climb']) {
  $(id).addEventListener('change',()=>{
    if(selectedFile)$('status').textContent='Stratégie modifiée : cliquez sur Calculer le parcours pour actualiser la prédiction.';
  });
}
async function analyze(file) {
  const version = ++analysisVersion;
  const mode = $('prediction-mode').value;
  const interval = $('spacing').value;
  const options = {mode,retainSource:true,interval:Number(interval),model:$('prediction-model').value,
    waypoints:customPoints.map(point => ({...point}))};
  try {
    options.strategy = analysisStrategy();
    if (mode === 'total') options.totalSeconds = parseClock($('manual-total').value,true);
    if (mode === 'pace') options.paceSeconds = parseClock($('manual-pace').value);
  } catch (error) {
    $('status').textContent = error.message;
    analysisBusy(false);
    return;
  }
  pausePlayback();
  routeData = null;
  analysisBusy(true);
  $('status').classList.remove('error');
  $('status').textContent = 'Analyse en cours…';
  $('result').hidden = true;
  try {
    options.gpx = await readGpx(file);
    if (version !== analysisVersion) return;
    const response = await fetch('/api/prediction',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(options)
    });
    const data = await response.json();
    if (version !== analysisVersion) return;
    if (!response.ok) throw Error(data.error);
    $('filename').textContent = file.name;
    $('file-info').textContent = 'Fichier GPX · '+number(file.size/1024,1)+
      ' Ko · '+number(data.trace.reduce((sum,segment) => sum+segment.length,0))+
      ' points · '+data.trace.length+' segment(s)';
    metrics($('result-metrics'), [['Distance',km(data.distance)],['Temps total estimé',time(data.duration)],
      ['Temps hors pauses estimé',data.movingDuration === null ? '—' : time(data.movingDuration)],
      ['Pauses estimées',data.pauses.duration === null ? '—' : time(data.pauses.duration)],
      ['Dénivelé positif',meters(data.ascent)],['Dénivelé négatif',meters(data.descent)]]);
    $('model-choice-summary').textContent = data.model.selectionLabel+' · '+data.model.status;
    $('pause-info').textContent = mode !== 'model' ? data.pauses.status :
      data.pauses.status+' · '+data.pauses.referenceCount+
      ' référence(s). Le temps total est décomposé en temps hors pauses et pauses estimées. '+
      'Les pauses sont réparties proportionnellement au temps écoulé pour calculer les cumuls aux repères. '+
      'Les lieux d’arrêt restent à définir. Part médiane du temps non enregistré dans les références : '+
      number(data.pauses.unknownFraction*100,1)+' %.';
    const arrival = element('div','');
    arrival.className = 'metric arrival-metric';
    const arrivalDate = element('strong','Départ à renseigner');
    arrivalDate.id = 'arrival-estimate';
    arrival.append(element('small','Arrivée prévue'),arrivalDate);
    $('result-metrics').append(arrival);
    showSegmentation($('prediction-segmentation'),data.classification);
    $('analysis-strategy-summary').textContent = data.strategy?.label || '';
    drawModel(data.model,$('prediction-model-chart'),$('prediction-model-info'));
    $('marks').replaceChildren();
    $('marks-caption').textContent = 'Passages estimés depuis le départ · tous les '+interval+' km';
    for (const [index,[distance,seconds,,,elevation,label]] of data.marks.entries()) {
      const row = $('marks').insertRow();
      const terrain = index === 0 ? '—' : dominantTerrain(data.marks[index-1][0],distance,data.sections);
      const cumulativePause = data.pauses.fraction === null ? '—' : time(seconds*data.pauses.fraction);
      for (const value of [label,km(distance),time(seconds),'—',meters(elevation),terrain,cumulativePause]) row.insertCell().textContent = value;
    }
    updateLegend(data);
    profileTracking = profile($('result-profile'),'Profil altimétrique',data);
    showTerrain($('result-terrain'),data);
    $('result').hidden = false;
    routeData = data;
    if(typeof scheduleStateSave==='function')scheduleStateSave();
    activeRouteKey = routeFingerprint(options.gpx);
    $('recalculate').disabled = false;
    updateSchedule();
    drawMap(data);
    positionPlayback(0);
    $('status').textContent = 'Analyse terminée.';
  } catch (error) {
    if (version === analysisVersion) {
      $('status').textContent = error.message;
      $('status').classList.add('error');
    }
  } finally {
    if (version === analysisVersion) analysisBusy(false);
  }
}
// Interroger l'état de démarrage sans bloquer l'interface. La boucle s'arrête
// lorsque les données sont chargées ou qu'une erreur de démarrage est affichée.
async function followStartup() {
  try {
    const response = await fetch('/api/startup');
    if (!response.ok) throw Error('Suivi du démarrage indisponible.');
    const startup = await response.json();
    $('startup-progress').value = Math.round(startup.progress*100);
    $('startup-message').textContent = startup.message || 'Chargement des références…';
    $('startup-detail').textContent = Math.round(startup.progress*100)+' % · '+startup.elapsed+' s'+
      (startup.total ? ' · '+startup.completed+' / '+startup.total : '');
    $('startup-watchdog').textContent = validationHealth(startup);
    $('retry-validation').hidden = startup.status !== 'error';
    if (startup.status === 'error') {
      startupReady = false;
      updatePredictionMode();
      $('startup-message').classList.add('error');
      $('reference-status').textContent = startup.message+' · Réactivez ou importez une référence chronométrée pour reconstruire le modèle.';
      $('reference-table').hidden = true;
      $('reference-metrics').replaceChildren();
      $('model-chart').replaceChildren();
      $('model-groups').replaceChildren();
      $('model-info').textContent = 'Modèle indisponible pour la sélection actuelle.';
      if ($('prediction-mode').value === 'model') {
        pausePlayback(); routeData = null; $('result').hidden = true;
      }
      return;
    }
    if (startup.status === 'ready') {
      if (await showReferences()) {
        startupReady = true;
        updatePredictionMode();
        $('prediction-model').disabled = false;
        $('startup-panel').hidden = true;
        refreshLocal();
        return;
      }
      $('startup-message').textContent = 'Nouvelle tentative de chargement des résultats…';
    }
  } catch (error) {
    $('startup-message').textContent = 'Connexion au serveur… '+error.message;
  }
  setTimeout(followStartup,1000);
}
followStartup();
updatePredictionMode();


// Bibliothèque locale. Les opérations longues publient leur progression côté serveur.
let localActivities = [];
let operationBusy = false;
async function requestJSON(path, options={}) {
  const response = await fetch(path,options);
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Action impossible.');
  return data;
}
function postJSON(path, data) {
  return requestJSON(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
}
function importFilters() {
  return {kind:$('import-kind').value,profile:$('import-profile').value || 'all',
    distanceClass:$('import-distance-class').value || 'all',minKm:$('import-min-km').value,maxKm:$('import-max-km').value,
    minDate:$('import-min-date').value,maxDate:$('import-max-date').value};
}
function filteredActivities() {
  const filters = importFilters();
  return localActivities.filter(activity =>
    (filters.kind === 'all' || activity.kind === filters.kind) &&
    (filters.profile === 'all' || activity.profile === filters.profile) &&
    (filters.distanceClass === 'all' || activity.distanceClass === filters.distanceClass) &&
    (!filters.minKm || activity.distance >= Number(filters.minKm)*1000) &&
    (!filters.maxKm || activity.distance <= Number(filters.maxKm)*1000) &&
    (!filters.minDate || activity.date >= filters.minDate) &&
    (!filters.maxDate || activity.date <= filters.maxDate));
}
function renderLocalActivities() {
  $('local-activities').replaceChildren();
  for (const activity of filteredActivities()) {
    const row = $('local-activities').insertRow();
    for (const value of [activity.date,activity.name,
      {running:'Course',cycling:'Vélo',hiking:'Rando'}[activity.kind],
      {flat:'▱ Plat / Vallonné',mountain:'▲ Intermédiaire / Montagne',sawtooth:'⋀⋀ Dents de scie',mixed:'∿ Mixte'}[activity.profile] || 'Non classé',
      {very_short:'< 20 km',short:'20–50 km',medium:'50–100 km',long:'100–160 km',ultra:'≥ 160 km'}[activity.distanceClass] || 'Non classée',
      km(activity.distance),activity.source]) {
      row.insertCell().textContent = value;
    }
    const reference = document.createElement('input');
    reference.type = 'checkbox';
    reference.checked = Boolean(activity.reference);
    reference.disabled = operationBusy;
    reference.setAttribute('aria-label','Utiliser '+activity.name+' comme référence');
    reference.addEventListener('change',() => libraryAction('/api/local/reference',
      {id:activity.id,reference:reference.checked}));
    row.insertCell().append(reference);
  }
}
async function refreshLocal() {
  try {
    const data = await requestJSON('/api/local');
    localActivities = data.activities;
    renderLocalActivities();
    await refreshSelection();
    const garmin = await requestJSON('/api/garmin/status');
    renderGarmin(garmin);
    const operation = await requestJSON('/api/operation');
    if (operation.status === 'loading' && !operation.initial && !operationBusy) {
      libraryBusy(true);
      watchOperation().catch(error => {
        $('library-status').textContent = error.message;
        libraryBusy(false);
      });
    }
  } catch (error) {
    $('library-status').textContent = error.message;
  }
}
function renderGarmin(data) {
  $('garmin-overview').textContent = 'Garmin · '+(data.connected ? 'Compte connecté' : data.mfa ? 'Code de double authentification requis' : data.message);
  $('garmin-overview').classList[data.available ? 'remove' : 'add']('error');
  $('garmin-status').textContent = data.connected ? 'Compte Garmin connecté.' :
    data.mfa ? 'Saisissez le code de double authentification.' : data.message;
  $('garmin-mfa-fields').hidden = !data.mfa;
  $('garmin-connect').disabled = !data.available || data.mfa;
  $('garmin-disconnect').disabled = !data.connected && !data.mfa;
}
function libraryBusy(value) {
  operationBusy = value;
  for (const button of document.querySelectorAll('.library-action, #reference-selection input')) button.disabled = value;
  $('operation-progress').hidden = !value;
  renderLocalActivities();
}
async function libraryAction(path, data) {
  if (operationBusy) return;
  libraryBusy(true);
  $('library-status').textContent = 'Opération en cours…';
  try {
    await postJSON(path,data);
    await watchOperation();
  } catch (error) {
    $('library-status').textContent = error.message;
    libraryBusy(false);
    refreshLocal();
  }
}
async function watchOperation() {
  const state = await requestJSON('/api/operation');
  $('garmin-stop').disabled = !(state.kind === 'garmin' && state.status === 'loading' && state.progress < .5 && !state.cancelRequested);
  $('operation-progress').value = Math.round((state.progress || 0)*100);
  $('library-status').textContent = state.message+
    (state.total ? ' · '+state.completed+' / '+state.total : '')+' · '+validationHealth(state);
  if (state.status === 'loading') {
    await new Promise(resolve => setTimeout(resolve,1000));
    return watchOperation();
  }
  const result = state.result || {};
  const parts = [];
  if (result.cancelled) parts.push('Import interrompu · activités déjà enregistrées conservées');
  if (result.imported !== undefined) parts.push(result.imported+' activité(s) importée(s) ou mise(s) à jour');
  if (result.filtered) parts.push(result.filtered+' activité(s) hors profil ou classe de distance');
  if (result.existing !== undefined) parts.push(result.existing+' déjà présente(s)');
  if (result.deleted !== undefined) parts.push(result.deleted+' activité(s) effacée(s) localement');
  if (result.errors?.length) parts.push(result.errors.length+' échec(s) · '+result.errors.slice(0,3).join(' · '));
  if (parts.length) $('library-status').textContent += ' · '+parts.join(' · ');
  libraryBusy(false);
  await refreshLocal();
  const startup = await requestJSON('/api/startup');
  if (startup.status === 'ready') {
    startupReady = true;
    updatePredictionMode();
    await showReferences();
    if (selectedFile && $('prediction-mode').value === 'model') await analyze(selectedFile);
  } else {
    $('startup-panel').hidden = false;
    followStartup();
  }
}
$('refresh-references').addEventListener('click',() => libraryAction('/api/references/refresh',{}));
$('upload-reference').addEventListener('click',() => $('reference-file').click());
$('reference-file').addEventListener('change',async () => {
  const file = $('reference-file').files[0];
  $('reference-file').value = '';
  if (!file) return;
  if (file.size > 100*1024*1024) {
    $('library-status').textContent = 'Source de référence limitée à 100 Mio.';
    return;
  }
  try {
    await libraryAction('/api/local/upload',{name:file.name.replace(/\.gpx$/i,''),gpx:await readGpx(file)});
  } catch (error) { $('library-status').textContent = error.message; }
});
for (const id of ['import-kind','import-profile','import-distance-class','import-min-km','import-max-km','import-min-date','import-max-date']) {
  $(id).addEventListener('change',renderLocalActivities);
}
$('garmin-connect').addEventListener('click',async () => {
  const email = $('garmin-email').value.trim();
  const password = $('garmin-password').value;
  $('garmin-password').value = '';
  $('garmin-status').textContent = $('garmin-overview').textContent = 'Connexion Garmin en cours…';
  $('garmin-connect').disabled = true;
  try { renderGarmin(await postJSON('/api/garmin/connect',{email,password})); }
  catch (error) { $('garmin-status').textContent = $('garmin-overview').textContent = error.message; $('garmin-connect').disabled = false; }
});
$('garmin-mfa-submit').addEventListener('click',async () => {
  const code = $('garmin-mfa').value;
  $('garmin-mfa').value = '';
  try { renderGarmin(await postJSON('/api/garmin/mfa',{code})); }
  catch (error) { $('garmin-status').textContent = error.message; }
});
$('garmin-disconnect').addEventListener('click',async () => {
  try { renderGarmin(await postJSON('/api/garmin/disconnect',{})); }
  catch (error) { $('garmin-status').textContent = error.message; }
});
$('garmin-import').addEventListener('click',() => libraryAction('/api/garmin/import',
  {filters:importFilters(),useRunning:$('import-use-running').checked}));
$('delete-matching').addEventListener('click',() => {
  const count = filteredActivities().length;
  if (count && window.confirm('Effacer définitivement les '+count+' imports locaux correspondant aux critères ?')) {
    libraryAction('/api/local/delete',{scope:'matching',filters:importFilters()});
  }
});
$('delete-all').addEventListener('click',() => {
  if (localActivities.length && window.confirm('Effacer définitivement tous les imports locaux ('+localActivities.length+') ?')) {
    libraryAction('/api/local/delete',{scope:'all'});
  }
});
// Navigation sans reconstruction du DOM : la carte conserve son état.
let currentScreen = "analysis";
function showScreen(name) {
  currentScreen = name;
  if (name !== "analysis") pausePlayback();
  $('screen-analysis').hidden = name !== 'analysis';
  document.querySelectorAll('.screen-references').forEach(node => { node.hidden = name !== 'references'; });
  $('screen-simulations').hidden = name !== 'simulations';
  $('screen-map').hidden = name !== 'map';
  $('screen-conversion').hidden = name !== 'conversion';
  $('screen-backups').hidden = name !== 'backups';
  if (typeof pauseSimulation === 'function') pauseSimulation();
  for (const screen of ['analysis','references','map','simulations','conversion','backups']) {
    $('tab-'+screen).setAttribute('aria-current',screen === name ? 'page' : 'false');
  }
  if (name === 'analysis') refreshMapSize();
  if (name === 'conversion' && conversionView) conversionView.resize();
  if (name === 'simulations') renderRuns();
  if (name === 'map') loadReferenceMap();
  if (name === 'references' && !startupReady) loadReferenceMap();
}
for (const name of ['analysis','references','map','simulations','conversion','backups']) {
  $('tab-'+name).addEventListener('click',() => showScreen(name));
}
$('reference-sort').addEventListener('change',showReferences);
async function refreshSelection() {
  try {
    const data = await requestJSON('/api/reference-selection');
    $('reference-selection').replaceChildren();
    for (const source of data.references) {
      const row = $('reference-selection').insertRow();
      row.insertCell().textContent = source.name;
      const checkbox = element('input','');
      checkbox.type = 'checkbox'; checkbox.checked = source.enabled;
      checkbox.setAttribute('aria-label','Inclure '+source.name+' dans le modèle');
      checkbox.disabled = operationBusy;
      checkbox.addEventListener('change',() => libraryAction('/api/reference-selection',
        {key:source.key,enabled:checkbox.checked}));
      row.insertCell().append(checkbox);
    }
  } catch (error) { $('reference-status').textContent = error.message; }
}

// Export GPX 1.1 : coordonnées originales, coupures, repères et horaires UTC.
const xmlEscape = value => String(value).replace(/[<>&"']/g,c =>
  ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[c]));
function buildGpx(data, name, departure) {
  const point = (tag,lat,lon,alt,seconds,label) => '<'+tag+' lat="'+lat+'" lon="'+lon+'"><ele>'+alt+'</ele>'+
    (departure ? '<time>'+new Date(new Date(departure).getTime()+seconds*1000).toISOString()+'</time>' : '')+
    (label ? '<name>'+xmlEscape(label)+'</name><desc>'+xmlEscape(label)+'</desc>' : '')+'</'+tag+'>';
  if (!data.exportPoints?.length) throw Error('Recalculez cette analyse pour préparer son export GPX.');
  return '<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="BZHAventure UltraTrail" xmlns="http://www.topografix.com/GPX/1/1">'+
    '<metadata><name>'+xmlEscape(name)+'</name><desc>'+ (data.model.scope==='recorded' ? 'Parcours et horaires enregistrés dans le GPX source.' : 'Parcours et horaires prévisionnels, sans mesure réelle.')+'</desc></metadata>'+
    data.marks.map(([d,t,lat,lon,alt,label])=>point('wpt',lat,lon,alt,t,label)).join('')+
    '<trk><name>'+xmlEscape(name)+'</name>'+data.exportPoints.map(segment=>'<trkseg>'+segment.map(
      ([lat,lon,alt,t])=>point('trkpt',lat,lon,alt,t)).join('')+'</trkseg>').join('')+'</trk></gpx>';
}
function downloadGpx(data, name, departure) {
  try {
    const url = URL.createObjectURL(new Blob([buildGpx(data,name,departure)],{type:'application/gpx+xml'}));
    const link = element('a',''); link.href = url;
    link.download = name.replace(/\.gpx$/i,'').replace(/[<>:"/\\|?*]/g,'_')+(data.model.scope==='recorded' ? '-enregistre.gpx' : '-prediction.gpx');
    document.body.append(link); link.click(); link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  } catch (error) { $('simulation-status').textContent = $('status').textContent = error.message; }
}
$('export-gpx').addEventListener('click',() => {
  try { if (routeData) {
    const departure=departureDate();
    if ($('departure').value && !departure) throw Error('Corrigez la date et l’heure de départ.');
    downloadGpx(routeData,selectedFile.name,departure);
  } }
  catch (error) { $('status').textContent = error.message; }
});

// Identifiant compact de comparaison, sans dupliquer les fichiers dans localStorage.
// Cette empreinte sert à l'interface et n'est pas un contrôle de sécurité.
function routeFingerprint(text) {
  let a=2166136261, b=5381;
  for (let i=0;i<text.length;i++) {
    a=Math.imul(a^text.charCodeAt(i),16777619);
    b=Math.imul(b,33)^text.charCodeAt(i);
  }
  return text.length+':'+(a>>>0).toString(16)+':'+(b>>>0).toString(16);
}
let activeRouteKey = '', runs = [];
try {
  const saved = JSON.parse(localStorage.getItem('bzhaventure-runs-v1') || '[]');
  if (Array.isArray(saved)) runs = saved.filter(r=>r.data?.marks?.length && Number.isFinite(r.data.duration)).slice(0,20);
} catch (_) { /* Le navigateur peut refuser le stockage local. */ }
// IndexedDB accepte les chronologies volumineuses que localStorage peut refuser.
let runsRevision=0;
const runDatabase = typeof indexedDB==='undefined' ? Promise.resolve(null) : new Promise(resolve=>{
  const request=indexedDB.open('bzhaventure-simulations',1);
  request.onupgradeneeded=()=>{request.result.createObjectStore('runs');};
  request.onsuccess=()=>resolve(request.result);request.onerror=()=>resolve(null);request.onblocked=()=>resolve(null);
});
function persistRuns() {
  const revision=++runsRevision, serialized=JSON.stringify(runs);
  if(typeof scheduleStateSave==='function')scheduleStateSave();
  if(typeof indexedDB==='undefined') {
    try {localStorage.setItem('bzhaventure-runs-v1',serialized);return true;}
    catch(_){$('simulation-status').textContent='Stockage navigateur indisponible ou plein : scénarios conservés pour cette session uniquement.';return false;}
  }
  runDatabase.then(db=>{
    if(!db)throw Error('Stockage indisponible');
    const transaction=db.transaction('runs','readwrite');transaction.objectStore('runs').put(serialized,'current');
    transaction.oncomplete=()=>{try{localStorage.removeItem?.('bzhaventure-runs-v1');}catch(_){}};
    transaction.onerror=transaction.onabort=()=>{if(revision===runsRevision)$('simulation-status').textContent='Stockage navigateur indisponible ou plein : scénarios conservés pour cette session uniquement.';};
  }).catch(()=>{
    try{localStorage.setItem('bzhaventure-runs-v1',serialized);}
    catch(_){if(revision===runsRevision)$('simulation-status').textContent='Stockage navigateur indisponible ou plein : scénarios conservés pour cette session uniquement.';}
  });
  return true;
}
$('save-run').addEventListener('click',() => {
  if (!routeData) { $('simulation-status').textContent = 'Analysez d’abord un parcours dans le premier écran.'; return; }
  if (runs.length >= 20) { $('simulation-status').textContent = 'Maximum 20 scénarios. Retirez un run avant d’en ajouter un.'; return; }
  let departure;
  try { departure = departureDate(); } catch (error) { $('simulation-status').textContent = error.message; return; }
  if ($('departure').value && !departure) { $('simulation-status').textContent='Corrigez la date et l’heure de départ.'; return; }
  runs.push({name:$('run-name').value.trim() || 'Run '+(runs.length+1),file:selectedFile.name,
    departure:departure ? departure.toISOString() : null,routeKey:activeRouteKey,
    data:JSON.parse(JSON.stringify(routeData))});
  $('simulation-status').textContent = 'Scénario ajouté à la comparaison.';
  persistRuns(); renderRuns();
});
function renderRuns() {
  $('simulation-runs').replaceChildren(); $('simulation-chart').replaceChildren();
  const baseline = runs[0];
  for (const [index,run] of runs.entries()) {
    const row = $('simulation-runs').insertRow(), data = run.data;
    for (const value of [run.name+' · '+run.file,
      (run.sourceDate || run.data.recordedStart || run.departure) ? new Date(run.sourceDate || run.data.recordedStart || run.departure).toLocaleDateString('fr-FR') : '—',
      km(data.distance),meters(data.ascent || 0),meters(data.descent || 0),time(data.duration),
      run.departure ? new Date(run.departure).toLocaleString('fr-FR') : '—',
      run.departure ? passageDate(new Date(run.departure),data.duration) : '—',
      profileLabel(data.classification || {}),data.classification?.distanceLabel || '—']) row.insertCell().textContent = value;
    if(data.strategy){const note=element('small',data.strategy.label);note.className='run-strategy-note';row.cells[0].append(note);}
    const actions = row.insertCell();
    const exportButton = element('button','GPX'); exportButton.type='button'; exportButton.className='button';
    exportButton.addEventListener('click',()=>downloadGpx(data,run.name,run.departure));
    const remove = element('button','Retirer'); remove.type='button'; remove.className='button';
    remove.addEventListener('click',()=>{runs.splice(index,1);persistRuns();renderRuns();});
    actions.append(exportButton,remove);
    const bar = element('div',''); bar.className='run-bar';
    const label = element('span',run.name+' · '+time(data.duration));
    const fill = element('div',''); fill.style.width=(100*data.duration/Math.max(...runs.map(r=>r.data.duration)))+'%';
    bar.append(label,fill); $('simulation-chart').append(bar);
  }
  $('simulation-marks-head').replaceChildren(); $('simulation-marks').replaceChildren();
  if (typeof renderRunVisuals === 'function') renderRunVisuals();
  if (!baseline) return;
  const same = runs.filter(r=>r.routeKey===baseline.routeKey);
  const head = element('tr',''); head.append(element('th','Repère du premier run'));
  same.forEach(r=>head.append(element('th',r.name))); $('simulation-marks-head').append(head);
  for (const mark of baseline.data.marks) {
    const row = $('simulation-marks').insertRow(); row.insertCell().textContent=mark[5]+' · '+km(mark[0]);
    for (const run of same) {
      const match = run.data.marks.find(m=>Math.abs(m[0]-mark[0])<0.001);
      row.insertCell().textContent = match ? time(match[1])+(run.departure ? ' · '+passageDate(new Date(run.departure),match[1]) : '') : 'Repère absent';
    }
  }
}
refreshLocal();

// Informations sur l'environnement réellement utilisé par le serveur.
requestJSON('/api/runtime').then(info=>{
  $('runtime-info').textContent='Python '+info.python+' · Application '+info.version;
}).catch(()=>{ $('runtime-info').textContent='Version Python indisponible'; });

let simulationFiles=[];
$('select-simulation-gpx').addEventListener('click',()=>$('simulation-files').click());
$('simulation-files').addEventListener('change',()=>{
  simulationFiles=Array.from($('simulation-files').files);
  $('simulation-files-info').textContent=simulationFiles.length ? simulationFiles.map(f=>f.name).join(' · ') : 'Aucun fichier sélectionné';
  $('simulation-files').value='';
});
$('simulation-mode').addEventListener('change',()=>{
  const mode=$('simulation-mode').value;
  $('simulation-model-fields').hidden=mode!=='model';
  $('simulation-departure-fields').hidden=mode==='recorded';
  $('recorded-help').hidden=mode!=='recorded';
  $('simulation-total-fields').hidden=mode!=='total';
  $('simulation-pace-fields').hidden=mode!=='pace';
});
$('simulate-files').addEventListener('click',async()=>{
  if (!simulationFiles.length) { $('simulation-status').textContent='Importez au moins un fichier GPX à simuler.'; return; }
  if (runs.length+simulationFiles.length>20) { $('simulation-status').textContent='La comparaison est limitée à 20 runs. Retirez des scénarios ou sélectionnez moins de fichiers.'; return; }
  const mode=$('simulation-mode').value, options={mode,model:$('simulation-model').value || 'auto',
    interval:Number($('simulation-spacing').value),waypoints:[],retainSource:true};
  let departure;
  try {
    if (!Number.isInteger(options.interval) || options.interval<1 || options.interval>50) throw Error('Espacement des repères : de 1 à 50 km.');
    if (mode==='total') options.totalSeconds=parseClock($('simulation-total').value,true);
    if (mode==='pace') options.paceSeconds=parseClock($('simulation-pace').value);
    departure=mode==='recorded' ? null : departureDate('simulation-departure');
    if (mode!=='recorded' && $('simulation-departure').value && !departure) throw Error('Corrigez le départ des simulations.');
  } catch(error) { $('simulation-status').textContent=error.message; return; }
  $('simulate-files').disabled=true; $('select-simulation-gpx').disabled=true; $('save-run').disabled=true;
  const files=[...simulationFiles], prefix=$('run-name').value.trim(), errors=[];
  let completed=0;
  try {
    for (const file of files) {
      $('simulation-status').textContent=(mode==='recorded' ? 'Lecture GPX ' : 'Simulation ')+(completed+errors.length+1)+' / '+files.length+' · '+file.name;
      try {
        const gpx=await readGpx(file);
        const data=await postJSON('/api/prediction',{...options,gpx});
        runs.push({name:(prefix ? prefix+' · ' : '')+file.name,file:file.name,sourceDate:gpxImportMetadata.get(file)?.recordedStart || null,
          departure:mode==='recorded' ? data.recordedStart : departure ? departure.toISOString() : null,routeKey:routeFingerprint(gpx),data});
        completed++;
        persistRuns(); renderRuns();
      } catch(error) { errors.push(file.name+' : '+error.message); }
    }
    $('simulation-status').textContent=completed+(mode==='recorded' ? ' course(s) enregistrée(s) ajoutée(s). ' : ' simulation(s) ajoutée(s). ')+errors.join(' · ');
    if (completed) persistRuns();
  } finally {
    $('simulate-files').disabled=false; $('select-simulation-gpx').disabled=false; $('save-run').disabled=false;
  }
});

function validationHealth(state) {
  if (state.status !== 'loading') return '';
  const age=Math.round(state.lastProgressAgo || 0);
  return state.slow ? 'Traitement long : '+age+' s sans nouvelle étape. La validation sera arrêtée après '+
    (state.validationTimeout || 180)+' s sans progression.' : 'Surveillance active · dernière progression il y a '+age+' s.';
}
$('retry-validation').addEventListener('click',()=>{
  $('retry-validation').hidden=true;
  libraryAction('/api/references/refresh',{});
  followStartup();
});
$('garmin-stop').addEventListener('click',async()=>{
  $('garmin-stop').disabled=true;
  try {
    const result=await postJSON('/api/garmin/stop',{});
    $('library-status').textContent=result.message;
  } catch(error) { $('library-status').textContent=error.message; }
});

const distanceColors=['#187e72','#65a15c','#d08b22','#5474bb','#ac5090'];
function drawReferenceHistogram(courses) {
  histogramCourses=courses; histogramBars=[];
  const profiles=RELIEF_PROFILES, distances=DISTANCE_IDS;
  const labels=['▱ Plat / Vallonné','▲ Intermédiaire / Montagne','⋀⋀ Dents de scie','∿ Mixte'];
  const distanceLabels=['< 20 km','20–50 km','50–100 km','100–160 km','≥ 160 km'];
  const counts=profiles.map(p=>distances.map(d=>courses.filter(c=>c.classification.profile===p && c.classification.distanceClass===d).length));
  const maximum=Math.max(1,...counts.flat());
  const svg=svgElement('svg',{viewBox:'0 0 1000 340',role:'group','aria-label':'Sélectionner un groupe de références par profil et distance'});
  svg.append(svgElement('line',{x1:45,y1:275,x2:980,y2:275,stroke:'#8aada4'}));
  counts.forEach((group,i)=>{
    const label=svgElement('text',{x:150+i*240,y:305,'text-anchor':'middle','font-size':11}); label.textContent=labels[i]; svg.append(label);
    group.forEach((count,j)=>{
      const x=70+i*240+j*32,height=count/maximum*225;
      const bar=svgElement('g',{role:'button',tabindex:'0','aria-pressed':'false',
        'aria-label':labels[i]+' · '+distanceLabels[j]+' : '+count+' course(s)',
        'data-profile':profiles[i],'data-distance':distances[j]});
      const activate=()=>selectHistogramGroup(profiles[i],distances[j]);
      bar.addEventListener('click',activate);
      bar.addEventListener('keydown',event=>{if(event.key==='Enter' || event.key===' '){event.preventDefault();activate();}});
      const rect=svgElement('rect',{x,y:275-Math.max(2,height),width:24,height:Math.max(2,height),fill:distanceColors[j]});
      const title=svgElement('title');title.textContent=labels[i]+' · '+distanceLabels[j]+' : '+count+' référence(s)';rect.append(title);
      const value=svgElement('text',{x:x+12,y:265-height,'text-anchor':'middle','font-size':14});value.textContent=count;
      bar.append(rect,value); svg.append(bar);
      histogramBars.push({bar,rect,profile:profiles[i],distance:distances[j]});
    });
  });
  $('reference-histogram').replaceChildren(svg);
  $('histogram-legend').replaceChildren();
  distanceLabels.forEach((label,i)=>{
    const item=element('span','■ '+label);item.style.color=distanceColors[i];$('histogram-legend').append(item);
  });
  applyHistogramSelection();
}

function selectHistogramGroup(profile,distance) {
  const same=histogramFilter?.profile===profile && histogramFilter?.distance===distance;
  histogramFilter=same || profile===null ? null : {profile,distance};
  applyHistogramSelection();
}
function applyHistogramSelection() {
  const matches=course=>!histogramFilter || (course.classification.profile===histogramFilter.profile &&
    course.classification.distanceClass===histogramFilter.distance);
  for (const entry of referenceRows) {
    const visible=matches(entry.course);
    entry.row.hidden=!visible; entry.branch.hidden=!visible || !entry.expanded;
  }
  for (const entry of referenceHeaders) entry.row.hidden=!!histogramFilter &&
    entry.group!==histogramFilter.profile+':'+histogramFilter.distance;
  for (const entry of histogramBars) {
    const selected=histogramFilter?.profile===entry.profile && histogramFilter?.distance===entry.distance;
    entry.bar.setAttribute('aria-pressed',String(selected));
    entry.rect.setAttribute('stroke',selected ? '#143e35' : 'none');
    entry.rect.setAttribute('stroke-width',selected ? '3' : '0');
  }
  $('clear-histogram-filter').hidden=!histogramFilter;
  $('histogram-selection-panel').hidden=!histogramFilter;
  $('histogram-course-list').replaceChildren();
  if (!histogramFilter) { $('histogram-filter-summary').textContent='Toutes les courses sont affichées.'; return; }
  const courses=histogramCourses.filter(matches);
  const labels={'flat':'▱ Plat / Vallonné','mountain':'▲ Intermédiaire / Montagne','sawtooth':'⋀⋀ Dents de scie','mixed':'∿ Mixte'};
  const distances=['< 20 km','20–50 km','50–100 km','100–160 km','≥ 160 km'];
  $('histogram-filter-summary').textContent=labels[histogramFilter.profile]+' · '+
    distances[DISTANCE_IDS.indexOf(histogramFilter.distance)]+' · '+courses.length+' course(s) incluse(s).'+
    (courses.length ? ' Le classement ci-dessous est filtré sur ce groupe.' : ' Aucune course dans ce groupe.');
  for (const course of courses) {
    const distance=course.distance ?? course.classification.distance;
    const row=$('histogram-course-list').insertRow();
    for (const value of [course.name,km(distance),meters(course.ascent ?? course.classification.ascent),
        Number.isFinite(course.actual) ? time(course.actual) : 'Après validation']) row.insertCell().textContent=value;
    const entry=referenceRows.find(e=>e.course===course || (e.course.name===course.name &&
      Math.abs(e.course.distance-distance)<.01 && (course.actual==null || course.actual===e.course.actual)));
    const button=element('button',entry ? 'Ouvrir les détails' : 'Détails après validation');
    button.type='button';button.className='button';button.disabled=!entry;
    button.addEventListener('click',()=>entry?.expand());row.insertCell().append(button);
  }
}
$('clear-histogram-filter').addEventListener('click',()=>selectHistogramGroup(null,null));

// Carte distincte : aucune mutation de la trace analysée ou de sa lecture.
let referenceMap, referenceLayers, referenceMapData, mapRequest=0;
const referenceColors=['#00796b','#b24b40','#4267ae','#9b4a98','#aa721c','#3b7b3e','#6845b0','#a34868'];
async function loadReferenceMap() {
  const version=++mapRequest;
  $('reference-map-status').textContent='Chargement des traces de référence…';
  try {
    const data=await requestJSON('/api/reference-map');
    if (version!==mapRequest) return;
    referenceMapData=data;
    const seen=new Set();
    const mappedCourses=data.courses.filter(course=>{
      const id=course.contentId || course.key;
      if (!course.enabled || seen.has(id)) return false;
      seen.add(id); return true;
    });
    drawReferenceHistogram(startupReady && referenceCourses.length ? referenceCourses : mappedCourses);
    renderReferenceMap();
  } catch(error) { if (version===mapRequest) $('reference-map-status').textContent=error.message; }
}
let selectedReferenceKey=null;
function showReferenceCourseInfo(course) {
  $('reference-course-details').hidden=!course;
  if(!course){$('reference-course-info').replaceChildren();return;}
  const d=course.summary || course.classification,start=course.recordedStart ? new Date(course.recordedStart) : null;
  metrics($('reference-course-info'),[['Course',course.name],['Profil',profileLabel(course.classification)],
    ['Classe de distance',course.classification.distanceLabel || '—'],['Distance',km(d.distance)],
    ['D+',Number.isFinite(d.ascent) ? meters(d.ascent) : '—'],['D−',Number.isFinite(d.descent) ? meters(d.descent) : '—'],
    ['Durée',Number.isFinite(course.duration) ? time(course.duration) : '—'],
    ['Départ',start ? passageDate(start,0) : '—'],['Arrivée',start && Number.isFinite(course.duration) ? passageDate(start,course.duration) : '—'],
    ['Pauses',Number.isFinite(course.pauses?.duration) ? time(course.pauses.duration) : '—'],['Modèle',course.enabled ? 'Retenue' : 'Exclue']]);
}
function selectReferenceCourse(key) {
  selectedReferenceKey=key || null;
  const course=referenceMapData?.courses.find(c=>c.key===selectedReferenceKey);
  $('reference-course-select').value=selectedReferenceKey || '';showReferenceCourseInfo(course);
  if(window.L && referenceMap) {
    const courses=referenceMapData.courses.filter(c=>!$('map-active-only').checked || c.enabled);
    const points=(course ? [course] : courses).flatMap(c=>c.trace.flat());
    referenceMap.invalidateSize();
    if(points.length)referenceMap.fitBounds(L.latLngBounds(points),{padding:[25,25],maxZoom:14});
  }else renderReferenceMap(selectedReferenceKey);
}
$('reference-course-select').addEventListener('change',()=>selectReferenceCourse($('reference-course-select').value));
function renderReferenceMap(focusKey=selectedReferenceKey) {
  if (!referenceMapData) return;
  const courses=referenceMapData.courses.filter(c=>!$('map-active-only').checked || c.enabled);
  $('reference-map-status').textContent=courses.length+' course(s) affichée(s). '+
    (referenceMapData.skipped.length ? 'Traces non exploitables : '+referenceMapData.skipped.join(' · ') : '');
  const focus=courses.find(c=>c.key===focusKey), visible=focus ? [focus] : courses;
  selectedReferenceKey=focus?.key || null;
  $('reference-course-select').replaceChildren(element('option','Toutes les courses'));
  $('reference-course-select').options[0].value='';
  for(const course of courses){const option=element('option',course.name);option.value=course.key;$('reference-course-select').append(option);}
  $('reference-course-select').value=selectedReferenceKey || '';showReferenceCourseInfo(focus);
  const allPoints=visible.flatMap(c=>c.trace.flat());
  $('reference-map-list').replaceChildren();
  courses.forEach((course,index)=>{
    const row=$('reference-map-list').insertRow();
    const name=row.insertCell(); name.textContent='■ '+course.name; name.style.color=referenceColors[index%referenceColors.length];
    row.insertCell().textContent=profileLabel(course.classification);
    row.insertCell().textContent=km(course.classification.distance);
    row.insertCell().textContent=course.enabled ? 'Retenue' : 'Exclue';
    const button=element('button','Centrer');button.type='button';button.className='button';
    button.addEventListener('click',event=>{event?.stopPropagation?.();selectReferenceCourse(course.key);});row.insertCell().append(button);
    row.tabIndex=0;row.setAttribute('aria-label','Sélectionner '+course.name);
    row.addEventListener('click',()=>selectReferenceCourse(course.key));
    row.addEventListener('keydown',event=>{if(event.key==='Enter' || event.key===' '){event.preventDefault();selectReferenceCourse(course.key);}});
  });
  if (window.L) {
    if (!referenceMap) {
      referenceMap=L.map('reference-map',{preferCanvas:true}).setView([46.6,2.5],5);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',maxZoom:19}).addTo(referenceMap);
      referenceLayers=L.featureGroup().addTo(referenceMap);
    }
    referenceLayers.clearLayers();
    courses.forEach((course,index)=>{
      const color=referenceColors[index%referenceColors.length];
      const label=()=>element('span',course.name+' · '+km(course.classification.distance)+(course.enabled ? ' · Retenue' : ' · Exclue'));
      course.trace.forEach(segment=>{
        L.polyline(segment,{color,weight:4,opacity:course.enabled ? .9 : .5,dashArray:course.enabled ? null : '6 6'}).bindPopup(label()).on('click',()=>selectReferenceCourse(course.key)).addTo(referenceLayers);
      });
      if (course.trace[0]?.[0]) L.circleMarker(course.trace[0][0],{color,radius:5}).bindPopup(label()).on('click',()=>selectReferenceCourse(course.key)).addTo(referenceLayers);
    });
    referenceMap.invalidateSize();
    if (allPoints.length) referenceMap.fitBounds(L.latLngBounds(allPoints),{padding:[25,25],maxZoom:14});
    return;
  }
  // Secours géographique si la bibliothèque de carte ne se charge pas.
  if (!allPoints.length) { $('reference-map').replaceChildren(element('p','Aucune référence à afficher.'));return; }
  const bounds=allPoints.reduce((b,p)=>[Math.min(b[0],p[0]),Math.max(b[1],p[0]),Math.min(b[2],p[1]),Math.max(b[3],p[1])],[Infinity,-Infinity,Infinity,-Infinity]);
  const [minLat,maxLat,minLon,maxLon]=bounds;
  const scale=Math.cos((minLat+maxLat)*Math.PI/360);
  const factor=Math.min(850/Math.max(.00001,(maxLon-minLon)*scale),430/Math.max(.00001,maxLat-minLat));
  const project=p=>[25+(p[1]-minLon)*scale*factor,455-(p[0]-minLat)*factor];
  const svg=svgElement('svg',{viewBox:'0 0 900 480',role:'img','aria-label':'Traces de toutes les références, sans fond de carte'});
  courses.forEach((course,index)=>course.trace.forEach(segment=>{
    const line=svgElement('polyline',{points:segment.map(p=>project(p).join(',')).join(' '),fill:'none',stroke:referenceColors[index%referenceColors.length],'stroke-width':2,opacity:course.enabled ? 1 : .45});
    line.setAttribute('tabindex','0');line.setAttribute('role','button');line.setAttribute('aria-label','Sélectionner '+course.name);
    line.addEventListener('click',()=>selectReferenceCourse(course.key));
    line.addEventListener('keydown',event=>{if(event.key==='Enter' || event.key===' '){event.preventDefault();selectReferenceCourse(course.key);}});
    const title=svgElement('title');title.textContent=course.name;line.append(title);svg.append(line);
  }));
  $('reference-map').replaceChildren(svg);
}
$('refresh-reference-map').addEventListener('click',loadReferenceMap);
$('map-active-only').addEventListener('change',()=>renderReferenceMap());

// Plein écran indépendant de la carte de prédiction : conserver le cadrage
// utilisateur, les filtres et l'actualisation dans le panneau agrandi.
function updateReferenceFullscreen() {
  const panel=$('reference-map-panel');
  const expanded=document.fullscreenElement===panel || panel.classList.contains('expanded');
  $('reference-map-fullscreen').textContent=expanded ? '⛶ Quitter le plein écran' : '⛶ Carte en plein écran';
  $('reference-map-fullscreen').setAttribute('aria-pressed',String(expanded));
  document.body.classList[expanded ? 'add' : 'remove']('reference-map-fullscreen');
  requestAnimationFrame(()=>{ if(referenceMap) referenceMap.invalidateSize({animate:false}); });
}
$('reference-map-fullscreen').addEventListener('click',async()=>{
  const panel=$('reference-map-panel');
  try {
    if(document.fullscreenElement===panel) await document.exitFullscreen();
    else if(panel.classList.contains('expanded')) panel.classList.remove('expanded');
    else {
      try { await panel.requestFullscreen(); }
      catch { panel.classList.add('expanded'); }
    }
  } catch(error) { $('reference-map-status').textContent='Changement de plein écran impossible : '+error.message; }
  updateReferenceFullscreen();
});
document.addEventListener('fullscreenchange',updateReferenceFullscreen);
document.addEventListener('keydown',event=>{
  if(event.key==='Escape' && $('reference-map-panel').classList.contains('expanded')) {
    $('reference-map-panel').classList.remove('expanded'); updateReferenceFullscreen();
    $('reference-map-fullscreen').focus?.();
  }
});
/* Cartes indépendantes et horloge commune de comparaison. Les dates originales
   ne sont jamais modifiées : seul l'instant de lecture est aligné. */
let runViews = [], simulationTime = 0, simulationAnimation = null, simulationLastFrame = null;
let conversionView = null;
function geoDistance(a,b) {
  const rad = value=>value*Math.PI/180, dlat=rad(b[0]-a[0]), dlon=rad(b[1]-a[1]);
  const h=Math.sin(dlat/2)**2+Math.cos(rad(a[0]))*Math.cos(rad(b[0]))*Math.sin(dlon/2)**2;
  return 12742000*Math.asin(Math.sqrt(Math.min(1,h)));
}
function viewSections(data) {
  if (data.sections?.length) return data.sections;
  let offset=0;
  const sections=[];
  for (const segment of data.exportPoints || []) {
    for (let i=1;i<segment.length;i++) {
      const start=segment[i-1],end=segment[i],length=geoDistance(start,end),duration=end[3]-start[3];
      sections.push({start,end,distance:offset,endDistance:offset+length,time:start[3],endTime:end[3],
        grade:length ? (end[2]-start[2])/length*100 : 0,speed:duration>0 ? length/duration*3.6 : 0});
      offset+=length;
    }
  }
  return sections;
}
function positionInSections(sections,seconds) {
  if (!sections.length) return null;
  let low=0,high=sections.length-1;
  while(low<high) { const mid=(low+high)>>1; if(sections[mid].endTime<seconds) low=mid+1; else high=mid; }
  if(seconds<sections[low].time && low>0)low--;
  const s=sections[low], f=Math.max(0,Math.min(1,(seconds-s.time)/Math.max(1e-9,s.endTime-s.time)));
  return {point:s.start.map((v,i)=>v+(s.end[i]-v)*f),distance:s.distance+(s.endDistance-s.distance)*f,speed:s.speed};
}
// Regrouper les traits par couleur limite le nombre de couches et de nœuds SVG.
function createCourseView(container,data,colorMode='grade') {
  const sections=viewSections(data), wrapper=element('div',''); wrapper.className='course-view';
  const mapNode=element('div',''); mapNode.className='comparison-map';
  const figure=element('figure',''); figure.className='comparison-profile';
  wrapper.append(mapNode,figure); container.append(wrapper);
  const value=s=>colorMode==='elevation' ? (s.start[2]+s.end[2])/2 : s[colorMode];
  let min=Infinity,max=-Infinity,minEle=Infinity,maxEle=-Infinity;
  let west=Infinity,east=-Infinity,south=Infinity,north=-Infinity;
  for(const s of sections) {
    min=Math.min(min,value(s));max=Math.max(max,value(s));
    for(const p of [s.start,s.end]) {minEle=Math.min(minEle,p[2]);maxEle=Math.max(maxEle,p[2]);
      west=Math.min(west,p[1]);east=Math.max(east,p[1]);south=Math.min(south,p[0]);north=Math.max(north,p[0]);}
  }
  if(!sections.length) {container.append(element('p','Géométrie indisponible pour cet ancien scénario : réimportez le GPX.'));return {update(){},destroy(){}};}
  const color=i=>'hsl('+(235-230*i/47)+',80%,43%)';
  const bucket=s=>Math.max(0,Math.min(47,Math.round((value(s)-min)/Math.max(1e-9,max-min)*47)));
  const total=sections[sections.length-1].endDistance || data.distance || 1;
  const profileProject=(d,e)=>[35+700*d/total,180-150*(e-minEle)/Math.max(1,maxEle-minEle)];
  const svg=svgElement('svg',{viewBox:'0 0 760 225',role:'img','aria-label':'Profil altimétrique coloré et position de lecture'});
  const paths=Array.from({length:48},()=>[]),lines=Array.from({length:48},()=>[]);
  for(const s of sections) {
    const a=profileProject(s.distance,s.start[2]),b=profileProject(s.endDistance,s.end[2]),i=bucket(s);
    paths[i].push('M'+a.join(',')+'L'+b.join(','));lines[i].push([s.start.slice(0,2),s.end.slice(0,2)]);
  }
  paths.forEach((path,i)=>{if(path.length) svg.append(svgElement('path',{d:path.join(''),fill:'none',stroke:color(i),'stroke-width':2}));});
  const guide=svgElement('line',{x1:35,x2:35,y1:20,y2:185,stroke:'#182d32','stroke-dasharray':'4 3'});
  const dot=svgElement('circle',{r:5,fill:'#182d32',stroke:'#fff','stroke-width':2});svg.append(guide,dot);
  const axis=svgElement('text',{x:35,y:210});axis.textContent='0 km → '+km(total)+' · '+meters(minEle)+' à '+meters(maxEle);svg.append(axis);
  figure.append(element('figcaption','Profil altimétrique'),svg,
    element('small',({grade:'Pente',elevation:'Altitude',speed:'Vitesse'}[colorMode])+ ' · '+number(min,1)+' → '+number(max,1)+({grade:' %',elevation:' m',speed:' km/h'}[colorMode])+' · bleu → rouge'));
  let localMap=null,marker=null,mapDot=null;
  const scaleLon=Math.cos((south+north)/2*Math.PI/180);
  const scale=Math.min(680/Math.max(1e-9,(east-west)*scaleLon),270/Math.max(1e-9,north-south));
  const project=p=>[40+(p[1]-west)*scaleLon*scale,300-(p[0]-south)*scale];
  if(typeof L!=='undefined') {
    localMap=L.map(mapNode);const renderer=L.svg({padding:.3});
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(localMap);
    lines.forEach((line,i)=>{if(line.length)L.polyline(line,{color:color(i),weight:4,renderer,interactive:false}).addTo(localMap);});
    marker=L.circleMarker(sections[0].start.slice(0,2),{radius:7,color:'#fff',weight:3,fillColor:'#172f32',fillOpacity:1,renderer}).addTo(localMap);
    localMap.fitBounds([[south,west],[north,east]],{padding:[20,20],maxZoom:16});
  } else {
    const mapSvg=svgElement('svg',{viewBox:'0 0 760 330',role:'img','aria-label':'Trace GPS sans fond cartographique'});
    lines.forEach((line,i)=>{if(line.length)mapSvg.append(svgElement('path',{d:line.map(([a,b])=>'M'+project(a).join(',')+'L'+project(b).join(',')).join(''),fill:'none',stroke:color(i),'stroke-width':3}));});
    mapDot=svgElement('circle',{r:6,fill:'#172f32',stroke:'#fff','stroke-width':2});mapSvg.append(mapDot);mapNode.append(mapSvg,element('small','Trace GPS · fond cartographique indisponible'));
  }
  return {
    update(seconds) {
      const position=positionInSections(sections,seconds);if(!position)return null;
      const [x,y]=profileProject(position.distance,position.point[2]);
      guide.setAttribute('x1',x);guide.setAttribute('x2',x);dot.setAttribute('cx',x);dot.setAttribute('cy',y);
      if(marker)marker.setLatLng(position.point.slice(0,2));
      if(mapDot){const [mx,my]=project(position.point);mapDot.setAttribute('cx',mx);mapDot.setAttribute('cy',my);}
      return position;
    },
    destroy(){if(localMap)localMap.remove();}, resize(){if(localMap)localMap.invalidateSize();}
  };
}
function pauseSimulation() {
  if(simulationAnimation!==null)cancelAnimationFrame(simulationAnimation);
  simulationAnimation=null;simulationLastFrame=null;$('simulation-play').textContent='▶ Lire les traces ensemble';
}
function simulationDuration(){return Math.max(0,...runs.map(r=>r.data.duration));}
function updateSimulation(seconds) {
  const duration=simulationDuration();simulationTime=Math.max(0,Math.min(duration,seconds));
  $('simulation-progress').value=duration ? simulationTime/duration*1000 : 0;
  const anchor=departureDate('simulation-anchor');
  $('simulation-clock').textContent=time(simulationTime)+' / '+time(duration)+(anchor ? ' · '+passageDate(anchor,simulationTime) : ' · départs alignés à 0');
  runViews.forEach(({view,run,status})=>{
    const elapsed=Math.min(simulationTime,run.data.duration),p=view.update(elapsed);
    status.textContent=time(elapsed)+' · '+(p ? km(p.distance)+' · '+meters(p.point[2])+' · '+number(p.speed,1)+' km/h' : '')+
      (anchor ? ' · '+passageDate(anchor,elapsed) : '')+(simulationTime>=run.data.duration ? ' · Arrivé' : '');
  });
}
function renderRunVisuals() {
  pauseSimulation();runViews.forEach(v=>v.view.destroy());runViews=[];$('simulation-views').replaceChildren();
  if(!$('simulation-anchor').value && runs[0]?.departure) {
    const d=new Date(runs[0].departure); if(Number.isFinite(d.getTime())) {
      $('simulation-anchor').value=new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);
    }
  }
  runs.forEach(run=>{
    const card=element('article','');card.className='run-card';card.append(element('h3',run.name));
    if(run.data.strategy)card.append(element('small',run.data.strategy.label));
    $('simulation-views').append(card);
    const view=createCourseView(card,run.data,$('simulation-color').value || 'grade'),status=element('p','');
    status.setAttribute('aria-live','off');card.append(status);runViews.push({view,run,status});
  });
  $('simulation-play').disabled=!runs.length;updateSimulation(simulationTime);
}
function simulationFrame(timestamp) {
  if(simulationLastFrame!==null)updateSimulation(simulationTime+(timestamp-simulationLastFrame)/1000*Number($('simulation-speed').value || 600));
  simulationLastFrame=timestamp;
  if(simulationTime>=simulationDuration()){pauseSimulation();return;}
  simulationAnimation=requestAnimationFrame(simulationFrame);
}
$('simulation-play').addEventListener('click',()=>{
  if(simulationAnimation!==null){pauseSimulation();return;}if(!runs.length)return;
  if(simulationTime>=simulationDuration())updateSimulation(0);
  $('simulation-play').textContent='Ⅱ Pause';simulationAnimation=requestAnimationFrame(simulationFrame);
});
$('simulation-progress').addEventListener('input',()=>{pauseSimulation();updateSimulation(Number($('simulation-progress').value)/1000*simulationDuration());});
$('simulation-speed').addEventListener('input',()=>{$('simulation-speed-value').value='×'+$('simulation-speed').value;});
$('simulation-anchor').addEventListener('input',()=>updateSimulation(simulationTime));
$('simulation-color').addEventListener('change',renderRunVisuals);
function showConversionPreview(data,file,report) {
  if(conversionView)conversionView.destroy();$('conversion-preview').replaceChildren();
  const start=data.recordedStart ? new Date(data.recordedStart) : null,c=data.classification || {};
  metrics($('conversion-source-info'),[['Fichier source',file.name],['Taille avant conversion',(report.originalBytes/1048576).toFixed(2)+' Mio'],
    ['Points source',number(report.pointCount)],['Distance',km(data.distance)],['D+',meters(data.ascent)],['D−',meters(data.descent)],
    ['Profil',profileLabel(c)],['Classe de distance',c.distanceLabel || '—'],['Durée enregistrée',data.duration ? time(data.duration) : 'Non disponible'],
    ['Départ',start ? passageDate(start,0) : '—'],['Arrivée',start ? passageDate(start,data.duration) : '—']]);
  conversionView=createCourseView($('conversion-preview'),data,'grade');conversionView.update(0);
}
// Présentation volontaire et mémorisée. Le bouton du ruban permet de la rouvrir.
const tourSteps=[
  ['analysis','Analyse d’un parcours','Importez un GPX, choisissez un modèle, une durée ou une allure, puis calculez les passages. Définissez le départ et les ravitaillements ; carte et profil suivent la lecture.'],
  ['references','Références et modèle prédictif','Importez vos courses chronométrées ou utilisez Garmin. Sélectionnez les références, explorez les profils et distances dans l’histogramme, puis comparez les courbes des modèles.'],
  ['map','Carte des références','Localisez les courses retenues ou exclues du modèle et agrandissez la carte en plein écran.'],
  ['conversion','Conversion GPX','Contrôlez les informations du fichier source et sa trace sur la carte. Compactez sans retirer de données ou allégez les capteurs pour le simulateur, puis téléchargez une copie.'],
  ['backups','Sauvegarde et restauration','Créez une archive complète des références, modèles, scénarios et réglages. Vérifiez une archive avant de restaurer ; une copie de sécurité est créée automatiquement.'],
  ['simulations','Comparaison et lecture simultanée','Importez plusieurs GPX. Le tableau décrit chaque course ; les cartes et profils colorés suivent une horloge commune avec départs alignés, curseur de position et vitesse réglable.']
];
let tourIndex=0,tourReturnScreen='analysis';
function renderTour() {
  const [screen,title,description]=tourSteps[tourIndex];showScreen(screen);
  $('tour-counter').textContent='Découverte · '+(tourIndex+1)+' / '+tourSteps.length;
  $('tour-title').textContent=title;$('tour-description').textContent=description;
  $('tour-previous').disabled=tourIndex===0;$('tour-next').textContent=tourIndex===tourSteps.length-1 ? 'Terminer' : 'Suivant';
}
function openTour() {
  tourReturnScreen=currentScreen;
  tourIndex=0;$('tour-panel').hidden=false;renderTour();$('tour-dialog').focus?.();
}
function closeTour(){ $('tour-panel').hidden=true;showScreen(tourReturnScreen);$('tour-open').focus?.(); }
$('tour-open').addEventListener('click',openTour);
$('tour-close').addEventListener('click',closeTour);
$('tour-next').addEventListener('click',()=>{if(tourIndex<tourSteps.length-1){tourIndex++;renderTour();}else closeTour();});
$('tour-previous').addEventListener('click',()=>{if(tourIndex){tourIndex--;renderTour();}});
$('tour-disabled').addEventListener('change',()=>{try{localStorage.setItem('bzhaventure-tour-disabled',$('tour-disabled').checked ? '1' : '0');}catch(_){}});
document.addEventListener('keydown',event=>{
  if(!$('tour-panel').hidden && event.key==='Escape')closeTour();
  if(!$('tour-panel').hidden && event.key==='Tab') {
    const controls=[$('tour-disabled'),$('tour-previous'),$('tour-next'),$('tour-close')].filter(n=>!n.disabled);
    const first=controls[0],last=controls[controls.length-1];
    if(event.shiftKey && (document.activeElement===first || document.activeElement===$('tour-dialog'))){event.preventDefault();last.focus?.();}
    else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus?.();}
  }
});
try{$('tour-disabled').checked=localStorage.getItem('bzhaventure-tour-disabled')==='1';if(!$('tour-disabled').checked)openTour();}catch(_){openTour();}

// La migration attend la lecture complète de l’ancien stockage navigateur.
const legacyRunsReady = new Promise(resolve=>{
  runDatabase.then(db=>{
    if(!db){resolve();return;}
    const request=db.transaction('runs','readonly').objectStore('runs').get('current');
    request.onsuccess=()=>{
      try{if(!runsRevision && request.result){const saved=JSON.parse(request.result);if(Array.isArray(saved)){
        runs=saved.filter(r=>r.data?.marks?.length && Number.isFinite(r.data.duration)).slice(0,20);
        if(currentScreen==='simulations')renderRuns();
      }}}catch(_){}finally{resolve();}
    };
    request.onerror=()=>resolve();
  }).catch(()=>resolve());
});
