/* Contrôle du contrôleur web avec un document et une API locaux simulés. */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const nodes = new Map();
class Node {
  constructor(tag='div') {
    this.tag = tag;
    this.children = [];
    this.events = {};
    this.attributes = {};
    this.textContent = '';
    this.value = '';
    this.hidden = false;
    this.disabled = false;
    this.style = {};
    const classes=new Set();
    this.classList = {add(...values){values.forEach(v=>classes.add(v));},remove(...values){values.forEach(v=>classes.delete(v));},contains(value){return classes.has(value);}};
  }
  set id(value) { this._id=value; nodes.set(value,this); }
  get id() { return this._id; }
  get options() { return this.children; }
  get rows() { return this.children; }
  get cells() { return this.children; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children=children; }
  addEventListener(name,handler) {
    const previous=this.events[name];
    this.events[name]=previous ? (...args)=>{const first=previous(...args);const second=handler(...args);return first instanceof Promise ? Promise.all([first,second]) : second ?? first;} : handler;
  }
  setAttribute(name,value) { this.attributes[name]=String(value); }
  setCustomValidity(message) { this.validationMessage=message; }
  reportValidity() { return !this.validationMessage; }
  insertRow() { const node=new Node('tr'); this.append(node); return node; }
  insertCell() { const node=new Node('td'); this.append(node); return node; }
  createCaption() { const node=new Node('caption'); this.append(node); return node; }
  createTHead() { const node=new Node('thead'); this.append(node); return node; }
  createTBody() { const node=new Node('tbody'); this.append(node); return node; }
}
const document = {
  body:new Node(),
  getElementById(id) { if(!nodes.has(id)) { const node=new Node(); node.id=id; } return nodes.get(id); },
  createElement:tag=>new Node(tag),
  createElementNS:(_,tag)=>new Node(tag),
  createTextNode:text=>text,
  events:{},
  addEventListener(name,handler){ (this.events[name] ||= []).push(handler); },
  querySelectorAll(){return [];},
};
const get=id=>document.getElementById(id);
for(const [id,value] of Object.entries({
  'spacing':'5','prediction-mode':'total','prediction-model':'auto','manual-total':'10:00:00',
  'color-mode':'grade','play-speed':'600','departure':'2026-11-08T07:00','import-kind':'all',
})) get(id).value=value;

const classification = {profile:'flat',profileLabel:'Plat / Vallonné',distanceClass:'short',
  distanceLabel:'Moins de 50 km',reliefDensity:20,longReliefShare:0,sampling:50};
const model = {curve:[{grade:-50,speed:5},{grade:50,speed:2}],observations:[],samples:0,
  scope:'global',status:'Test',count:2,exactCount:2,localWeight:.5};
const models = ['flat','mountain','sawtooth','mixed'].flatMap(profile=>
  ['very_short','short','medium','long','ultra'].map(distanceClass=>({...model,profile,distanceClass,
    profileLabel:profile,distanceLabel:distanceClass,sampling:100,references:[],error:null})));
const references = {courses:[],models,model,inclinationModel:model,error:6.3,meanError:9.7,
  baselineError:7.5,baselineMeanError:9.7,skipped:[],cache:{restored:true,reused:16,total:16},
  inclinationTest:{courseCount:16,medianError:7.3,meanError:10.3,bands:[]}};
