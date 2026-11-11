/** Sauvegarde locale des scénarios et export complet ; aucun identifiant Garmin. */
const stateFields=['prediction-mode','prediction-model','manual-total','manual-pace','spacing','departure',
 'analysis-adjustment','analysis-split','analysis-split-percent','analysis-climb','color-mode','play-speed',
 'simulation-mode','simulation-model','simulation-total','simulation-pace','simulation-departure',
 'simulation-spacing','simulation-anchor','simulation-color','simulation-speed','import-kind','import-profile',
 'import-distance-class','import-min-km','import-max-km','import-min-date','import-max-date'];
const pendingStateChoices={};
let stateHydrated=false,stateTimer=null,lastAnalysis=null,restoreToken=null,stateSequence=0,stateRetries=0;
if (hostedAccount) {
  $('backup-select').hidden=true;
  $('backup-restore').hidden=true;
  $('backup-status').textContent='Les sauvegardes concernent uniquement votre compte. La restauration est assurée par la maintenance du serveur.';
}
function captureState(){
  if(routeData?.sourceId && selectedFile)lastAnalysis={sourceId:routeData.sourceId,name:selectedFile.name};
  return {runs,settings:Object.fromEntries(stateFields.map(id=>[id,pendingStateChoices[id] ?? $(id).value])),waypoints:customPoints,lastAnalysis,
    tourDisabled:$('tour-disabled').checked};
}
function applyClientState(state,resetAnalysis=false){
  if(!state)return;
  if(resetAnalysis){analysisVersion++;pausePlayback();routeData=null;selectedFile=null;activeRouteKey='';$('result').hidden=true;analysisBusy(false);}
  runs=Array.isArray(state.runs) ? state.runs : [];lastAnalysis=state.lastAnalysis || null;
  customPoints=state.waypoints || [];
  for(const [id,value] of Object.entries(state.settings || {}))if(stateFields.includes(id)){
    if(['prediction-model','simulation-model'].includes(id))pendingStateChoices[id]=value;
    $(id).value=value;
  }
  restoreDeferredChoices();
  $('tour-disabled').checked=!!state.tourDisabled;
  if(!hostedAccount)try{localStorage.setItem('bzhaventure-tour-disabled',state.tourDisabled ? '1' : '0');}catch(_){}
  if(state.tourDisabled)$('tour-panel').hidden=true;
  updatePredictionMode();renderWaypoints();
  if(currentScreen==='simulations')renderRuns();
}
function scheduleStateSave(){
  if(!stateHydrated)return;
  clearTimeout(stateTimer);
  stateTimer=setTimeout(async()=>{
    const sequence=++stateSequence;
    try{await postJSON('/api/state',{state:captureState()});stateRetries=0;}
    catch(error){if(sequence===stateSequence)$('backup-status').textContent='Réglages non synchronisés : '+error.message+(hostedAccount ? ' Réessayez la sauvegarde avant de quitter la page.' : ' Les scénarios restent dans ce navigateur ; réessayez la sauvegarde après la mise à jour.');if(stateRetries++<24)setTimeout(scheduleStateSave,5000);}
  },600);
}
async function hydrateState(attempt=0){
  await legacyRunsReady;
  try{
    const response=await requestJSON('/api/state');
    if(response.state && !runsRevision)applyClientState(response.state);
    stateHydrated=true;
    if(!response.state || runsRevision)scheduleStateSave();
  }catch(error){if(attempt<24)setTimeout(()=>hydrateState(attempt+1),5000);}
}
function restoreDeferredChoices(){
  for(const [id,value] of Object.entries(pendingStateChoices)){
    if(Array.from($(id).options).some(o=>o.value===value)){$(id).value=value;delete pendingStateChoices[id];}
  }
}
for(const id of stateFields)$(id).addEventListener('change',()=>{delete pendingStateChoices[id];scheduleStateSave();});
$('tour-disabled').addEventListener('change',scheduleStateSave);
for(const id of ['add-waypoint','clear-waypoints']){const node=document.getElementById(id);if(node)node.addEventListener('click',scheduleStateSave);}
function setBackupBusy(busy){$('backup-create').disabled=busy;$('backup-select').disabled=busy;$('backup-restore').disabled=busy || !restoreToken;}
$('backup-create').addEventListener('click',async()=>{
  setBackupBusy(true);$('backup-status').textContent='Création de l’archive complète… Cette étape peut prendre quelques minutes pour les grandes bibliothèques.';
  try{
    await legacyRunsReady;
    const result=await postJSON('/api/backup/create',{state:captureState()});
    const link=element('a','Télécharger '+result.name);link.href=apiUrl(result.url);link.download=result.name;
    $('backup-download').replaceChildren(link);$('backup-status').textContent='Sauvegarde créée · '+(result.bytes/1048576).toFixed(1)+' Mio. Téléchargez-la et copiez-la sur un autre support.';
  }catch(error){$('backup-status').textContent=error.message;}finally{setBackupBusy(false);}
});
$('backup-select').addEventListener('click',()=>$('backup-file').click());
$('backup-file').addEventListener('change',async()=>{
  const file=$('backup-file').files[0];$('backup-file').value='';if(!file)return;
  restoreToken=null;setBackupBusy(true);$('backup-status').textContent='Vérification complète de l’archive…';
  try{
    if(file.size>2*1024**3)throw Error('Archive limitée à 2 Gio.');
    const result=await requestJSON('/api/backup/inspect',{method:'POST',headers:{'Content-Type':'application/zip'},body:file});
    restoreToken=result.token;$('backup-preview').textContent=file.name+' · version '+result.version+' · '+new Date(result.createdAt).toLocaleString('fr-FR')+' · '+result.files+' fichiers vérifiés.';
    $('backup-status').textContent='Archive vérifiée. La restauration remplacera les données locales après sauvegarde de sécurité.';
  }catch(error){$('backup-status').textContent=error.message;}finally{setBackupBusy(false);}
});
$('backup-restore').addEventListener('click',async()=>{
  if(!restoreToken)return;
  setBackupBusy(true);$('backup-status').textContent='Restauration et reconstruction des modèles en cours…';
  try{
    await postJSON('/api/backup/restore',{token:restoreToken});
    let restoreWarning='';
    while(true){
      const operation=await requestJSON('/api/operation');
      if(operation.status==='error'){if(operation.result?.restored){restoreWarning=operation.message;break;}throw Error(operation.message);}
      if(operation.status==='ready')break;
      $('backup-status').textContent=operation.message;await new Promise(resolve=>setTimeout(resolve,1000));
    }
    const response=await requestJSON('/api/state');applyClientState(response.state,true);runsRevision++;
    await refreshLocal();await showReferences();
    $('backup-status').textContent='Données restaurées. Une archive avant-restauration est conservée dans le dossier local des sauvegardes.'+(restoreWarning ? ' Recalcul des modèles : '+restoreWarning : '');
  }catch(error){$('backup-status').textContent=error.message;}finally{setBackupBusy(false);}
});
$('resume-analysis').addEventListener('click',async()=>{
  try{
    if(!lastAnalysis)throw Error('Aucun parcours conservé : importez-en un dans Analyse.');
    const response=await apiFetch('/api/source?id='+lastAnalysis.sourceId);
    if(!response.ok)throw Error('Le GPX source n’est pas disponible dans cette sauvegarde.');
    const file=new File([await response.blob()],lastAnalysis.name || 'parcours.gpx',{type:'application/gpx+xml'});
    selectedFile=file;showScreen('analysis');await analyze(file);
  }catch(error){$('backup-status').textContent=error.message;}
});
hydrateState();

async function showBackups(){
  try{
    const report=await requestJSON('/api/backup/list');$('backup-history').replaceChildren();
    if(report.automatic)$('backup-history').append(element('p',report.automatic.message));
    for(const item of report.backups){const link=element('a',new Date(item.createdAt).toLocaleString('fr-FR')+' · '+item.label+' · '+(item.bytes/1048576).toFixed(1)+' Mio');link.href=apiUrl('/api/backup/download?token='+item.token);link.download='PredicTrail-'+item.token+'.zip';const row=element('p','');row.append(link);$('backup-history').append(row);}
  }catch(error){$('backup-history').textContent=error.message;}
}
$('backup-refresh').addEventListener('click',showBackups);
$('tab-backups').addEventListener('click',showBackups);
