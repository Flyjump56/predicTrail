/** Actualiser le suivi sans recharger la page ni toucher aux formulaires. */
(() => {
  const url = document.currentScript.dataset.operationsUrl;
  let previous = {};
  let stopped = false;

  function render(node, state, failure) {
    const bar = node.querySelector('progress');
    const label = node.querySelector('span');
    bar.hidden = !state || Boolean(failure);
    let text = failure || 'Aucun calcul depuis le démarrage du serveur.';
    if (state && !failure) {
      const percent = Math.round(state.progress * 100);
      bar.value = percent;
      const status = {loading:'En cours', ready:'Terminé', error:'Échec'}[state.status] || 'Calcul';
      const kind = state.kind === 'garmin' ? 'Import Garmin' : 'Mise à jour des références et des modèles';
      const files = state.total ? ' · '+state.completed+' / '+state.total : '';
      const slow = state.slow ? ' · traitement long' : '';
      text = status+' · '+kind+' · '+percent+' % · '+state.message+files+' · '+Math.round(state.elapsed)+' s'+slow;
    }
    if (label.textContent !== text) label.textContent = text;
  }

  async function refresh() {
    const nodes = Array.from(document.querySelectorAll('[data-operation-account]'))
      .filter(node => node.dataset.operationAccount && !node.hidden);
    try {
      if (!document.hidden && nodes.length) {
        const response = await fetch(url);
        if (!response.ok) {
          stopped = response.status === 401 || response.status === 403;
          throw Error(stopped ? 'Reconnectez-vous pour suivre les calculs.' : 'Suivi momentanément indisponible.');
        }
        const {operations} = await response.json();
        for (const node of nodes) render(node, operations[node.dataset.operationAccount]);
        for (const [account,state] of Object.entries(operations)) {
          if (previous[account]?.status === 'loading' && state.status !== 'loading') {
            document.dispatchEvent(new CustomEvent('predictrail-operation-finished',{detail:account}));
          }
        }
        previous = operations;
      }
    } catch (error) {
      for (const node of nodes) render(node, null, error.message);
    } finally {
      if (!stopped) setTimeout(refresh,2000);
    }
  }

  refresh();
})();
