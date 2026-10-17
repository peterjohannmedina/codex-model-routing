'use strict';
const byId = id => document.getElementById(id);
let csrf = '', formVersion = '', dirty = false, polling = false, loaded = false;
let editRevision = 0, formEpoch = 0, saving = false;
let authorizationRequired = false;
function requireAuthorization() {
  authorizationRequired = true; loaded = false;
  text('connection','Browser authorization required');
  text('message','Reopen Routing desk using its installed shortcut or bootstrap open command. This obtains a fresh one-use browser authorization; no server restart is needed. This tab has stopped polling and its displayed values may be stale.');
  byId('message').className='error';byId('save').disabled=true;byId('reload').disabled=true;
  byId('catalog-refresh').disabled=true;byId('native-managed').disabled=true;
  for(const input of modelInputs.values())input.disabled=true;
}
const fields = {
  decisions: {'enabled':'decisions-enabled','api_key_env':'decisions-key-env','timeout_seconds':'decisions-timeout','minimum_confidence':'decisions-confidence','max_input_tokens':'decision-token-cap','max_cost_usd':'decision-cost-cap'},
  local: {'enabled':'local-enabled','base_url':'local-url','model':'local-model','api_key_env':'local-key-env','efforts':'local-efforts','timeout_seconds':'local-timeout','max_output_tokens':'local-output','allow_remote':'local-remote','prefer_when_eligible':'local-prefer'},
  observability: {'enabled':'ledger-enabled','retention_days':'retention','max_events':'max-events','local_input_usd_per_million':'input-rate','local_output_usd_per_million':'output-rate'}
};
const text = (id, value) => { byId(id).textContent = value; };
const money = value => value === null || value === undefined ? 'Unknown' : '$' + value.toFixed(6);
const number = value => value === null || value === undefined ? 'Unknown' : value.toLocaleString();
const time = value => value ? new Date(value).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'}) : 'Unobserved';
const configHints = {
  invalid_key_environment_name:'Enter an environment-variable name such as OPENAI_API_KEY, not an API key value.',
  missing_key_environment_name:'Enter OPENAI_API_KEY or another environment-variable name; store the key separately.',
  invalid_timeout:'Use a timeout between 0.05 and 10 seconds.',
  invalid_confidence_threshold:'Use a minimum confidence between 0 and 1.',
  invalid_evaluator_token_cap:'Use a non-negative whole number or leave the input-token cap blank.',
  invalid_evaluator_cost_cap:'Use a cost cap between 0 and 1000000 USD or leave it blank.',
  invalid_output_budget:'Use a whole-number output limit between 1 and 4096.',
  invalid_local_efforts:'Use supported effort names, separated by commas, such as default.',
  invalid_local_model:'Use a nonsecret model ID of at most 256 characters.',
  invalid_local_url:'Use an HTTP(S) base URL without credentials, query strings or fragments.',
  sensitive_model_label:'Use a nonsecret model ID; do not include credential-like values.',
  sensitive_endpoint:'Use a nonsecret HTTP(S) base URL without credentials, query strings or fragments.',
  invalid_observability_configuration:'Check history retention (1–30 days), maximum requests (10–5000), and non-negative rates.',
  invalid_config_flag:'Provider and history toggles must be enabled or disabled.'
};
const fieldLabels = {'decisions.api_key_env':'Decisions credential name','local.api_key_env':'Local credential name',
  'decisions.timeout_seconds':'Decisions timeout','local.timeout_seconds':'Local timeout',
  'decisions.minimum_confidence':'Minimum confidence','decisions.max_input_tokens':'Evaluator token cap',
  'decisions.max_cost_usd':'Evaluator cost cap','local.max_output_tokens':'Local output limit','local.efforts':'Local efforts',
  'local.model':'Local model','local.base_url':'Local base URL','observability':'History settings','providers':'Provider settings'};
