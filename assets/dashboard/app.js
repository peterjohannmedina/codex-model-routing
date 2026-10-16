'use strict';
const byId = id => document.getElementById(id);
let csrf = '', formVersion = '', dirty = false, polling = false, loaded = false;
let editRevision = 0, formEpoch = 0, saving = false;
const fields = {
  decisions: {'enabled':'decisions-enabled','api_key_env':'decisions-key-env','timeout_seconds':'decisions-timeout','minimum_confidence':'decisions-confidence','max_input_tokens':'decision-token-cap','max_cost_usd':'decision-cost-cap'},
  local: {'enabled':'local-enabled','base_url':'local-url','model':'local-model','api_key_env':'local-key-env','efforts':'local-efforts','timeout_seconds':'local-timeout','max_output_tokens':'local-output','allow_remote':'local-remote','prefer_when_eligible':'local-prefer'},
  observability: {'enabled':'ledger-enabled','retention_days':'retention','max_events':'max-events','local_input_usd_per_million':'input-rate','local_output_usd_per_million':'output-rate'}
};
const text = (id, value) => { byId(id).textContent = value; };
const money = value => value === null || value === undefined ? 'Unknown' : '$' + value.toFixed(6);
const number = value => value === null || value === undefined ? 'Unknown' : value.toLocaleString();
const time = value => value ? new Date(value).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'}) : 'Unobserved';
async function api(path, body, bootstrap) {
  const controller = new AbortController(), timeout = setTimeout(()=>controller.abort(),5000);
  const options = {credentials:'same-origin', cache:'no-store',signal:controller.signal,headers:{'X-Routing-CSRF':csrf}};
  if (body !== undefined) Object.assign(options, {method:'POST',headers:{'Content-Type':'application/json','X-Routing-CSRF':csrf},body:JSON.stringify(body)});
  if (bootstrap) options.headers['X-Routing-Bootstrap']=bootstrap;
  try {
    const response = await fetch(path, options);
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'local_request_failed');
    return value;
  } finally {clearTimeout(timeout);}
}
function fill(config, version) {
  for (const [group, items] of Object.entries(fields)) for (const [key,id] of Object.entries(items)) {
    const node = byId(id), value = config[group][key];
    if (node.type === 'checkbox') node.checked = value;
    else node.value = Array.isArray(value) ? value.join(', ') : (value ?? '');
  }
  formVersion = version; loaded = true; byId('save').disabled = false;
  text('save-status','Saved settings loaded. Provider execution requires separate consent.');
}
function readForm() {
  const config = {schema_version:1};
  for (const [group, items] of Object.entries(fields)) {
    config[group] = {};
    for (const [key,id] of Object.entries(items)) {
      const node = byId(id);
      config[group][key] = node.type === 'checkbox' ? node.checked : node.type === 'number' ? (node.value === '' ? null : Number(node.value)) : key === 'efforts' ? node.value.split(',').map(s=>s.trim()).filter(Boolean) : node.value.trim() || null;
    }
  }
  return config;
}
function addDetail(list, label, value) {
  const dt=document.createElement('dt'), dd=document.createElement('dd'); dt.textContent=label; dd.textContent=value ?? 'Unknown'; list.append(dt,dd);
}
function renderEvents(events) {
  const holder = byId('events'); holder.replaceChildren();
  if (!events.length) {
    const empty=document.createElement('div'); empty.className='empty'; empty.textContent='No instrumented activity in this scope. Connect an explicit router command or Codex exec JSON stream; other sessions remain unobserved.'; holder.append(empty); return;
  }
  for (const event of events.slice(0,100)) {
    const row=document.createElement('details'), summary=document.createElement('summary');
    const source=event.source==='codex_otel'?'Codex OTel':event.source==='router'?'Router':'Codex exec';
    const status=event.mode==='otel_session'?'Session settings observed':event.mode==='otel_response'?'Model response observed':event.execution_status==='completed'?'Executed · complete':event.execution_status==='started'?'In progress':event.execution_status==='failed'||event.error?'Failed / stopped':'Recommendation';
    const values=[time(event.observed_at), (event.model || 'Model unobserved') + (event.effort ? ' · '+event.effort : ''), source, status];
    values.forEach((value,i)=>{ const span=document.createElement('span'); span.textContent=value; if(i===2)span.className='event-source'; if(i===3)span.className='event-status'; summary.append(span); });
    const list=document.createElement('dl');
    addDetail(list,'Session',event.session_id); addDetail(list,event.source==='codex_otel'?'Observation (derived ID)':'Request',event.request_id);
    addDetail(list,'Session evidence',event.session_source || (event.session_id==='unassigned'?'Unassigned':'Caller-assigned UUID'));
    addDetail(list,'Source / mode',event.source+' / '+(event.mode || 'unknown'));
    addDetail(list,'Model evidence',event.model_source); addDetail(list,'Execution',event.execution_status);
    addDetail(list,'Execution request model / effort',(event.execution_model || 'Unobserved')+' / '+(event.execution_effort || 'Unobserved'));
    addDetail(list,'Collector stream',event.stream_status || 'Not a collected stream');
    addDetail(list,'Override model / effort',(event.override_model || 'Automatic')+' / '+(event.override_effort || 'Automatic'));
    addDetail(list,'Fallback / error',event.fallback_reason || event.error || 'None recorded');
    addDetail(list,'Local observation',event.local_status || 'Unobserved');
    addDetail(list,'Evaluator attempts',number(event.evaluator_attempts));
    addDetail(list,'Evaluator input / output',number(event.evaluator_usage?.input_tokens)+' / '+number(event.evaluator_usage?.output_tokens));
    addDetail(list,'Downstream attempts',number(event.downstream_attempts));
    addDetail(list,'Downstream input / output',number(event.downstream_usage?.input_tokens)+' / '+number(event.downstream_usage?.output_tokens));
    addDetail(list,'Command items',number(event.command_items));
    addDetail(list,'Observed / source timestamp',event.observed_at+' / '+(event.source_timestamp || 'Source timestamp unavailable'));
    row.append(summary,list); holder.append(row);
  }
}
function renderChart(days) {
  const chart=byId('chart'); chart.replaceChildren();
  const selected=days.slice(-14), max=Math.max(1,...selected.map(d=>d.requests));
  selected.forEach((day,index)=>{
    const width=660/Math.max(1,selected.length), height=day.requests/max*80;
    const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');
    for(const [key,value] of Object.entries({x:20+index*width,y:90-height,width:Math.max(3,width-12),height,rx:4,class:'chart-bar'}))rect.setAttribute(key,String(value));
    const title=document.createElementNS(rect.namespaceURI,'title'); title.textContent=day.day+': '+day.requests+' requests; '+day.completed_executions+' completions'; rect.append(title);
    const label=document.createElementNS(rect.namespaceURI,'text');label.setAttribute('x',String(20+index*width));label.setAttribute('y','110');label.setAttribute('class','chart-label');label.textContent=day.day.slice(5);chart.append(rect,label);
  });
  text('daily-summary',selected.length ? selected.map(d=>d.day+': '+d.requests+' requests / '+d.completed_executions+' completed').join(' · ') : 'No retained activity yet.');
}
function render(data, formFresh = true) {
  const totals=data.totals;
  const otel=totals.otel || {sessions:0,responses:0}, receiver=data.otel_receiver;
  text('otel-receiver',receiver?.enabled?'Receiver enabled · exporter configuration unverified':'Receiver disabled');
  text('otel-summary',otel.sessions+' sessions with retained OTel metadata; '+otel.responses+' model-response observations. '+(otel.responses?'Known input / output tokens: '+number(otel.input_tokens.known)+' / '+number(otel.output_tokens.known)+'; unknown input / output: '+otel.input_tokens.unknown_responses+' / '+otel.output_tokens.unknown_responses+'. ':'No response usage observed. ')+(receiver?.last_received_at?'Last accepted batch: '+time(receiver.last_received_at)+'.':'No accepted batch in this receiver process.'));
  text('requests',number(totals.requests)); text('executions',number(totals.completed_executions));
  for(const name of ['evaluator','downstream']) {
    const input=totals[name].input_tokens;
    text(name,number(input.known)); text(name+'-unknown',input.unknown_requests+' requests with unknown input usage');
  }
  text('evaluator-cost',money(totals.evaluator_base_cost_estimate_usd));text('local-cost',money(totals.local_cost_estimate_usd));
  text('scope-note',data.selected_session ? 'Selected session · retained history' : data.sessions.length+' recorded sessions · retained history');
  const select=byId('session'), current=select.value;
  const all=document.createElement('option');all.value='';all.textContent='All instrumented sessions';select.replaceChildren(all);
  for(const session of data.sessions){const option=document.createElement('option');option.value=session;option.textContent=session==='unassigned'?'Unassigned router commands':session;select.append(option);}
  select.value=current;
  for(const name of ['decisions','local']){
    const enabled=data.config[name].enabled, configured=name==='decisions'||Boolean(data.config.local.model&&data.config.local.base_url);
    text(name+'-configured',enabled?(configured?'Enabled · configured':'Enabled · unconfigured'):'Disabled');byId(name+'-configured').className='pill'+(enabled?'':' off');
    const observed=data.events.find(e=>name==='local'?e.local_status&&e.local_status!=='disabled':e.evaluator_attempts>0||e.fallback_reason==='missing_api_key');
    text(name+'-observed',observed?'Last observation: '+(name==='local'?observed.local_status:observed.fallback_reason||'response received')+' · '+time(observed.observed_at)+' (historical)':'Last observation: unobserved');
  }
  if(!dirty&&!saving&&formFresh)fill(data.config,data.config_version);
  renderEvents(data.events);renderChart(data.daily);
  text('updated','Refreshed '+time(data.observed_at)+' · local observation time');text('connection','Dashboard live · 2s');
}
async function refresh(){
  if(polling)return;polling=true;
  const pollEpoch=formEpoch;
  try{const data=await api('/api/state'+(byId('session').value?'?session='+encodeURIComponent(byId('session').value):''));render(data,pollEpoch===formEpoch);text('message','');}
  catch(error){text('connection','Disconnected');text('message','Local data unavailable: '+error.message+'. The last displayed values may be stale.');byId('message').className='error';}
  finally{polling=false;}
}
byId('config-form').addEventListener('input',()=>{editRevision++;dirty=true;text('save-status','Unsaved changes. Live observations continue.');});
byId('config-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!loaded||saving)return;
  const submittedRevision=editRevision, snapshot=readForm(), version=formVersion;
  saving=true;formEpoch++;byId('save').disabled=true;byId('reload').disabled=true;
  try{
    const saved=await api('/api/config',{config:snapshot,version});
    formEpoch++; // Polls begun during the pending save also contain pre-save state.
    if(saved.config_version)formVersion=saved.config_version;
    dirty=editRevision!==submittedRevision;
    await refresh();
    dirty=editRevision!==submittedRevision;
    text('save-status',dirty?'Saved earlier snapshot; newer edits remain unsaved.':'Saved locally. No provider request was made.');
  }
  catch(error){text('save-status','Save failed: '+error.message+'. Reload saved settings before retrying if another writer changed them.');}
  finally{saving=false;byId('save').disabled=false;byId('reload').disabled=false;}
});
byId('reload').addEventListener('click',()=>{if(saving)return;formEpoch++;dirty=false;refresh();});
byId('session').addEventListener('change',refresh);
byId('clear').addEventListener('click',async()=>{if(!confirm('Delete retained local usage metadata? This does not change provider settings or erase filesystem backups.'))return;try{await api('/api/ledger/clear',{confirm:true});await refresh();}catch(error){text('message','Could not clear history: '+error.message);}});
(async()=>{try{
  csrf=sessionStorage.getItem('routing-csrf') || '';
  const prefix='#authorize=';
  if(location.hash.startsWith(prefix)){
    try{const authorization=await api('/api/auth',{},location.hash.slice(prefix.length));csrf=authorization.csrf;sessionStorage.setItem('routing-csrf',csrf);}
    catch(error){if(!csrf)throw error;}
    finally{history.replaceState(null,'',location.pathname);}
  }
  csrf=(await api('/api/session')).csrf;await refresh();
}catch(error){text('message','Open the private one-use launch file from the server terminal to authorize this browser. Restart the server if the file expired.');}
setInterval(()=>{if(!document.hidden)refresh();},2000);})();
