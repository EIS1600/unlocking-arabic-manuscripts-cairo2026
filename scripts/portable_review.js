/* Workshop-only session controller. Build with python scripts/build_portable_review.py. */
'use strict';
const pristine = '<!doctype html>\n' + document.documentElement.outerHTML;
const resources = JSON.parse(document.getElementById('workshop-resources').textContent);
const state = JSON.parse(document.getElementById('workshop-state').textContent);
const viewer = document.getElementById('viewer'), nav = document.getElementById('documents');
const status = document.getElementById('status'), saveButton = document.getElementById('save');
let active = null, ready = false, dirty = false, busy = false;
let selection = 0;
const documents = resources.documents;
const loads = new Map();
window.workshopDocumentLoaded = (digest, html) => {
  const doc=documents.find(item=>item.digest===digest);
  if(doc && typeof html==='string')doc.html=html;
};
function ensureDocument(doc) {
  if(typeof doc.html==='string')return Promise.resolve(doc.html);
  if(loads.has(doc.id))return loads.get(doc.id);
  const promise=new Promise((resolve,reject)=>{
    const script=document.createElement('script');
    const timer=setTimeout(()=>finish(Error('Loading timed out. Select the document again to retry.')),120000);
    function finish(error){clearTimeout(timer);script.remove();if(error){loads.delete(doc.id);reject(error);}else resolve(doc.html);}
    script.onload=()=>finish(typeof doc.html==='string'?null:Error('Document data was not returned.'));
    script.onerror=()=>finish(Error('Could not load document. Check the connection and select it again.'));
    script.src=doc.url;document.head.append(script);
  });
  loads.set(doc.id,promise);return promise;
}
if (state.schema !== 'cairo_workshop_session' || state.version !== 1 || state.bundle !== resources.id) throw Error('Incompatible workshop session.');
function message(text, error=false) {status.textContent=text;status.dataset.error=String(error);}
function changed() {dirty=true;message('Unsaved changes — click Save HTML before closing.');}
window.workshopChanged = source => {if(source===viewer.contentWindow && ready)changed();};
function capture() {
  if (active && ready) state.drafts[active.id] = viewer.contentWindow.workshopReview.capture();
}
async function selectDocument(id) {
  if (busy) return;
  capture();
  const next = documents.find(doc => doc.id === id);
  if (!next) throw Error('Unknown document.');
  active=next;ready=false;state.active=id;
  const ticket=++selection;
  saveButton.disabled=true;viewer.srcdoc='';
  message('Loading '+next.label+'…');
  for (const link of nav.querySelectorAll('[data-document]')) {
    link.setAttribute('aria-current',String(link.dataset.document===id));
    link.classList.toggle('active',link.dataset.document===id);
  }
  try {
    const html=await ensureDocument(next);
    if(ticket===selection)viewer.srcdoc=html;
  }catch(error){if(ticket===selection)message(error.message,true);}
}
for (const kind of ['metadata','ocr']) {
  const group=documents.filter(doc=>doc.kind===kind);
  if (!group.length) continue;
  const title=document.createElement('h2');title.textContent=kind==='metadata'?'Metadata':'OCR';nav.append(title);
  const list=document.createElement(kind==='ocr'?'ol':'div');list.className='review-list';nav.append(list);
  for (const doc of group) {
    const link=document.createElement('a');link.href='#';link.className='review-link '+(doc.status_class||'');link.title=doc.status_text||'';link.textContent=doc.label;link.dataset.document=doc.id;
    link.addEventListener('click',event=>{event.preventDefault();selectDocument(doc.id);});
    if(kind==='ocr'){const li=document.createElement('li');li.append(link);list.append(li);}else list.append(link);
  }
}
window.addEventListener('message',event=>{
  if(event.source!==viewer.contentWindow)return;
  if(event.data?.type==='workshop-ready') {
    if(!viewer.contentWindow.workshopReview)return;
    try {
      viewer.contentWindow.workshopReview.restore(state.drafts[active.id]);
      ready=true;saveButton.disabled=false;
      if (!dirty) message(state.saved_at?'Saved HTML opened. Further edits need another Save HTML.':'No autosave. Use Save HTML before closing.');
    } catch(error){message('Could not restore this document: '+error.message,true);}
  } else if(event.data?.type==='workshop-dirty' && ready) changed();
  else if(event.data?.type==='openiti-export-ocr-dataset-json') exportAll('json');
  else if(event.data?.type==='openiti-export-ocr-dataset-markdown') exportAll('md');
});
function safeJson(value) {return JSON.stringify(value).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');}
function savedHtml() {
  if (!ready) throw Error('Wait for the document to finish loading.');
  capture();state.saved_at=new Date().toISOString();
  function replaceData(html,id,value){
    const opening='<script id="'+id+'" type="application/json">';
    const start=html.indexOf(opening)+opening.length,end=html.indexOf('<'+'/script>',start);
    if(start<opening.length||end<start)throw Error('Missing session container.');
    return html.slice(0,start)+safeJson(value)+html.slice(end);
  }
  const embedded={...resources,documents:documents.map(doc=>{
    if(typeof doc.html!=='string')throw Error('Some documents have not downloaded yet.');
    const {url,digest,...inline}=doc;return inline;
  })};
  return replaceData(replaceData(pristine,'workshop-resources',embedded),'workshop-state',state);
}
function download(content,name,type) {
  const url=URL.createObjectURL(new Blob([content],{type})),link=document.createElement('a');
  link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
}
saveButton.addEventListener('click',async()=>{
  if(busy||!ready)return;
  busy=true;saveButton.disabled=true;
  try {
    for(const [index,doc] of documents.entries()){
      message('Preparing offline HTML: document '+(index+1)+' of '+documents.length+'…');
      await ensureDocument(doc);
    }
    download(savedHtml(),resources.filename.replace(/\.html$/,'')+'-saved.html','text/html;charset=utf-8');
    dirty=false;message('HTML download requested. Check that it finished; reopen that downloaded file to continue.');
  } catch(error){message('Save failed: '+error.message+' Your edits remain in this open page.',true);}
  finally{busy=false;saveButton.disabled=!ready;}
});
async function loadForExport(doc) {
  if(active?.id===doc.id && ready)return {api:viewer.contentWindow.workshopReview,dispose(){}};
  const html=await ensureDocument(doc);
  const frame=document.createElement('iframe');frame.hidden=true;document.body.append(frame);
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>finish(Error('Timed out loading '+doc.label)),30000);
    function finish(error) {clearTimeout(timer);window.removeEventListener('message',receive);if(error){frame.remove();reject(error);}}
    function receive(event) {
      if(event.source!==frame.contentWindow||event.data?.type!=='workshop-ready')return;
      try {const api=frame.contentWindow.workshopReview;api.restore(state.drafts[doc.id]);finish();resolve({api,dispose:()=>frame.remove()});}
      catch(error){finish(error);}
    }
    window.addEventListener('message',receive);frame.srcdoc=html;
  });
}
async function exportAll(format) {
  if(busy||!ready)return;
  capture();busy=true;saveButton.disabled=true;
  try {
    const results=[];
    for(const doc of documents.filter(doc=>doc.kind==='ocr')) {
      const loaded=await loadForExport(doc);
      try {results.push({doc,result:loaded.api.exportData(format)});}finally{loaded.dispose();}
    }
    if(results.some(item=>!item.result.complete) && !confirm('Some documents have unresolved readings, pending suggestions or layout issues. Export incomplete results anyway?'))return;
    const content=format==='json'?JSON.stringify({schema:'openiti_ocr_ground_truth_dataset',schema_version:1,documents:results.map(item=>JSON.parse(item.result.json))},null,2):results.map(item=>'<!-- '+item.doc.label.replace(/--/g,'—')+' -->\n'+item.result.markdown).join('\n\n');
    download(content,'workshop-transcriptions.'+format,format==='json'?'application/json':'text/markdown');
  }catch(error){message('Export failed: '+error.message,true);}
  finally{busy=false;saveButton.disabled=false;}
}
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
const layout=document.querySelector('.layout'),handle=document.getElementById('splitHandle'),toggle=document.getElementById('sidebarToggleBtn');
let fontSize=16;
for(const [id,delta] of [['shellFontSmallerBtn',-1],['shellFontLargerBtn',1]])document.getElementById(id).onclick=()=>{
  fontSize=Math.max(12,Math.min(24,fontSize+delta));document.body.style.setProperty('--review-font-size',fontSize+'px');
};
toggle.onclick=()=>{
  const collapsed=document.body.classList.toggle('sidebar-collapsed');toggle.textContent=collapsed?'›':'‹';
  toggle.setAttribute('aria-expanded',String(!collapsed));toggle.title=collapsed?'Expand file list':'Collapse file list';toggle.setAttribute('aria-label',toggle.title);
};
function resizeSidebar(width){layout.style.setProperty('--sidebar-width',Math.max(120,Math.min(window.innerWidth-200,width))+'px');}
handle.addEventListener('pointerdown',event=>{
  if(event.target===toggle||document.body.classList.contains('sidebar-collapsed'))return;
  handle.setPointerCapture(event.pointerId);handle.classList.add('active');event.preventDefault();
});
handle.addEventListener('pointermove',event=>{if(handle.hasPointerCapture(event.pointerId))resizeSidebar(event.clientX);});
handle.addEventListener('pointerup',event=>{if(handle.hasPointerCapture(event.pointerId))handle.releasePointerCapture(event.pointerId);handle.classList.remove('active');});
handle.addEventListener('keydown',event=>{if(event.target!==handle||!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();resizeSidebar(document.getElementById('reviewSidebar').offsetWidth+(event.key==='ArrowRight'?20:-20));});
selectDocument(state.active || documents[0].id);