const requests = [];
const pending = [];
let holdPredictions = false;
let centralState=null;
let activities = [
  {id:'one',name:'Course',kind:'running',source:'gpx',distance:20000,date:'2026-05-01',reference:1,profile:'flat',distanceClass:'short'},
  {id:'two',name:'Vélo',kind:'cycling',source:'garmin',distance:30000,date:'2026-05-02',reference:0,profile:'mountain',distanceClass:'short'},
];
function prediction(options) {
  const duration = options.mode==='recorded' ? 4800 : options.mode==='pace' ? options.paceSeconds*10 : options.totalSeconds;
  const marks = [[0,0,48,2,100,'Départ'],[10000,duration,48.1,2.1,100,'Arrivée']];
  for(const point of options.waypoints) {
    marks.push([point.km*1000,duration*point.km/10,48.05,2.05,100,'Repère · '+point.comment]);
  }
  marks.sort((a,b)=>a[0]-b[0]);
  return {classification,distance:10000,duration,ascent:10,descent:10,marks,
    exportPoints:[[[48,2,100,0],[48.1,2.1,100,duration]]],customWaypoints:options.waypoints,trace:[[[48,2],[48.1,2.1]]],profile:[[[0,100],[10000,100]]],
    recordedStart:'2026-05-01T06:00:00+00:00',
    model:{...model,scope:options.mode==='recorded' ? 'recorded' : 'manual',selectionLabel:options.mode==='recorded' ? 'Temps enregistrés du GPX' : 'Durée manuelle'},
    movingDuration:null,pauses:{duration:null,fraction:null,referenceCount:0,unknownFraction:0,status:'Manuel'},
    terrain:[{name:'Plat',distance:10000,actual:null,estimated:duration}],
    sections:[{start:[48,2,100],end:[48.1,2.1,100],distance:0,endDistance:10000,
      time:0,endTime:duration,grade:0,speed:36000/duration}]};
}
async function fetch(url,request={}) {
  requests.push({url,request});
  let data;
  if(url==='/api/state') {if(request.method==='POST'){centralState=JSON.parse(request.body).state;data={saved:true};}else data={state:centralState};}
  else if(url==='/api/backup/list')data={backups:[]};
  else if(url==='/api/backup/create'){centralState=JSON.parse(request.body).state;data={token:'a'.repeat(32),name:'PredicTrail-test.zip',url:'/api/backup/download?token='+ 'a'.repeat(32),bytes:100};}
  else if(url==='/api/backup/inspect')data={token:'a'.repeat(32),version:'3.0.0',createdAt:'2026-11-08T07:00:00Z',files:4};
  else if(url==='/api/backup/restore')data={accepted:true};
  else if(url==='/api/startup') data={status:'ready',progress:1,elapsed:.2};
  else if(url==='/api/references') data=references;
  else if(url==='/api/reference-selection') data={references:[{key:'file:one',name:'Course native',enabled:true}]};
  else if(url==='/api/reference-map') data={courses:[{key:'one',name:'Course localisée',enabled:true,trace:[[[48,2],[48.1,2.1]]],classification:{...classification,distance:10000}}],skipped:[]};
  else if(url==='/api/garmin/stop') data={stopping:true,message:'Arrêt demandé'};
  else if(url==='/api/runtime') data={python:'3.9.1',version:'1.2.1'};
  else if(url==='/api/local') data={activities};
  else if(url==='/api/garmin/status') data={available:false,connected:false,message:'Facultatif'};
  else if(url==='/api/operation') data={status:'ready',progress:1,message:'Terminé',result:{deleted:1}};
  else if(url==='/api/local/delete') { activities=activities.filter(a=>a.kind!=='cycling'); data={accepted:true}; }
  else if(url==='/api/gpx/convert') {
    const options=JSON.parse(request.body);
    data={gpx:options.gpx,report:{originalBytes:26000000,convertedBytes:11000000,gainPercent:57.7,
      pointCount:64292,optimized:true,optimizable:true,importable:true,recordedCompatible:true,removedExtensions:0}};
  }
  else if(url==='/api/prediction') {
    const options=JSON.parse(request.body);
    if(holdPredictions) return new Promise(resolve=>pending.push(()=>resolve({ok:true,json:async()=>prediction(options)})));
    data=prediction(options);
  } else throw Error('Route inattendue '+url);
  return {ok:true,json:async()=>data};
}
class FileReader {
  readAsDataURL() {
    setImmediate(()=>{this.result='data:application/gpx+xml;base64,PHg+';this.onload();});
  }
}
const savedRuns=new Map();
const localStorage={getItem:key=>savedRuns.get(key)||null,setItem:(key,value)=>savedRuns.set(key,value)};
const context = {localStorage,document,window:{addEventListener(){},confirm:()=>true},fetch,FileReader,console,
  Blob,atob,URL:{createObjectURL:()=> 'blob:qa-gpx',revokeObjectURL(){}},
  clearTimeout(){},setTimeout(){},requestAnimationFrame:()=>1,cancelAnimationFrame(){}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/bzhaventure/web/app.js'),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/bzhaventure/web/backup.js'),'utf8'),context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function settle() { for(let i=0;i<8;i++) await tick(); }
