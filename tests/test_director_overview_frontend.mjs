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
      if (req.url === '/web/js/minimax_timeline.js') source += '\nexport {CineStackH3DirectorEditor};';
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
  await page.locator('.cs-mode select').selectOption('refine_only');
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
  await page.locator('.cs-mode select').selectOption('first_pass');
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
  await page.locator('.cs-mode select').selectOption('legacy');
  check(await page.evaluate(()=>JSON.parse(editor.timelineWidget.value).executionMode)==='legacy','legacy behavior selectable and serialized');
  await page.locator('.cs-row').nth(3).locator('.cs-title').click();
  check(await page.evaluate(()=>editor.selectedIndex)===3,'overview navigates existing segment editor');
  await page.evaluate(()=>{editor.selectedIndex=0;editor.renderImageBatchGroups()});
  await page.evaluate(()=>document.querySelector('main').style.width='540px');
  check(await page.locator('.cstk-overview').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'narrow Comfy node fits even inside a wide browser viewport');
  await page.evaluate(()=>document.querySelector('main').style.width='100%');
  if(process.env.QA_DIR){
    await fs.mkdir(process.env.QA_DIR,{recursive:true});
    await page.evaluate(async()=>{await editor.overview.checkCache();editor.overview.list.scrollTop=0});
    await page.screenshot({path:path.join(process.env.QA_DIR,'director-desktop.png'),fullPage:true});
    await page.setViewportSize({width:600,height:1100});
    await page.screenshot({path:path.join(process.env.QA_DIR,'director-narrow.png'),fullPage:true});
    check(await page.evaluate(()=>{const el=editor.overview.root;return el.scrollWidth<=el.clientWidth+2}),'workbench has no narrow-panel horizontal overflow');
  }
  check(errors.length===0,`browser errors: ${errors.join(', ')}`);
  const modeChecks=await page.evaluate(async()=>{
    const checks=[];const check=(ok,name)=>{if(!ok)throw new Error(name);checks.push(name)};
    const {setLocale}=await import('/web/js/minimax_i18n.js');
    setLocale('en');check(editor.overview.root.textContent.includes('Segment workbench'),'overview follows English locale');setLocale('zh');
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