function saveError(error) {
  if(error.code==='configuration_changed_reload_before_saving')return 'Settings changed in another tab or process. Reload saved settings before retrying.';
  const hint=Object.hasOwn(configHints,error.code)?configHints[error.code]:null;
  const label=Object.hasOwn(fieldLabels,error.field)?fieldLabels[error.field]:'Provider settings';
  return hint?label+': '+hint:'Could not confirm the save. Check provider and history fields; keys are stored separately.';
}
function credentialIssue(config) {
  for(const group of ['decisions','local']) {
    const value=config[group].api_key_env;
    if((group==='decisions'&&value===null)||(value!==null&&!/^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(value)))
      return {code:value===null?'missing_key_environment_name':'invalid_key_environment_name',field:group+'.api_key_env'};
  }
  return null;
}
function showCredentialIssue(issue, node) {
  node.setCustomValidity(configHints[issue.code]);
  node.setAttribute('aria-invalid','true');
  text('save-status',saveError(issue));
}
for(const group of ['decisions','local']) {
  const node=byId(fields[group].api_key_env);
  // Native required/pattern validation runs before submit and does not bubble.
  node.addEventListener('invalid',event=>{
    event.preventDefault();
    showCredentialIssue({code:group==='decisions'&&!node.value.trim()?'missing_key_environment_name':'invalid_key_environment_name',field:group+'.api_key_env'},node);
  });
  node.addEventListener('input',()=>{node.setCustomValidity('');node.setAttribute('aria-invalid','false');});
}
async function api(path, body, bootstrap) {
  const controller = new AbortController(), timeout = setTimeout(()=>controller.abort(),path==='/api/models/refresh'?12000:5000);
  const options = {credentials:'same-origin', cache:'no-store',signal:controller.signal,headers:{'X-Routing-CSRF':csrf}};
  if (body !== undefined) Object.assign(options, {method:'POST',headers:{'Content-Type':'application/json','X-Routing-CSRF':csrf},body:JSON.stringify(body)});
  if (bootstrap) options.headers['X-Routing-Bootstrap']=bootstrap;
  try {
    const response = await fetch(path, options);
    const value = await response.json();
    if (!response.ok) {
      if(path!=='/api/auth'&&response.status===403)requireAuthorization();
      const error=new Error(value.error || 'local_request_failed');error.code=value.error;error.field=value.field;throw error;
    }
    return value;
  } finally {clearTimeout(timeout);}
}
function fill(config, version) {
  for (const [group, items] of Object.entries(fields)) for (const [key,id] of Object.entries(items)) {
    const node = byId(id), value = config[group][key];
    if (node.type === 'checkbox') node.checked = value;
    else node.value = Array.isArray(value) ? value.join(', ') : (value ?? '');
  }
  for(const group of ['decisions','local']) {
    const node=byId(fields[group].api_key_env);node.setCustomValidity('');node.setAttribute('aria-invalid','false');
  }
  formVersion = version; loaded = true; byId('save').disabled = false;
  byId('native-managed').checked=config.native?.allowed_models!==null&&config.native?.allowed_models!==undefined;
  for(const [id,input] of modelInputs)input.checked=(config.native?.allowed_models||[]).includes(id);
  updateNativeControls();
  text('save-status','Saved settings loaded. Keys are stored separately; provider execution requires consent.');
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
  config.native={allowed_models:byId('native-managed').checked?Array.from(modelInputs).filter(([,input])=>input.checked).map(([id])=>id):null};
  return config;
}
let modelInputs=new Map(), catalogSignature=null, catalogBusy=false;
function updateNativeControls(){
  const managed=byId('native-managed').checked;
  for(const input of modelInputs.values())input.disabled=authorizationRequired||!managed||input.unsupported;
  const count=Array.from(modelInputs.values()).filter(input=>input.checked).length;
  text('native-policy-status',managed?(count?count+' selected. Save settings to apply.':'No native models selected. Saving blocks native routing; eligible local routes remain possible.'):'Existing routing policy is unchanged; model checkboxes are inactive.');
}
function renderCatalog(data){
  const catalog=data.model_catalog||{status:'unverified',models:[]};
  text('catalog-status','Codex catalog: '+catalog.status+'. Entitlement and remote freshness remain unverified.'+(catalog.last_error?' Refresh failed; retained choices are historical.':''));
  text('catalog-source',(catalog.source||'No Codex query yet')+' · queried '+time(catalog.queried_at)+(catalog.plan_type?' · reported plan '+catalog.plan_type:'')+(catalog.cache_fetched_at?' · native cache timestamp '+time(catalog.cache_fetched_at):''));
  const saved=data.config.native?.allowed_models;
  const signature=JSON.stringify([catalog.models,saved]);
  if(signature!==catalogSignature){
    const selected=dirty?new Set(Array.from(modelInputs).filter(([,input])=>input.checked).map(([id])=>id)):new Set(saved||[]);
    const models=[...(catalog.models||[])];
    for(const id of selected)if(!models.some(m=>m.id===id))models.push({id,efforts:[],policy_supported:false,missing:true});
    const children=[],next=new Map();
    for(const [index,model] of models.entries()){
      const label=document.createElement('label'),input=document.createElement('input'),description=document.createElement('span');
      input.type='checkbox';input.setAttribute('id','native-model-'+index);input.checked=selected.has(model.id);
      input.unsupported=!model.policy_supported&&!model.missing;
      description.textContent=model.id+' · '+(model.missing?'Unavailable in latest report; cannot route':model.efforts.join(', '))+(!model.policy_supported&&!model.missing?' · unsupported by routing policy':'');
      input.addEventListener('change',()=>{dirty=true;formEpoch++;updateNativeControls();});label.append(input,description);children.push(label);next.set(model.id,input);
    }
    byId('catalog-models').replaceChildren(...children);modelInputs=next;catalogSignature=signature;
  }
  updateNativeControls();byId('catalog-refresh').disabled=catalogBusy||authorizationRequired;
}
function addDetail(list, label, value) {
  const dt=document.createElement('dt'), dd=document.createElement('dd'); dt.textContent=label; dd.textContent=value ?? 'Unknown'; list.append(dt,dd);
}
function renderEvents(events) {
  const holder = byId('events'), current = Array.from(holder.children);
  const existing = new Map(current.filter(row=>row.routingObservationKey).map(row=>[row.routingObservationKey,row]));
  const focused = current.find(row=>row.routingObservationKey && document.activeElement===row.children[0])?.routingObservationKey;
  if (!events.length) {
    const empty=document.createElement('div'); empty.className='empty'; empty.textContent='No instrumented activity in this scope. Connect an explicit router command or Codex exec JSON stream; other sessions remain unobserved.'; holder.replaceChildren(empty); return;
  }
  const next=[], seen=new Set();
  for (const event of events.slice(0,100)) {
    // IDs are stable across polling, enrichment and reordering. Include session
    // and source so two scopes never borrow each other's expansion state.
    let key=[event.source,event.session_id,event.request_id].every(value=>typeof value==='string')?
      JSON.stringify([event.source,event.session_id,event.request_id]):null;
    if(seen.has(key))key=null;
    if(key)seen.add(key);
    const previous=key?existing.get(key):null, data=JSON.stringify(event);
    if(previous?.routingObservationData===data){next.push(previous);continue;}
    const row=document.createElement('details'), summary=document.createElement('summary');
    row.routingObservationKey=key;row.routingObservationData=data;row.open=previous?.open || false;
    const source=event.source==='codex_otel'?'Codex OTel':event.source==='router'?'Router':'Codex exec';
    const status=event.mode==='otel_session'?'Session settings observed':event.mode==='otel_response'?'Model response observed':event.execution_status==='completed'?'Executed · complete':event.execution_status==='started'?'In progress':event.execution_status==='failed'||event.error?'Failed / stopped':'Recommendation';
    const values=[time(event.observed_at), (event.model || 'Model unobserved') + (event.effort ? ' · '+event.effort : ''), source, status];
    values.forEach((value,i)=>{ const span=document.createElement('span'); span.textContent=value; if(i===2)span.className='event-source'; if(i===3)span.className='event-status'; summary.append(span); });
    const list=document.createElement('dl');
    addDetail(list,'Session',event.session_id); addDetail(list,event.source==='codex_otel'?'Observation (derived ID)':'Request',event.request_id);
    addDetail(list,'Session evidence',event.session_source || (event.session_id==='unassigned'?'Unassigned':'Caller-assigned UUID'));
    addDetail(list,'Source / mode',event.source+' / '+(event.mode || 'unknown'));
    if(event.source==='codex_otel'){
      addDetail(list,'Producer version',event.producer_version);
      addDetail(list,'Contract evidence',event.contract_validation==='reviewed_version'?'Source-reviewed version':event.contract_validation==='reviewed_series_schema'?'Reviewed series schema match; exact build semantics unverified':'Not recorded');
    }
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
    row.append(summary,list); next.push(row);
  }
  // Leave unchanged nodes attached: expansion, text selection and keyboard focus
  // survive ordinary polls. Restore summary focus when a real update moves it.
  if(current.length!==next.length || next.some((row,index)=>row!==current[index])){
    holder.replaceChildren(...next);
    if(focused)next.find(row=>row.routingObservationKey===focused)?.children[0].focus({preventScroll:true});
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
  text('coverage-status',(data.config.observability.enabled?'Local recording enabled. ':'Local recording disabled. ')+(data.sessions.length?'Retained session labels: '+data.sessions.length+'. Historical records do not prove an active feed.':'No recorded sessions yet. Connect an instrumented command, exec JSON stream or approved new Codex CLI OTel export.')+' Dashboard connection does not connect sessions.');
  const otel=totals.otel || {sessions:0,responses:0}, receiver=data.otel_receiver;
  text('observed-sessions',number(otel.sessions));text('observed-responses',number(otel.responses));
  text('otel-receiver',receiver?.enabled?'Receiver listening · '+(receiver.accepted_records?'metadata received':'no metadata received'):'Receiver disabled');
  text('otel-summary',otel.sessions+' sessions with retained OTel metadata; '+otel.responses+' model-response observations. '+(otel.responses?'Known input / output tokens: '+number(otel.input_tokens.known)+' / '+number(otel.output_tokens.known)+'; unknown input / output: '+otel.input_tokens.unknown_responses+' / '+otel.output_tokens.unknown_responses+'. ':'No response usage observed. ')+(receiver?.last_received_at?'Last validated batch: '+time(receiver.last_received_at)+'.':'No validated batch in this receiver process.'));
  let diagnostic=!receiver?.enabled?'Start the approved receiver to receive CLI exports.':
    !receiver.runtime_version?'This receiver predates compatibility diagnostics. Update and restart the dashboard receiver through its supported lifecycle before testing new CLI exports; this does not restart Codex.':
    receiver.unsupported_version_records?'Some records use an unsupported CLI version; check compatibility before upgrading the receiver.':
    receiver.missing_version_records?'Session or response records arrived without the required event app.version; the resource version alone does not establish that session contract.':
    receiver.invalid_version_records?'Session or response records have an invalid event app.version field; check the producer schema.':
    receiver.unauthorized_requests?'Some exporter requests failed authorization or Host/origin checks; review the approved endpoint and capability setup.':
    receiver.invalid_batches?'Some exporter requests failed JSON/schema/size checks; use uncompressed OTLP/HTTP JSON.':
    receiver.storage_errors?'Some observations could not be stored; check local state access.':
    receiver.recording_disabled_batches?'Export batches arrived while local recording was disabled; those observations were not stored.':
    receiver.last_received_at&&!receiver.accepted_records?'Export batches arrived, but no supported session or response metadata was accepted.':
    !receiver.last_received_at?'No export batch has reached this receiver. Confirm the producer uses the same Codex home and approved exporter; an already-running producer may retain startup settings.':
    'Metadata has reached this receiver; retained history does not prove that every open session is connected.';
  const count=value=>number(Number.isSafeInteger(value)&&value>=0?value:0);
  if(receiver?.runtime_version)diagnostic+=' Requests / unauthorized / invalid: '+count(receiver?.requests)+' / '+count(receiver?.unauthorized_requests)+' / '+count(receiver?.invalid_batches)+
    '. Accepted / ignored / rejected records: '+count(receiver?.accepted_records)+' / '+count(receiver?.ignored_records)+' / '+count(receiver?.rejected_records)+'.';
  if(receiver?.state_id)diagnostic+=' Local state ID: '+receiver.state_id+'.';
  if(receiver?.runtime_version)diagnostic+=' Runtime: '+receiver.runtime_version+'.';
  if(receiver?.producer_metadata){
    const events=receiver.producer_metadata.events||{};
    diagnostic+=' Producer event classes: session starts '+count(events.session_start)+', response events '+count(events.response_event)+', API requests '+count(events.api_request)+', process events '+count(events.process)+', other '+count(events.other)+', missing event name '+count(events.missing)+'.';
    if(!events.session_start&&!events.response_event&&receiver.last_received_at)diagnostic+=' No session-start or response event has reached this receiver; API/process traffic does not contain response usage.';
    if(events.schema_compatible)diagnostic+=' '+count(events.schema_compatible)+' observations match the reviewed series schema; their exact build semantics remain unverified.';
    const features=receiver.producer_metadata.features||{};
    if(features.unknown_record_fields)diagnostic+=' '+count(features.unknown_record_fields)+' records contain unrecognized top-level fields; names and values were discarded.';
    if(features.top_level_event_name_only)diagnostic+=' '+count(features.top_level_event_name_only)+' records have only a top-level event name, without the reviewed event.name attribute.';
  }
  if(receiver?.running_revision)diagnostic+=' Running revision: '+receiver.running_revision+'.';
  if(receiver?.restart_required===true)diagnostic+=' Installed files differ from this running receiver; reopen through the installed launcher to apply the update.';
  text('otel-diagnostics',diagnostic);
  text('requests',number(totals.requests)); text('executions',number(totals.completed_executions));
  for(const name of ['evaluator','downstream']) {
    const input=totals[name].input_tokens;
    text(name,number(input.known)); text(name+'-unknown',input.unknown_requests+' requests with unknown input usage');
  }
  text('evaluator-cost',money(totals.evaluator_base_cost_estimate_usd));text('local-cost',money(totals.local_cost_estimate_usd));
  text('scope-note',(data.selected_session?'Selected session':'All retained sessions')+' · router commands and JSON collector only');
  const select=byId('session'), current=select.value;
  const all=document.createElement('option');all.value='';all.textContent='All recorded sessions';select.replaceChildren(all);
  for(const session of data.sessions){const option=document.createElement('option');option.value=session;option.textContent=session==='unassigned'?'Unassigned router commands':session;select.append(option);}
  select.value=current;
  for(const name of ['decisions','local']){
    const enabled=data.config[name].enabled, configured=name==='decisions'||Boolean(data.config.local.model&&data.config.local.base_url);
    text(name+'-configured',enabled?(configured?'Enabled · settings only':'Enabled · unconfigured'):'Disabled');byId(name+'-configured').className='pill'+(enabled?'':' off');
    const observed=data.events.find(e=>name==='local'?e.local_status&&e.local_status!=='disabled':e.evaluator_attempts>0||e.fallback_reason==='missing_api_key');
    text(name+'-observed',observed?'Last observation: '+(name==='local'?observed.local_status:observed.fallback_reason||'response received')+' · '+time(observed.observed_at)+' (historical)':'Last observation: unobserved');
  }
  if(!dirty&&!saving&&formFresh)fill(data.config,data.config_version);
  renderCatalog(data);renderEvents(data.events);renderChart(data.daily);
  text('updated','Refreshed '+time(data.observed_at)+' · local observation time');text('connection','Dashboard connected · 2s');
}
async function refresh(){
  if(polling||authorizationRequired)return;polling=true;
  const pollEpoch=formEpoch;
  try{const data=await api('/api/state'+(byId('session').value?'?session='+encodeURIComponent(byId('session').value):''));if(authorizationRequired)return;render(data,pollEpoch===formEpoch);text('message','');}
  catch(error){if(!authorizationRequired){text('connection','Disconnected');text('message','Local data unavailable: '+error.message+'. The last displayed values may be stale.');byId('message').className='error';}}
  finally{polling=false;}
}
byId('config-form').addEventListener('input',()=>{editRevision++;dirty=true;text('save-status','Unsaved changes. Live observations continue.');});
byId('config-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!loaded||saving)return;
  const submittedRevision=editRevision, snapshot=readForm(), version=formVersion;
  const issue=credentialIssue(snapshot);
  for(const id of ['decisions-key-env','local-key-env'])byId(id).setAttribute('aria-invalid','false');
  if(issue){showCredentialIssue(issue,byId(issue.field==='decisions.api_key_env'?'decisions-key-env':'local-key-env'));return;}
  saving=true;formEpoch++;byId('save').disabled=true;byId('reload').disabled=true;
  try{
    const saved=await api('/api/config',{config:snapshot,version});
    formEpoch++; // Polls begun during the pending save also contain pre-save state.
    if(saved.config_version)formVersion=saved.config_version;
    dirty=editRevision!==submittedRevision;
    await refresh();
    dirty=editRevision!==submittedRevision;
    text('save-status',dirty?'Saved earlier snapshot; newer edits remain unsaved.':'Settings saved locally. No key was stored or checked. No provider request was made.');
  }
  catch(error){text('save-status',saveError(error));}
  finally{saving=false;byId('save').disabled=!loaded;byId('reload').disabled=authorizationRequired;}
});
byId('reload').addEventListener('click',()=>{if(saving)return;formEpoch++;dirty=false;refresh();});
byId('native-managed').addEventListener('change',()=>{dirty=true;formEpoch++;updateNativeControls();});
byId('catalog-refresh').addEventListener('click',async()=>{
  if(catalogBusy||authorizationRequired)return;
  catalogBusy=true;byId('catalog-refresh').disabled=true;
  text('catalog-status','Reading the signed-in Codex account and picker catalog. No model turn is started.');
  try{await api('/api/models/refresh',{});await refresh();}
  catch(error){text('catalog-status',authorizationRequired?'Reopen the dashboard to authorize this tab.':'Catalog refresh failed. Existing data may be stale; no routing choices were changed.');}
  finally{catalogBusy=false;byId('catalog-refresh').disabled=authorizationRequired;}
});
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
}catch(error){if(error.code==='local_browser_authorization_required'||authorizationRequired)requireAuthorization();else{text('connection','Disconnected');text('message','Local connection unavailable. Reopen Routing desk using its installed shortcut or bootstrap open command.');}}
setInterval(()=>{if(!document.hidden&&!authorizationRequired)refresh();},2000);})();