async function run() {
  await vm.runInContext(`(async () => {
    const pending = [];
    const job = processGpxFiles(['A','B','C'].map(name => ({name})),file =>
      new Promise((resolve,reject) => pending.push({name:file.name,resolve,reject})));
    if (pending.map(p => p.name).join('') !== 'AB') throw Error('Deux fichiers doivent démarrer ensemble.');
    pending[1].reject(Error('GPX invalide'));
    await Promise.resolve();
    if (pending[2]?.name !== 'C') throw Error('Le lot doit continuer après un échec.');
    pending[2].resolve('C');
    pending[0].resolve('A');
    const results = await job;
    if (results[0].value !== 'A' || !results[1].error.startsWith('B') || results[2].value !== 'C')
      throw Error('Les résultats doivent suivre l’ordre de sélection.');
  })()`,context);
  await settle();
  assert(get('cache-info').textContent.includes('16 / 16'));
  assert(get('garmin-overview').textContent.includes('Facultatif'));
  assert(get('runtime-info').textContent.includes('Python 3.9.1'));
  assert.equal(get('model-groups').rows.length,20);
  const file={name:'test.gpx',size:100};
  get('file').files=[file];
  get('file').events.change();
  await settle();
  assert(get('arrival-estimate').textContent.includes('17:00:00'));
  get('waypoint-km').value='3.125';
  get('waypoint-comment').value='Eau <script>';
  get('add-waypoint').events.click();
  await settle();
  assert(get('marks').rows.some(row=>row.cells[0].textContent.includes('Eau <script>')));
  get('prediction-mode').value='pace';
  get('prediction-mode').events.change();
  get('manual-pace').value='06:00';
  get('calculate-route').events.click();
  await settle();
  assert(get('arrival-estimate').textContent.includes('08:00:00'));

  // Deux réponses inversées doivent conserver la dernière demande de l'utilisateur.
  holdPredictions=true;
  get('prediction-mode').value='total';
  get('manual-total').value='10:00:00';
  const old=vm.runInContext('analyze(selectedFile)',context);
  await settle();
  get('manual-total').value='12:00:00';
  const current=vm.runInContext('analyze(selectedFile)',context);
  await settle();
  assert.equal(pending.length,2);
  pending[1](); await current;
  pending[0](); await old;
  assert(get('arrival-estimate').textContent.includes('19:00:00'));
  holdPredictions=false;

  get('import-profile').value='flat'; get('import-profile').events.change();
  assert.equal(get('local-activities').rows.length,1);
  get('import-profile').value='mountain'; get('import-profile').events.change();
  assert.equal(get('local-activities').rows.length,1);
  get('import-distance-class').value='ultra'; get('import-distance-class').events.change();
  assert.equal(get('local-activities').rows.length,0);
  get('import-distance-class').value='short';
  get('import-kind').value='cycling';
  get('import-min-km').value='25';
  get('import-max-km').value='35';
  get('import-kind').events.change();
  assert.equal(get('local-activities').rows.length,1);
  get('delete-matching').events.click();
  await settle();
  const removal=requests.find(r=>r.url==='/api/local/delete');
  const selection=JSON.parse(removal.request.body);
  assert.equal(selection.scope,'matching');
  assert.equal(selection.filters.kind,'cycling');
  assert.equal(selection.filters.profile,'mountain');
  assert.equal(selection.filters.distanceClass,'short');
  assert.equal(activities.length,1);
  get('tab-simulations').events.click();
  assert(get('screen-analysis').hidden);
  get('run-name').value='Prudent';
  get('save-run').events.click();
  assert.equal(get('simulation-runs').rows.length,1);
  assert(savedRuns.get('bzhaventure-runs-v1').includes('Prudent'));
  get('manual-total').value='10:00:00';
  await vm.runInContext('analyze(selectedFile)',context);
  get('run-name').value='Rapide'; get('save-run').events.click();
  assert.equal(get('simulation-runs').rows.length,2);
  assert(get('simulation-runs').rows[1].cells[5].textContent.includes('10:00:00'));
  const xml=vm.runInContext('buildGpx(routeData,"A < B",departureDate())',context);
  assert(xml.includes('A &lt; B'));
  assert(xml.includes('<trkpt lat="48"'));
  assert(xml.includes('<wpt lat='));
  assert(xml.includes('Eau &lt;script&gt;'));
  assert(xml.includes('<time>'));
  get('tab-analysis').events.click();
  assert(!get('screen-analysis').hidden);
  const groupResult=vm.runInContext(`(() => {
    const make=(name,profile,distance,actual,groupEstimated)=>({name,actual,groupEstimated,estimated:actual,
      distance:10000,ascent:100,classification:{profile,distanceClass:distance}});
    const a=make('A','flat','short',100,120),b=make('B','flat','short',90,110),
      c=make('C','mountain','long',50,null),d=make('D','flat','long',200,201);
    const list=[a,b,c,d];const r=rankReferenceGroups(list,'performance');
    return {ranks:[a,b,c,d].map(x=>r.rank.get(x)),closest:r.closest.has(c),groups:r.groups.size};
  })()`,context);
  assert.deepEqual(Array.from(groupResult.ranks),[2,1,1,1]);
  assert.equal(groupResult.closest,false); assert.equal(groupResult.groups,3);
  get('simulation-mode').value='total';
  get('simulation-mode').events.change();
  assert(!get('simulation-total-fields').hidden);
  get('simulation-total').value='09:00:00';
  get('simulation-spacing').value='5';
  get('simulation-departure').value='2026-11-08T07:00';
  get('simulation-files').files=[{name:'nouveau.gpx',size:120}];
  get('simulation-files').events.change();
  await get('simulate-files').events.click();
  assert.equal(get('simulation-runs').rows.length,3);
  assert(get('simulation-runs').rows[2].cells[0].textContent.includes('nouveau.gpx'));
  assert(get('simulation-runs').rows[2].cells[5].textContent.includes('09:00:00'));
  get('simulation-mode').value='recorded'; get('simulation-mode').events.change();
  assert(get('simulation-departure-fields').hidden); assert(get('simulation-total-fields').hidden);
  get('simulation-departure').value='invalid date'; // Ne doit pas altérer les dates du GPX.
  await get('simulate-files').events.click();
  assert.equal(get('simulation-runs').rows.length,4);
  assert(get('simulation-runs').rows[3].cells[5].textContent.includes('01:20:00'));
  assert(get('simulation-runs').rows[3].cells[6].textContent.includes('2026'));
  const conversions=requests.filter(r=>r.url==='/api/gpx/convert');
  assert(conversions.length>=2);
  assert.equal(JSON.parse(conversions.at(-1).request.body).mode,'compact');
  assert(get('gpx-import-reports').children.some(n=>n.textContent.includes('57.7 %')));
  assert(get('gpx-import-reports').children.some(n=>n.children.some(c=>c.download?.endsWith('-compact.gpx'))));
  const recordedRequest=JSON.parse(requests.filter(r=>r.url==='/api/prediction').at(-1).request.body);
  assert.equal(recordedRequest.mode,'recorded');
  assert(!('totalSeconds' in recordedRequest)); assert(!('paceSeconds' in recordedRequest));
  get('garmin-email').value='test@example.com'; get('garmin-password').value='test-only';
  await get('garmin-connect').events.click(); // API indisponible simulée : erreur visible hors panneau.
  assert(get('garmin-overview').textContent.includes('/api/garmin/connect'));
  assert.equal(get('garmin-password').value,'');
  assert.equal(get('garmin-connect').disabled,false);
  const makeReference=(name,cls,distance)=>({...prediction({mode:'total',totalSeconds:3600,waypoints:[]}),
    name,classification:cls,distance,actual:3600,estimated:3500,groupEstimated:3500,inclinationEstimated:null,
    model:{...model,status:'Test',exactCount:1},pauses:{duration:60,count:1,unobserved:0}});
  references.courses=[makeReference('Course plate',classification,10000),
    makeReference('Course montagne',{...classification,profile:'mountain',profileLabel:'Intermédiaire / Montagne',distanceClass:'long'},130000)];
  await vm.runInContext('showReferences()',context);
  const bars=get('reference-histogram').children[0].children.filter(n=>n.tag==='g');
  assert.equal(bars.length,20); assert.equal(get('histogram-legend').children.length,5);
  const flatBar=bars.find(n=>n.attributes['data-profile']==='flat' && n.attributes['data-distance']==='short');
  flatBar.events.click();
  assert.equal(get('histogram-course-list').rows.length,1);
  assert.equal(flatBar.attributes['aria-pressed'],'true');
  assert(get('histogram-filter-summary').textContent.includes('1 course'));
  assert(vm.runInContext('referenceRows[1].row.hidden',context));
  get('histogram-course-list').rows[0].cells[4].children[0].events.click();
  assert(!vm.runInContext('referenceRows[0].branch.hidden',context));
  const emptyBar=bars.find(n=>n.attributes['data-profile']==='flat' && n.attributes['data-distance']==='ultra');
  emptyBar.events.keydown({key:'Enter',preventDefault(){}});
  assert.equal(get('histogram-course-list').rows.length,0);
  assert(get('histogram-filter-summary').textContent.includes('Aucune course'));
  get('clear-histogram-filter').events.click();
  assert(!vm.runInContext('referenceRows[1].row.hidden',context));
  assert(!vm.runInContext('referenceRows[0].branch.hidden',context));
  assert.equal(vm.runInContext('referenceCourses.length',context),2);
  get('tab-map').events.click(); await settle();
  assert(!get('screen-map').hidden);
  assert.equal(get('reference-map-list').rows.length,1);
  assert(get('reference-map-status').textContent.includes('1 course'));
  assert(get('reference-map').children[0].attributes['aria-label'].includes('Traces'));
  await get('garmin-stop').events.click();
  assert(get('library-status').textContent.includes('Arrêt demandé'));
  assert(vm.runInContext("validationHealth({status:'loading',slow:true,lastProgressAgo:45,validationTimeout:180})",context).includes('180'));
  const referencePanel=get('reference-map-panel');
  referencePanel.requestFullscreen=async()=>{ document.fullscreenElement=referencePanel; };
  document.exitFullscreen=async()=>{ document.fullscreenElement=null; };
  await get('reference-map-fullscreen').events.click();
  assert.equal(get('reference-map-fullscreen').attributes['aria-pressed'],'true');
  assert(get('reference-map-fullscreen').textContent.includes('Quitter le plein écran'));
  await get('reference-map-fullscreen').events.click();
  assert.equal(get('reference-map-fullscreen').attributes['aria-pressed'],'false');
  referencePanel.requestFullscreen=async()=>{throw Error('API refusée');};
  await get('reference-map-fullscreen').events.click();
  assert(referencePanel.classList.contains('expanded'));
  assert(document.body.classList.contains('reference-map-fullscreen'));
  for(const handler of document.events.keydown) handler({key:'Escape'});
  assert(!referencePanel.classList.contains('expanded'));
  assert(!document.body.classList.contains('reference-map-fullscreen'));
  assert.equal(get('reference-map-fullscreen').attributes['aria-pressed'],'false');
  // Le tableau du modèle suit la courbe sélectionnée.
  get('model-select').value='1';get('model-select').events.change();
  assert.equal(get('model-groups').rows.filter(r=>!r.hidden).length,1);
  get('model-select').value='global';get('model-select').events.change();
  assert.equal(get('model-groups').rows.filter(r=>!r.hidden).length,20);
  get('model-select').value='inclination';get('model-select').events.change();
  assert.equal(get('model-groups').rows.filter(r=>!r.hidden).length,20);
  // Le guide peut être fermé, désactivé et réactivé.
  get('tour-open').events.click();assert(!get('tour-panel').hidden);
  get('tour-next').events.click();assert(get('tour-title').textContent.includes('Références'));
  get('tour-disabled').checked=true;get('tour-disabled').events.change();
  assert.equal(savedRuns.get('bzhaventure-tour-disabled'),'1');
  get('tour-disabled').checked=false;get('tour-disabled').events.change();
  assert.equal(savedRuns.get('bzhaventure-tour-disabled'),'0');get('tour-close').events.click();
  assert(get('tour-panel').hidden);
  // Des durées différentes partagent le même temps écoulé, avec arrêt à l'arrivée.
  get('tab-simulations').events.click();
  assert.equal(get('simulation-views').children.length,4);
  const originalRuns=vm.runInContext('JSON.stringify(runs)',context);
  get('simulation-progress').value='500';get('simulation-progress').events.input();
  assert(vm.runInContext('simulationTime',context)>0);
  assert(vm.runInContext('runViews[3].status.textContent',context).includes('Arrivé'));
  assert(!vm.runInContext('runViews[0].status.textContent',context).includes('Arrivé'));
  const position=vm.runInContext('positionInSections(viewSections(runs[0].data),runs[0].data.duration/2)',context);
  assert.equal(position.distance,5000);
  const gapPosition=vm.runInContext(`positionInSections([
    {start:[0,0,0],end:[1,1,1],distance:0,endDistance:100,time:0,endTime:10,speed:36},
    {start:[2,2,2],end:[3,3,3],distance:100,endDistance:200,time:20,endTime:30,speed:36}],15)`,context);
  assert.equal(gapPosition.distance,100);assert.equal(gapPosition.point[0],1);
  get('simulation-speed').value='1200';get('simulation-speed').events.input();
  assert.equal(get('simulation-speed-value').value,'×1200');
  get('simulation-color').value='elevation';get('simulation-color').events.change();
  assert.equal(vm.runInContext('JSON.stringify(runs)',context),originalRuns);
  get('simulation-play').events.click();assert.equal(get('simulation-play').textContent,'Ⅱ Pause');
  get('simulation-play').events.click();assert(get('simulation-play').textContent.includes('Lire'));
  get('simulation-runs').rows[3].cells[10].children[1].events.click();
  assert.equal(get('simulation-views').children.length,3);
  get('tab-conversion').events.click();assert(!get('screen-conversion').hidden);assert(get('screen-simulations').hidden);
  // Les réglages sont appliqués dans Analyse, sans modifier les imports comparés.
  get('analysis-adjustment').value='-10';get('analysis-split').value='negative';
  get('analysis-split-percent').value='15';get('analysis-climb').value='20';
  await vm.runInContext('analyze(selectedFile)',context);
  const adjustedRequest=JSON.parse(requests.filter(r=>r.url==='/api/prediction').at(-1).request.body);
  assert.equal(adjustedRequest.strategy.adjustmentPercent,-10);assert.equal(adjustedRequest.strategy.split,'negative');
  assert.equal(adjustedRequest.strategy.climbPercent,20);assert(!get('analysis-strategy-fields').disabled);
  get('simulation-mode').value='total';get('simulation-mode').events.change();get('simulation-departure').value='';
  await get('simulate-files').events.click();
  assert(!JSON.parse(requests.filter(r=>r.url==='/api/prediction').at(-1).request.body).strategy);
  get('simulation-mode').value='recorded';get('simulation-mode').events.change();await get('simulate-files').events.click();
  assert(!JSON.parse(requests.filter(r=>r.url==='/api/prediction').at(-1).request.body).strategy);
  // Le centrage Leaflet utilise les bornes de la référence sélectionnée et montre sa fiche.
  const focused=vm.runInContext(`(() => {
    referenceMapData.courses.push({key:'two',name:'Autre course',enabled:true,trace:[[[42,1],[42.2,1.2]]],
      classification:{profile:'sawtooth',profileLabel:'Dent de scie',distance:12000,distanceLabel:'Moins de 20 km'},
      summary:{distance:12000,ascent:900,descent:850,profile:[[[0,100],[12000,150]]]},
      terrain:[{name:'Montée',distance:12000,actual:7000,estimated:null}],unassigned:200,
      pauses:{duration:120,count:1,unobserved:200},duration:7200,recordedStart:'2026-01-01T06:00:00Z'});
    window.L=true;L={latLngBounds:points=>points};
    referenceMap={invalidateSize(){},fitBounds(bounds){this.bounds=bounds}};
    selectReferenceCourse('two');const result=referenceMap.bounds;
    window.L=false;referenceMap=null;return result;
  })()`,context);
  assert.equal(focused[0][0],42);assert.equal(focused[1][1],1.2);
  assert(!get('reference-course-details').hidden);assert.equal(get('reference-course-select').value,'two');
  assert(get('reference-course-info').children.some(n=>n.children.some(c=>c.textContent.includes('Dents de scie'))));
  const courseAnalysis = get('reference-course-analysis').children;
  assert.deepEqual(courseAnalysis.map(section=>section.children[0].textContent),
    ['Profil et dénivelé','Montée, plat et descente','Pauses et enregistrement GPX']);
  assert(courseAnalysis[0].children[1].children.some(node=>node.tag==='svg'));
  assert(courseAnalysis[1].children[1].children[0].children[1].rows[0].cells.some(cell=>cell.textContent==='Temps GPX'));
  assert(courseAnalysis[2].children[1].children.some(metric=>metric.children.some(node=>node.textContent==='00:02:00')));

  get('tab-backups').events.click();assert(!get('screen-backups').hidden);
  await get('backup-create').events.click();assert(centralState.runs.length>0);
  assert.equal(centralState.settings['analysis-adjustment'],'-10');
  assert(!('garmin-password' in centralState.settings));
  assert(get('backup-download').children[0].href.includes('/api/backup/download'));
  get('backup-file').files=[{name:'sauvegarde.zip',size:100}];await get('backup-file').events.change();
  assert(!get('backup-restore').disabled);assert(get('backup-preview').textContent.includes('4 fichiers'));
  vm.runInContext(`(() => {
    const saved = runs;
    const mark = (distance,label) => [distance,distance/2,48,2,100,label];
    runs = [
      {name:'Crêtes',file:'cretes.gpx',routeKey:'a',data:{
        marks:[mark(0,'Départ'),mark(1500,'Passage'),mark(2000,'Arrivée')],
        sections:[
          {distance:0,endDistance:1000,start:[48,2,100],end:[48,2,200]},
          {distance:1000,endDistance:2000,start:[48,2,400],end:[48,2,340]}
        ],ascent:100,descent:60
      }},
      {name:'Vallée',file:'vallee.gpx',routeKey:'b',data:{
        marks:[mark(0,'Départ'),mark(1000,'Passage'),mark(3000,'Arrivée')],
        profile:[[[0,50],[1000,30],[3000,60]]],ascent:30,descent:20
      }}
    ];
    renderRunPassages();
    runs = saved;
  })()`,context);
  const passages = get('simulation-marks').rows;
  assert.equal(get('simulation-marks-head').rows[0].cells.length,3);
  assert.equal(passages.length,4);
  assert.equal(passages[1].cells[1].textContent,'—');
  assert.equal(passages[1].cells[2].textContent,'1,00 km · D+ 0 m · D− 20 m');
  assert.equal(passages[2].cells[1].textContent,'1,50 km · D+ 100 m · D− 30 m');
  assert.equal(passages[2].cells[2].textContent,'—');
  assert.equal(passages[3].cells[1].textContent,'2,00 km · D+ 100 m · D− 60 m');
  assert.equal(passages[3].cells[2].textContent,'3,00 km · D+ 30 m · D− 20 m');
  console.log('Interface vérifiée · modèles filtrés, guide réactivable, conversion, comparaison synchronisée, curseur, vitesse, coloration, retrait des runs et fonctions existantes.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
