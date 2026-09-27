/* Workshop-only adapter, injected inside each review's existing script scope.
 * Loaded by: python scripts/build_portable_review.py
 * Production autosave is intentionally not modified.
 */
function saveDraft() {
  if (!workshopRestoring) parent.workshopChanged?.(window);
  return true;
}
function restoreDraft() {}
function queueFileAutosave() {}
function queueAutomaticReviewOutput() {}
function queueReviewOutputWrite() { return false; }
function queueReviewOutputDelete() { return false; }
function initializeStandaloneAutosave() {}
function setAutosaveStatus() {}

window.workshopReview = {
  capture() {
    if (typeof closeActiveInput === 'function') closeActiveInput();
    return {draft:draftPayload(), scroll:window.scrollY};
  },
  restore(saved) {
    if (!saved) return;
    workshopRestoring = true;
    try {
      if (!restoreStandaloneAutosaveDraft(saved.draft)) throw Error('Saved review state does not match this document.');
      setTimeout(() => window.scrollTo(0, saved.scroll || 0), 0);
    } finally { workshopRestoring = false; }
  },
  exportData(format) {
    if (typeof collectJsonForParent === 'function') {
      const output = format === 'md' ? collectMarkdownForParent() : collectJsonForParent();
      const result = groundTruth();
      const pending = result.agent_review?.pending_confirmation_count || result.consensus_review?.pending_confirmation_count || 0;
      return {...output, complete: result.technical_complete === true && pending === 0};
    }
    return {json:JSON.stringify(typeof groundTruthDataset === 'function' ? groundTruthDataset() : groundTruth(), null, 2),complete:true};
  }
};
for (const element of document.querySelectorAll('#connectDatasetBtn,#autosaveStatus,.autosave-separator')) element.hidden = true;
const help = document.getElementById('reviewHelpDialog');
if (help) {
  for (const p of help.querySelectorAll('p')) {
    if (p.textContent.includes('Connect Dataset') || p.textContent.includes('Human changes are saved separately')) {
      p.textContent = 'Text, structure, layout and individual confirmations remain editable. Save HTML in the left sidebar preserves your work, including pending suggestions. Reopen the downloaded file to continue. Saving does not confirm suggestions or mark a document as reviewed.';
    }
  }
}
workshopRestoring = false;
parent.postMessage({type:'workshop-ready'}, '*');
