/** Real Director editor and workbench in a browser; Comfy queue/cache are host fixtures. */
import { createRequire } from 'node:module';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', req.url.endsWith('.js') ? 'text/javascript' : 'text/html');
  if (req.url === '/scripts/app.js') return res.end(`export const app={graph:{_nodes:[],links:{},setDirtyCanvas(){}},canvas:{ds:{scale:1},setDirty(){}},registerExtension(x){(globalThis.extensions||=[]).push(x)},async queuePrompt(){globalThis.queued=(globalThis.queued||0)+1}};`);
  if (req.url === '/scripts/api.js') return res.end(`export const api=new EventTarget();api.fetchApi=async()=>new Response('{}');`);
  if (req.url.startsWith('/web/js/')) {
    try {
      const filename = path.resolve(root, '.' + req.url);
      if (!filename.startsWith(root + path.sep)) throw new Error('Invalid path');
      let source = await fs.readFile(filename, 'utf8');
      if (req.url === '/web/js/minimax_timeline.js') source += '\nexport {CineStackH3DirectorEditor, parseTimeline};';
      return res.end(source);
    } catch { res.statusCode = 404; return res.end(); }
  }
  res.end('<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:20px;font:14px system-ui;background:#101613;color:#e6eee9}h1{font-size:18px;margin:0 0 6px}p{font-size:12px;color:#b7c5bd;margin:0 0 14px}.cstk-host{width:100%;height:1250px}</style><h1>影栈 H3 导演台</h1><p>真实前端 · ComfyUI 宿主模拟 · 未运行模型</p><main class="cstk-host"></main>');
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await chromium.launch({headless:true, ...(process.env.CHROME_BIN ? {executablePath:process.env.CHROME_BIN} : {})});
  const page = await browser.newPage({viewport:{width:1380,height:1100}});
  const errors=[]; page.on('pageerror', error=>errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.evaluate(async () => {
    const {app}=await import('/scripts/app.js'); const {api}=await import('/scripts/api.js');
    const {setLocale}=await import('/web/js/minimax_i18n.js'); setLocale('zh');
    const {CineStackH3DirectorEditor}=await import('/web/js/minimax_timeline.js');
    const task='r2v — 参考主体生视频(Reference to Video)';
    const timeline={version:5,timelineMode:'prompt_batch',editMode:'segment',frameRate:24,
      global:{taskType:task,prompt:'',refs:[],commonEnabled:false},
      output:{mode:'fixed',width:864,height:480,megapixels:.4,aspectRatio:'16:9 (宽屏)',audioMode:'generate',exportMode:'all',continuityEnabled:false},
      segments:Array.from({length:5},(_,i)=>({id:`shot-${i}`,start:i*124,length:124,frameCount:124,durationSec:5,
        prompt:`[Shot 1] 镜头 ${i+1}：人物走入场景，保持参考人物身份。\n\n整体音景：脚步与环境声。`,refs:[],refAudios:[],refVideos:[],loras:[],
        first_pass_seed:i===2?'200':i===3?'18446744073709551615':null}))};
    const values={task_type:task,global_prompt:'',timeline_data:JSON.stringify(timeline),frame_rate:24,total_frames:620,width:864,height:480,ref_max_size:864,
      seed:100,cfg:1,steps:4,sampler:'res_multistep',scheduler:'simple',shift_video:12,shift_audio:3,cache_name:'',cache_frames_codec:'raw'};
    const node={id:56,type:'CineStackH3Director',comfyClass:'CineStackH3Director',mode:0,size:[1340,1600],flags:{},
      inputs:[{name:'refine',link:1}],widgets:Object.entries(values).map(([name,value])=>({name,value,options:{values:name==='task_type'?[task,'t2v — 文生视频(Text to Video)','fl2v — 首尾帧生视频(First Last Frame to Video)']:[]}})),
      setDirtyCanvas(){},setSize(size){this.size=size},computeSize(){return this.size}};
    const refine={id:39,type:'CineStackH3DirectorRefine',mode:0,inputs:[{name:'sigmas',link:2}],widgets:[{name:'mode',value:'refine'},{name:'skip_fl2v',value:false},{name:'refine_only',value:false},{name:'confirm_first_pass',value:true},{name:'sampler',value:'euler'}]};
    app.graph._nodes=[node,refine]; app.graph.links={1:{origin_id:39},2:{origin_id:33}}; node.graph=app.graph; refine.graph=app.graph;
    globalThis.forceMatch=false;globalThis.posts=[];
    api.fetchApi=async(url,options)=>{
      if (!url.includes('first_pass_cache_status')) return new Response('{}');
      const payload=JSON.parse(options.body); globalThis.posts.push(payload);
      const data=JSON.parse(payload.timeline_data);
      const selected=data.runSelectEnabled?data.runSelection:data.segments.map((_,i)=>i);
      const segments=data.segments.map((row,i)=>({segment:i+1,exists:i!==4||forceMatch,matches:forceMatch||i<2||i===3,selected:selected.includes(i),
        expected_seed_text:String(row.first_pass_seed??payload.seed),cached_seed_text:i===4&&!forceMatch?null:String(i===2&&!forceMatch?100:row.first_pass_seed??payload.seed),
        diff_keys:forceMatch||i<2||i===3?[]:[i===4?'<missing-cache>':'seed'],final_exists:i<2}));
      return new Response(JSON.stringify({segments,segment_total:5,matched_count:segments.filter(r=>r.matches).length,
        can_confirm_refine:selected.length>0&&segments.filter(r=>r.selected).every(r=>r.matches),exists:true,matches:segments.every(r=>r.matches)}));
    };
    const editor=new CineStackH3DirectorEditor(node,document.querySelector('main'),{name:'timeline_ui',options:{},element:document.querySelector('main')});
    node._cineStackEditor=editor;globalThis.editor=editor;globalThis.refine=refine;
  });
  await page.waitForSelector('.cstk-overview .cs-row');
  await page.waitForFunction(()=>editor.overview.data!==null);
  const checks=[]; const check=(ok,name)=>{if(!ok)throw new Error(name);checks.push(name)};
  check(await page.locator('.cs-row').count()===5,'real editor mounts five overview rows');
  check((await page.locator('.cs-source').first().innerText()).includes('继承全局 · 100'),'inherited effective seed visible');
  const input=page.locator('.cs-row').first().locator('.cs-seed input');
  await input.focus(); await input.pressSequentially('777');
  check(await input.inputValue()==='777','seed typing preserves focus across updates');
  check(await page.evaluate(()=>editor.timeline.segments[0].first_pass_seed)==='777','overview writes authoritative segment seed');
  check(await page.locator('.bd-batch-card').first().locator('[data-cstk-seed-control] input').inputValue()==='777','overview seed synchronizes the original card input');
  check((await page.locator('.cs-row').nth(3).innerText()).includes('18446744073709551615'),'uint64 seed remains exact');
  await page.locator('.cs-row').nth(1).locator('.cs-pin').click();
  check(await page.evaluate(()=>editor.timeline.segments[1].first_pass_seed)==='100','fix inherited seed without changing its effective value');
  await page.locator('.cs-refresh').click(); await page.waitForFunction(()=>editor.overview.data!==null);
  check((await page.locator('.cs-row').nth(2).innerText()).includes('一采失配'),'mismatch visible beside segment');
  await page.locator('.cs-row').nth(2).locator('.cs-diff summary').click();
  check((await page.locator('.cs-row').nth(2).innerText()).includes('100 → 当前: 200'),'mismatch shows cached and current seed');
  await page.locator('.cs-mode [data-mode="refine_only"]').click();
  await page.waitForFunction(()=>editor.overview.data!==null);
  check(await page.locator('.cs-queue').isDisabled(),'strict second pass blocked when any selected cache mismatches');
  await page.locator('.cs-scope select').selectOption('selected');
  for (const index of [2,4]) await page.locator('.cs-row').nth(index).locator('input[type=checkbox]').uncheck();
  await page.locator('.cs-refresh').click(); await page.waitForFunction(()=>editor.overview.data!==null);
  check(!(await page.locator('.cs-queue').isDisabled()),'matching selected subset enables second pass');
  await page.locator('.cs-queue').click();
  await page.waitForFunction(()=>globalThis.queued===1,{},{timeout:5000}).catch(async error=>{
    console.log(await page.evaluate(()=>({message:editor.overview.message.textContent,disabled:editor.overview.queue.disabled,
      mode:editor.timeline.executionMode,data:editor.overview.data,selection:editor.timeline.runSelection,posts:posts.length})));
    throw error;
  });
  check(await page.evaluate(()=>globalThis.queued)===1,'queue action calls Comfy host once');
  check(await page.evaluate(()=>JSON.parse(editor.timelineWidget.value).executionMode)==='refine_only','execution mode persists in actual timeline serialization');
  check(await page.evaluate(()=>refine.widgets.find(w=>w.name==='refine_only').value)===false,'UI mode never mutates wired Refine widgets');
  const asyncChecks = await page.evaluate(async () => {
    const {api}=await import('/scripts/api.js'); const {app}=await import('/scripts/app.js');
    const {connectedOverviewRefine}=await import('/web/js/cinestack_director_overview.js');
    const checks=[]; const check=(ok,name)=>{if(!ok)throw new Error(name);checks.push(name)};
    const overview=editor.overview;
    const originalFetch=api.fetchApi; let release, started;
    const waiting=new Promise(resolve=>started=resolve);
    api.fetchApi=async(...args)=>{started();await new Promise(resolve=>release=resolve);return originalFetch(...args)};
    const before=globalThis.queued;
    const pending=overview.submit();await waiting;
    check(overview.busy && overview.queue.disabled,'strict submission locks button before asynchronous preflight');
    await overview.submit();
    editor.timeline.executionMode='first_pass';overview.update();clearTimeout(overview.timer);
    release();await pending;api.fetchApi=originalFetch;
    check(globalThis.queued===before,'mode change during preflight cancels submission instead of sampling first pass');
    check(!overview.busy,'cancelled submission releases busy state');
    editor.timeline.executionMode='refine_only';overview.update();await overview.checkCache();
    refine.widgets.find(w=>w.name==='skip_fl2v').value=true;overview.update();
    check(overview.data===null,'Refine settings invalidate workbench status');
    refine.widgets.find(w=>w.name==='skip_fl2v').value=false;
    const reroute={id:88,type:'Reroute',mode:0,inputs:[{name:'',link:88}]};
    app.graph._nodes.push(reroute);app.graph.links[1]={origin_id:88};app.graph.links[88]={origin_id:39};
    check(connectedOverviewRefine(editor.node)===refine,'Refine resolver follows Reroute');
    app.graph.links[88]={origin_id:88};check(connectedOverviewRefine(editor.node)===null,'Refine resolver stops on Reroute cycle');
    app.graph.links[1]={origin_id:39};overview.update();await overview.checkCache();
    const globalSeed=editor.node.widgets.find(w=>w.name==='seed');const saved=globalSeed.value;
    const row=editor.timeline.segments[1];const fixed=row.first_pass_seed;
    row.first_pass_seed=null;globalSeed.value=10000000000000000;overview.update();
    check(overview.list.children[1].querySelector('.cs-pin').disabled,'unsafe global numeric seed cannot be pinned as an allegedly exact decimal');
    row.first_pass_seed=fixed;globalSeed.value=saved;overview.update();await overview.checkCache();
    return checks;
  });checks.push(...asyncChecks);
  await page.evaluate(()=>{refine.mode=4;editor.overview.updateAction()});
  check(await page.locator('.cs-queue').isDisabled(),'bypassed refine cannot enable strict action');
  await page.evaluate(()=>refine.mode=0);
  await page.locator('.cs-mode [data-mode="first_pass"]').click();
  check(!(await page.locator('.cs-queue').isDisabled()),'first pass can run despite stale/missing cache');
  const refused=await page.evaluate(async()=>{
    const {app}=await import('/scripts/app.js');const original=app.queuePrompt;
    app.queuePrompt=async()=>false;await editor.overview.submit();app.queuePrompt=original;
    return editor.overview.message.textContent;
  });
  check(refused.includes('尚未确认提交')&&!refused.includes('已提交队列'),'host false return never reports successful submission');
  await input.fill('-1');
  check(await page.locator('.cs-queue').isDisabled(),'invalid seed blocks queue without silently using old value');
  await input.fill('0');
  check((await page.locator('.cs-source').first().innerText()).includes('本段固定 · 0'),'zero is a fixed seed');
  await page.locator('.cs-mode [data-mode="legacy"]').click();
  check(await page.evaluate(()=>JSON.parse(editor.timelineWidget.value).executionMode)==='legacy','legacy behavior selectable and serialized');
  const jointState = await page.evaluate(() => {
    const before = editor.timeline.segments.map(s => s.first_pass_seed);
    editor.toggleContinuityJoint(2);
    const off = JSON.parse(editor.timelineWidget.value).segments[2].continuityFromPrev;
    editor.toggleContinuityJoint(2);
    const on = JSON.parse(editor.timelineWidget.value).segments[2].continuityFromPrev;
    return {off, on, sameSeeds: JSON.stringify(before) === JSON.stringify(editor.timeline.segments.map(s => s.first_pass_seed))};
  });
  check(jointState.off === false && jointState.on === true, 'junction toggles persist on the right segment without changing the legacy schema');
  check(jointState.sameSeeds, 'junction editing preserves all independent seeds');
  const lowMemory=page.locator('[data-r="out-low-memory"]');
  check(!(await lowMemory.isChecked()),'old workflow defaults to normal memory behavior');
  await lowMemory.check();
  check(await page.evaluate(()=>JSON.parse(editor.timelineWidget.value).output.lowMemoryMode)===true,'disk mode persists in timeline JSON');
  check(await page.locator('[data-r="out-export-mode"]').isDisabled(),'disk mode makes its file-delivery behavior explicit');
  check((await page.locator('.cs-message').innerText()).includes('IMAGE/AUDIO'),'disk mode explains blocked media sockets');
  await lowMemory.uncheck();
  check(!(await page.locator('[data-r="out-export-mode"]').isDisabled()),'disabling disk mode restores legacy export controls');
  await lowMemory.check();
  const rolling=page.locator('[data-r="out-rolling-generation"]');
  check(!(await rolling.isChecked()),'legacy workflows do not automatically enable rolling');
  await rolling.check();
  check(!(await lowMemory.isChecked()),'rolling replaces the heavy disk-export choice');
  check(await page.evaluate(()=>JSON.parse(editor.timelineWidget.value).output.rollingGeneration)===true,'rolling is serialized exactly in timeline output');
  check((await page.locator('.cs-message').innerText()).includes('复用其他段'),'all plus rolling explains saved-video reuse');
  check(!(await page.locator('[data-r="out-export-mode"]').isDisabled()),'rolling allows all versus selected export');
  const baseManifest=page.locator('[data-r="out-rolling-base"]');
  check(await baseManifest.isVisible(),'all plus rolling offers explicit legacy manifest import');
  await baseManifest.fill('E:\\ComfyUI\\output\\previous\\manifest.json');
  await baseManifest.blur();
  check(await page.evaluate(()=>JSON.parse(editor.timelineWidget.value).output.rollingBaseManifest)==='E:\\ComfyUI\\output\\previous\\manifest.json','legacy manifest path serializes without losing Windows separators');
  await page.locator('[data-r="out-export-mode"]').selectOption('segments');
  check(!(await baseManifest.isVisible()),'segment export hides full-result import');
  check((await page.locator('.cs-message').innerText()).includes('滚动生成'),'segment plus rolling retains selected-only description');
  check(await page.evaluate(()=>JSON.parse(editor.timelineWidget.value).output.exportMode)==='segments','rolling segment scope persists');
  await page.locator('[data-r="out-export-mode"]').selectOption('all');
  check((await page.locator('.cs-message').innerText()).includes('复用其他段'),'switching to all updates reuse scope');
  await lowMemory.check();
  check(!(await rolling.isChecked()),'selecting legacy disk mode disables rolling');
  await lowMemory.uncheck();
  check(!(await page.locator('[data-r="out-export-mode"]').isDisabled()),'turning off both memory modes restores normal export');
  await rolling.check();
  // Exercise the production global queue wrapper, not only the workbench action.
  const submissionChecks = await page.evaluate(async () => {
    const {CineStackH3DirectorEditor, parseTimeline} = await import('/web/js/minimax_timeline.js');
    const checks=[];const check=(ok,name)=>{if(!ok)throw new Error(name);checks.push(name)};
    const saved=JSON.parse(editor.timelineWidget.value);
    saved.executionMode='refine_only';
    Object.assign(saved.output,{rollingGeneration:true,lowMemoryMode:false,memoryDiagnostics:true,
      rollingBaseManifest:'output/previous/manifest.json',futureOutputSetting:17});
    const holder=document.createElement('div');document.body.append(holder);
    const node={...editor.node,id:57,widgets:editor.node.widgets.map(w=>({name:w.name,value:w.name==='timeline_data'?JSON.stringify(saved):w.value,options:{...w.options}})),_cineStackEditor:null};
    const loaded=new CineStackH3DirectorEditor(node,holder,{options:{},element:holder});node._cineStackEditor=loaded;
    check(loaded.outRolling.checked && loaded.timeline.executionMode==='refine_only','import keeps rolling and strict second pass');
    check(loaded.overview.modeButtons.find(b=>b.dataset.mode==='refine_only').getAttribute('aria-pressed')==='true','reloaded strict second-pass button is visibly selected');
    const payload=JSON.parse(loaded.timelineWidget.serializeValue(node));
    check(payload.output.rollingGeneration && payload.output.memoryDiagnostics && payload.output.futureOutputSetting===17 && payload.output.rollingBaseManifest===saved.output.rollingBaseManifest,'save/submit preserves output extensions including diagnostics and manifest');
    const again=parseTimeline(JSON.stringify(payload),620,24);
    check(again.executionMode==='refine_only' && again.output.rollingGeneration===true,'saved workflow round trip keeps execution mode');
    // Simulate a pending debounce / direct API export bypassing queuePrompt.
    loaded.timelineWidget.value='{}';loaded.overview.setMode('first_pass');loaded.timelineWidget.value='{}';
    const current=JSON.parse(loaded.timelineWidget.serializeValue(node));
    check(current.executionMode==='first_pass' && current.output.rollingGeneration,'serialization flushes editor without queue or blur');
    loaded.onOutputField('rollingGeneration',false);
    check(JSON.parse(loaded.timelineWidget.serializeValue(node)).output.rollingGeneration===false,'explicit disable survives serialization');
    const legacy=parseTimeline(JSON.stringify({...saved,executionMode:undefined,output:{exportMode:'all'}}),620,24);
    check(!legacy.output.rollingGeneration && !legacy.executionMode,'old workflows retain legacy non-rolling defaults');
    loaded.overview.dispose();holder.remove();return checks;
  });checks.push(...submissionChecks);
  const preflightChecks = await page.evaluate(async () => {
    const {app}=await import('/scripts/app.js');
    const {api}=await import('/scripts/api.js');
    const {installDirectorQueueGuard,rememberQueueNodeDefinition}=await import('/web/js/cinestack_director_overview.js');
    const checks=[];const check=(ok,name)=>{if(!ok)throw new Error(name);checks.push(name)};
    const overview=editor.overview;
    const savedSeeds=JSON.stringify(editor.timeline.segments.map(s=>s.first_pass_seed));
    const savedRefine=JSON.stringify(refine.widgets);
    check(overview.modeButtons.length===3 && !overview.root.querySelector('.cs-mode select'),'three visible stage buttons replace hidden mode dropdown');
    check(overview.stageConflict && overview.queue.disabled,'rolling All plus legacy confirmation is blocked before submission');
    check(!overview.recovery.hidden && overview.recovery.textContent.includes('滚动生成＋全部导出'),'conflict explains why and how to choose a stage');
    check(overview.root.querySelector('.cs-run-summary').textContent.includes('3 段 · 滚动生成 · 全部导出'),'run summary shows selected count and output modes');
    rememberQueueNodeDefinition({name:'SaveFixture',output_node:true});
    let reachable=true;
    app.graphToPrompt=async()=>({output:{56:{class_type:'CineStackH3Director',inputs:{timeline_data:editor.timelineWidget.serializeValue(editor.node)}},90:{class_type:'SaveFixture',inputs:reachable?{images:['56',0]}:{}},91:{class_type:'SaveFixture',inputs:{}}}});
    let flushes=0;
    installDirectorQueueGuard(()=>{flushes++;editor.flushTimelineSync()},()=>{});
    const installed=app.queuePrompt;installDirectorQueueGuard(()=>{},()=>{});
    check(app.queuePrompt===installed,'global queue guard installs once');
    const before=globalThis.queued;
    overview.root.open=false;
    check(await app.queuePrompt(0,1)===false && globalThis.queued===before,'main Run is stopped before host submission for the same conflict');
    check(overview.root.open && document.activeElement.dataset.fix==='first_pass','main Run expands and focuses an actionable recovery button');
    const repair=overview.recovery.querySelector('[data-fix="first_pass"]');repair.click();
    check(globalThis.queued===before && editor.timeline.executionMode==='first_pass','repair changes only mode and never starts sampling automatically');
    check(overview.modeButtons[0].getAttribute('aria-pressed')==='true','selected stage has an accessible pressed state');
    check(JSON.stringify(editor.timeline.segments.map(s=>s.first_pass_seed))===savedSeeds && JSON.stringify(refine.widgets)===savedRefine,'stage recovery preserves independent seeds and wired Refine values');
    check(JSON.parse(editor.timelineWidget.value).executionMode==='first_pass','repair persists the established workflow field');
    await app.queuePrompt(0,1);
    check(globalThis.queued===before+1 && flushes>=2,'global first pass passes through exactly once after preflight');
    overview.setMode('legacy');
    reachable=false;
    await app.queuePrompt(0,1);
    check(globalThis.queued===before+2,'unused Director does not block an unrelated output');
    reachable=true;
    await app.queuePrompt(0,1,{queueNodeIds:['91']});
    check(globalThis.queued===before+3,'partial execution ignores Directors outside requested dependencies');
    editor.node.mode=4;await app.queuePrompt(0,1);editor.node.mode=0;
    check(globalThis.queued===before+4,'bypassed Director does not block queue');
    editor.timeline.output.exportMode='segments';overview.update();
    check(!overview.stageConflict,'segment export keeps legacy mixed-stage behavior');
    editor.timeline.output.exportMode='all';
    refine.widgets.find(w=>w.name==='confirm_first_pass').value=false;overview.update();
    check(!overview.stageConflict,'legacy without confirm-first retains old behavior');
    refine.widgets.find(w=>w.name==='confirm_first_pass').value=true;
    editor.timeline.runSelectEnabled=false;overview.setMode('refine_only');
    const count=globalThis.queued;
    check(await app.queuePrompt(0,1)===false && globalThis.queued===count,'main Run also rejects missing strict second-pass caches');
    overview.recovery.querySelector('[data-fix="inspect"]').click();
    check([...overview.rows.values()].some(v=>!v.diff.hidden && v.diff.open),'cache recovery opens concrete segment differences');
    globalThis.forceMatch=true;await app.queuePrompt(0,1);
    check(globalThis.queued===count+1,'main Run rechecks and accepts matching second-pass caches');
    // A disconnected service must never be treated as a matching cache.
    const fetch=api.fetchApi;api.fetchApi=async()=>{throw new Error('offline')};
    check(await app.queuePrompt(0,1)===false && globalThis.queued===count+1,'cache request failure stops strict second pass before submission');
    check(overview.recovery.textContent.includes('offline'),'failed cache request has a visible retry action');
    api.fetchApi=fetch;
    const originalGraphToPrompt=app.graphToPrompt;
    app.graphToPrompt=async()=>{const p=await originalGraphToPrompt();p.output[56].inputs.timeline_data='{}';return p};
    const mismatchCount=globalThis.queued;
    check(await app.queuePrompt(0,1)===false && globalThis.queued===mismatchCount,'serialized stage mismatch blocks main Run');
    check(overview.recovery.textContent.includes('与界面不一致'),'serialization mismatch is explicitly explained');
    app.graphToPrompt=originalGraphToPrompt;
    overview.setMode('first_pass');editor.onOutputField('rollingGeneration',false);
    app.graphToPrompt=async()=>{const p=await originalGraphToPrompt();p.output[90].inputs={video:['56',9]};return p};
    check(await app.queuePrompt(0,1)===false && globalThis.queued===mismatchCount,'normal mode file VIDEO connection stops before queue');
    check(overview.recovery.textContent.includes('文件视频端口'),'file VIDEO conflict is actionable');
    overview.recovery.querySelector('[data-fix="rolling"]').click();
    check(editor.timeline.output.rollingGeneration===true && globalThis.queued===mismatchCount,'enable rolling action persists without auto-generation');
    await app.queuePrompt(0,1);
    check(globalThis.queued===mismatchCount+1,'file VIDEO queues after explicit rolling fix');
    app.graphToPrompt=originalGraphToPrompt;globalThis.forceMatch=false;
    editor.timeline.runSelectEnabled=true;editor.timeline.runSelection=[0,1,3];overview.setMode('legacy');
    delete app.graphToPrompt;
    return checks;
  });checks.push(...preflightChecks);
  await page.locator('.cs-row').nth(3).locator('.cs-title').click();
  check(await page.evaluate(()=>editor.selectedIndex)===3,'overview navigates existing segment editor');
  await page.evaluate(()=>{editor.selectedIndex=0;editor.renderImageBatchGroups()});
  await page.locator('.cs-mode [data-mode="first_pass"]').focus();
  await page.keyboard.press('Enter');
  check(await page.evaluate(()=>editor.timeline.executionMode)==='first_pass','execution buttons support keyboard activation');
  await page.locator('.cs-mode [data-mode="legacy"]').click();
  await page.evaluate(()=>document.querySelector('main').style.width='540px');
  check(await page.locator('.cstk-overview').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'narrow Comfy node fits even inside a wide browser viewport');
  await page.evaluate(()=>document.querySelector('main').style.width='100%');
  const deliveryChecks=await page.evaluate(async()=>{
    const checks=[];const check=(ok,name)=>{if(!ok)throw new Error(name);checks.push(name)};
    const {api}=await import('/scripts/api.js');
    const {ensureVideoOutputs}=await import('/web/js/cinestack_video_results.js');
    const original=Array.from({length:8},(_,i)=>({name:`old_${i}`,links:[100+i]}));
    const node={outputs:[...original],addOutput(name,type){this.outputs.push({name,type,links:null})}};
    ensureVideoOutputs(node);ensureVideoOutputs(node);
    check(node.outputs.length===10&&original.every((x,i)=>node.outputs[i]===x),'video ports append idempotently without changing any old slot or link');
    check(node.outputs[8].name==='first_pass_video'&&node.outputs[9].type==='VIDEO','new ports match backend ordering and VIDEO type');
    const rows=[{stage:'first',scope:'timeline',available:true,complete:true,filename:'timeline_first_pass.mp4',subfolder:'minimax_seg_export/测试 空格',type:'output',path:'/root/ComfyUI/output/minimax_seg_export/测试 空格/timeline_first_pass.mp4'},
      {stage:'final',scope:'timeline',available:false,complete:false,reason:'本轮尚未生成最终视频。'}];
    const emit=(node,output)=>api.dispatchEvent(new CustomEvent('executed',{detail:{node,output}}));
    emit(999,{cinestack_videos:rows});
    check(!editor.overview.videoResults.root.querySelector('.cs-video-row'),'other node execution cannot overwrite this Director results');
    emit(56,{cinestack_videos:rows});
    const root=editor.overview.videoResults.root;
    check(root.querySelectorAll('.cs-video-row').length===2,'executed metadata shows separate first and final results');
    check(root.querySelector('[data-stage=final]').textContent.includes('尚未生成')&&!root.querySelector('[data-stage=final] a'),'unproduced final has an explicit reason and no save or preview link');
    const player=root.querySelector('video');
    check(player.preload==='none'&&!player.hasAttribute('src'),'preview does not preload or fetch video bytes');
    const link=root.querySelector('a'); const url=new URL(link.href);
    check(link.download==='timeline_first_pass.mp4'&&url.searchParams.get('subfolder')==='minimax_seg_export/测试 空格','native download preserves encoded output locator and filename');
    check(!link.href.startsWith('blob:'),'download uses server file URL without a full-video Blob');
    const button=root.querySelector('button');button.click();
    check(!player.hidden&&player.src===link.href&&button.getAttribute('aria-expanded')==='true','preview button opens the file-backed native player');
    player.dispatchEvent(new Event('error'));
    check(root.querySelector('[role=status]').textContent.includes('无法播放'),'playback failure explains server file and download recovery');
    button.click();
    check(player.hidden&&!player.hasAttribute('src'),'closing preview removes media source and releases player buffering');
    emit(56,{cinestack_videos:[{...rows[0],scope:'selected',complete:false},rows[1]]});
    check(root.textContent.includes('本轮选中段')&&root.textContent.includes('仅部分段'),'selected and incomplete stages cannot look like full timeline output');
    emit(56,{cinestack_videos:[{...rows[0],filename:'../secret.mp4'},rows[1]]});
    check(!root.querySelector('a'),'unsafe locator is never turned into a download link');
    emit(56,{cinestack_videos:[]});
    check(!root.querySelector('video'),'normal mode result clears stale rolling preview');
    emit(56,{cinestack_videos:rows});
    check(editor.node._cinestackVideoResults===rows,'completed UI metadata survives editor remount without entering workflow settings');
    const extension=globalThis.extensions.find(item=>item.name==='ComfyUI.CineStackH3DirectorPlugin');
    class DirectorFixture { onExecuted(){return 'host-result';} }
    DirectorFixture.comfyClass='CineStackH3Director';
    await extension.beforeRegisterNodeDef(DirectorFixture,{name:'CineStackH3Director',input:{required:{}}});
    const restored=new DirectorFixture();
    check(restored.onExecuted({cinestack_videos:rows})==='host-result'&&restored._cinestackVideoResults===rows,'history/cached onExecuted restores file metadata and preserves host callback result');
    restored.onExecuted({unrelated:[]});
    check(restored._cinestackVideoResults===rows,'unrelated execution payload does not erase completed video metadata');
    return checks;
  });checks.push(...deliveryChecks);
  if(process.env.QA_DIR){
    await fs.mkdir(process.env.QA_DIR,{recursive:true});
    await page.evaluate(async()=>{await editor.overview.checkCache();editor.overview.list.scrollTop=0});
    await page.locator('.cstk-overview').screenshot({path:path.join(process.env.QA_DIR,'director-desktop.png')});
    await page.locator('.cs-videos').screenshot({path:path.join(process.env.QA_DIR,'videos-desktop.png')});
    await page.setViewportSize({width:600,height:1100});
    await page.locator('.cstk-overview').screenshot({path:path.join(process.env.QA_DIR,'director-narrow.png')});
    await page.locator('.cs-videos').screenshot({path:path.join(process.env.QA_DIR,'videos-narrow.png')});
    check(await page.evaluate(()=>{const el=editor.overview.root;return el.scrollWidth<=el.clientWidth+2}),'workbench has no narrow-panel horizontal overflow');
  }
  check(errors.length===0,`browser errors: ${errors.join(', ')}`);
  const modeChecks=await page.evaluate(async()=>{
    const checks=[];const check=(ok,name)=>{if(!ok)throw new Error(name);checks.push(name)};
    const {setLocale}=await import('/web/js/minimax_i18n.js');
    setLocale('en');check(editor.overview.root.textContent.includes('Segment workbench'),'overview follows English locale');
    check(editor.overview.videoResults.root.textContent.includes('Download file'),'video preview and download actions follow English locale');
    check(editor.root.textContent.includes('Low RAM'),'disk-mode label follows English locale');
    check(editor.root.textContent.includes('Rolling generation'),'rolling label follows English locale');setLocale('zh');
    const raw={version:5,timelineMode:'fl2v',editMode:'segment',frameRate:24,global:{taskType:'fl2v'},
      output:{mode:'fixed',width:864,height:480,audioMode:'generate'},
      shots:[{id:'s1',durationSec:5,prompt:'first',first_pass_seed:'0'},{id:'s2',durationSec:5,prompt:'second',first_pass_seed:'200'}]};
    editor.applyImportedTimeline(raw,{task_type:'fl2v — 首尾帧生视频(First Last Frame to Video)'});editor.overview.update();
    check(editor.overview.rows.size===2,'FL2V shot groups appear in overview');
    const input=editor.overview.list.children[1].querySelector('.cs-seed input');input.value='188';input.dispatchEvent(new Event('input',{bubbles:true}));
    check(editor.timeline.shots[1].first_pass_seed==='188'&&editor.timeline.segments[1].first_pass_seed==='188','FL2V seed writes shots and rebuilt segments');
    check(JSON.parse(editor.timelineWidget.value).shots[1].first_pass_seed==='188','FL2V workflow serialization retains seed');
    editor.timeline.shots[0].externalSeedLinked=true;editor.overview.update();
    check(editor.overview.list.children[0].querySelector('.cs-seed input').disabled,'externally wired seed stays read-only');
    return checks;
  });checks.push(...modeChecks);
  check(errors.length===0,`final browser errors: ${errors.join(', ')}`);
  await page.evaluate(()=>editor.destroy());
  check(await page.locator('.cstk-overview').count()===0,'removing editor disposes overview and listeners');
  console.log(JSON.stringify({passed:checks.length,checks},null,2));
} finally {await browser?.close();await new Promise(resolve=>server.close(resolve));}
