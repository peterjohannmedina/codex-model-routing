// Focused asynchronous save and authorized-navigation regressions. No network.
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const script=fs.readFileSync(path.join(root,'assets/dashboard/app.js'),'utf8');
const html=fs.readFileSync(path.join(root,'assets/dashboard/index.html'),'utf8');
class Element{
  constructor(type=''){this.type=type;this.value='';this.checked=false;this.children=[];this.listeners={};this.textContent='';}
  append(...items){this.children.push(...items);}replaceChildren(...items){this.children=items;}
  setAttribute(){}addEventListener(kind,fn){this.listeners[kind]=fn;}
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function boot(hash,delaySave=false){
  const nodes={},calls=[],historyChanges=[];
  for(const match of html.matchAll(/<([a-z]+)\b([^>]*\bid="([^"]+)"[^>]*)>/g))nodes[match[3]]=new Element(/\btype="([^"]+)"/.exec(match[2])?.[1]||'');
  let snapshot={config:JSON.parse(fs.readFileSync(path.join(root,'assets/routing-config.example.json'),'utf8')),config_version:'base',events:[],sessions:[],daily:[],observed_at:'2026-10-15T22:00:00Z',totals:{requests:0,completed_executions:0,evaluator:{input_tokens:{known:0,unknown_requests:0}},downstream:{input_tokens:{known:0,unknown_requests:0}},evaluator_base_cost_estimate_usd:null,local_cost_estimate_usd:null}};
  let interval, release, saves=0, nextStateGate=null;
  const gate=new Promise(resolve=>{release=resolve;});
  const storage=new Map([['routing-csrf','fixture-capability']]);
  const fetch=async(url,options)=>{
    calls.push({url,options});
    if(url==='/api/auth')throw new Error('navigation_anchor_sent_as_bootstrap');
    assert.equal(options.headers['X-Routing-CSRF'],'fixture-capability');
    if(url==='/api/session')return{ok:true,json:async()=>({csrf:'fixture-capability'})};
    if(url==='/api/state'){
      const captured=structuredClone(snapshot), delayed=nextStateGate;nextStateGate=null;
      if(delayed)await delayed;
      return{ok:true,json:async()=>captured};
    }
    assert.equal(url,'/api/config');const body=JSON.parse(options.body);
    if(delaySave&&saves===0)await gate;
    saves++;snapshot.config=body.config;snapshot.config_version='saved-'+saves;
    return{ok:true,json:async()=>({saved:true,config_version:snapshot.config_version})};
  };
  const context=vm.createContext({document:{hidden:false,getElementById:id=>nodes[id],createElement:()=>new Element(),createElementNS:()=>new Element()},location:{hash,pathname:'/'},history:{replaceState:(_a,_b,value)=>historyChanges.push(value)},sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},fetch,AbortController,setTimeout,clearTimeout,setInterval:fn=>{interval=fn;},confirm:()=>false});
  vm.runInContext(script,context);
  return{nodes,calls,historyChanges,release,poll:()=>interval(),snapshot:()=>snapshot,
    holdNextPoll:()=>{let resume;nextStateGate=new Promise(resolve=>{resume=resolve;});return resume;}};
}
async function anchors(){
  for(const hash of ['#providers','#activity','#overview']){
    const ui=boot(hash);await flush();await flush();
    assert.equal(ui.calls.filter(c=>c.url==='/api/auth').length,0,'navigation was treated as bootstrap');
    assert.equal(ui.nodes.requests.textContent,'0','stored authorized session was not recovered');
    assert.equal(ui.historyChanges.length,0,'navigation anchor was discarded');
    ui.poll();await flush();assert.match(ui.nodes.connection.textContent,/Dashboard live/);
  }
  const expired=boot('#authorize=expired-nonce');await flush();await flush();
  assert.equal(expired.nodes.requests.textContent,'0','failed bootstrap discarded a valid stored capability');
  assert.equal(expired.historyChanges.length,1);
}
async function delayedSave(){
  const ui=boot('',true);await flush();await flush();
  ui.nodes['local-model'].value='first-snapshot';ui.nodes['config-form'].listeners.input();
  const pending=ui.nodes['config-form'].listeners.submit({preventDefault(){}});
  await flush();
  ui.nodes['local-model'].value='newer-unsaved-edit';ui.nodes['config-form'].listeners.input();
  ui.poll();await flush();
  ui.release();await pending;await flush();
  assert.equal(ui.nodes['local-model'].value,'newer-unsaved-edit','save response clobbered a newer edit');
  assert.match(ui.nodes['save-status'].textContent,/newer.*unsaved/i);
  assert.equal(ui.snapshot().config.local.model,'first-snapshot','first POST was not a snapshot');
  await ui.nodes['config-form'].listeners.submit({preventDefault(){}});
  const posts=ui.calls.filter(c=>c.url==='/api/config');
  assert.equal(JSON.parse(posts[1].options.body).version,'saved-1','next edit used a stale saved version');
  assert.equal(ui.snapshot().config.local.model,'newer-unsaved-edit');
}
async function stalePoll(){
  const ui=boot('',true);await flush();await flush();
  ui.nodes['local-model'].value='saved-before-old-get';ui.nodes['config-form'].listeners.input();
  const pending=ui.nodes['config-form'].listeners.submit({preventDefault(){}});await flush();
  const resumePoll=ui.holdNextPoll();ui.poll();await flush();
  ui.release();await pending;
  assert.equal(ui.nodes['local-model'].value,'saved-before-old-get');
  resumePoll();await flush();await flush();
  assert.equal(ui.nodes['local-model'].value,'saved-before-old-get','old GET restored the pre-save form after POST completion');
  ui.nodes['local-model'].value='next-edit';ui.nodes['config-form'].listeners.input();
  await ui.nodes['config-form'].listeners.submit({preventDefault(){}});
  const posts=ui.calls.filter(c=>c.url==='/api/config');
  assert.equal(JSON.parse(posts[1].options.body).version,'saved-1','old GET restored the pre-save version');
}
(async()=>{const selected=process.argv[2];if(!selected||selected==='anchors')await anchors();if(!selected||selected==='save')await delayedSave();if(!selected||selected==='poll')await stalePoll();console.log('Dashboard navigation, delayed-save and stale-poll regressions pass.');})().catch(error=>{console.error(error);process.exitCode=1;});
