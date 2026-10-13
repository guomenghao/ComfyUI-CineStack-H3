// Modified for CineStack on 2026-10-13; see CHANGELOG.md and NOTICE.
/** Browser checks with real plugin JS modules; Comfy host APIs are inert stubs. */
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
  if (req.url === '/scripts/app.js') return res.end('export const app = { graph: {_nodes:[], links:{}}, registerExtension(x){(globalThis.extensions ||= []).push(x)} };');
  if (req.url === '/scripts/api.js') return res.end('export const api = new EventTarget(); api.fetchApi = async () => new Response("{}", {status:200});');
  if (req.url.startsWith('/web/js/')) {
    try { return res.end(await fs.readFile(path.join(root, req.url))); }
    catch { res.statusCode = 404; return res.end(); }
  }
  res.end('<html><meta charset="utf-8"><style>body{font:14px system-ui;background:#181818;color:#ddd;padding:24px}#fixture{width:390px;padding:16px;border:1px solid #444;border-radius:6px}input{color:#ddd;background:#242424;border:1px solid #555;padding:6px}</style><h2>分段一采 seed</h2><div id="fixture"></div></html>');
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await chromium.launch({headless: true,
    ...(process.env.CHROME_BIN ? {executablePath: process.env.CHROME_BIN} : {})});
  const page = await browser.newPage({viewport:{width:760,height:540}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  const results = await page.evaluate(async () => {
    const seed = await import('/web/js/minimax_segment_seed.js');
    const fl = await import('/web/js/minimax_fl2v.js');
    const gen = await import('/web/js/minimax_gen_timeline.js');
    const batch = await import('/web/js/minimax_image_batch.js');
    const witness = await import('/web/js/minimax_external_witness.js');
    await import('/web/js/minimax_timeline.js');
    await import('/web/js/minimax_refine.js');
    const checks = [];
    const check = (ok, name) => { if (!ok) throw new Error(name); checks.push(name); };
    const migration = await import('/web/js/cinestack_migration.js');
    const old = {nodes:[{id:9,type:'MiniMaxH3Director',widgets_values:[0,'18446744073709551615'],
      inputs:[{name:'model',link:11}]}],links:[[11,1,0,9,0,'MODEL']],
      definitions:{subgraphs:[{nodes:[{type:'MiniMaxH3DirectorRefine'}]}]}};
    const widgets = JSON.stringify(old.nodes[0].widgets_values);
    check(migration.migrateWorkflowInPlace(old) === 2 && old.nodes[0].type === 'CineStackH3Director', 'legacy root and nested nodes migrate');
    check(JSON.stringify(old.nodes[0].widgets_values) === widgets && old.nodes[0].id === 9 && old.links[0][3] === 9, 'migration preserves widgets seed IDs and links');
    check(migration.migrateWorkflowInPlace(old) === 0, 'migration is idempotent');
    const upstream = {nodes:[{type:'MiniMaxH3Director'}]};
    check(migration.migrateWorkflowInPlace(upstream, () => true) === 0 && upstream.nodes[0].type === 'MiniMaxH3Director', 'installed upstream nodes are not intercepted');
    const apiOld = {'9':{class_type:'MiniMaxH3Director',inputs:{seed:0,global_prompt:'MiniMaxH3Director'}}};
    check(migration.migrateWorkflowInPlace(apiOld) === 1 && apiOld['9'].inputs.global_prompt === 'MiniMaxH3Director', 'API migration preserves user prompt');

    check(seed.normalizeSegmentSeed('0000') === '0', 'seed zero');
    check(seed.normalizeSegmentSeed('18446744073709551615') === '18446744073709551615', 'uint64 precision');
    check(seed.normalizeSegmentSeed('') === null, 'inherit global');
    for (const value of ['-1','1.5','1e3','18446744073709551616']) {
      let rejected = false; try { seed.normalizeSegmentSeed(value); } catch { rejected = true; }
      check(rejected, `reject ${value}`);
    }
    const row = {};
    let syncs = 0;
    const control = seed.createSegmentSeedControl(() => row, () => syncs++,
      {label:'一采 seed', placeholder:'留空继承全局'});
    document.querySelector('#fixture').append(control);
    const input = control.querySelector('input');
    input.value = '18446744073709551615'; input.dispatchEvent(new Event('input'));
    check(row.first_pass_seed === '18446744073709551615' && syncs === 1, 'input writes exact JSON seed immediately');
    input.value = '-2'; input.dispatchEvent(new Event('input'));
    check(row.first_pass_seed === '-2' && !input.checkValidity(), 'invalid draft persists for backend rejection');
    input.value = '0'; input.dispatchEvent(new Event('input'));
    check(row.first_pass_seed === '0' && input.checkValidity(), 'recover valid seed');
    const editor = {timeline:{frameRate:24, output:{}, shots:[fl.newFl2vShot({first_pass_seed:'18446744073709551615',prompt:'shot'})]},
      selectedIndex:0, getFrameRate:()=>24};
    fl.syncFl2vFromShots(editor);
    check(editor.timeline.segments[0].first_pass_seed === '18446744073709551615', 'fl2v rebuild preserves seed');
    const payload = fl.buildFl2vPayloadFields(editor);
    check(payload.shots[0].first_pass_seed === '18446744073709551615' && payload.segments[0].first_pass_seed === '18446744073709551615', 'fl2v payload preserves seed');
    fl.duplicateFl2vShot(editor);
    check(editor.timeline.shots[1].first_pass_seed === '18446744073709551615', 'fl2v duplicate preserves seed');
    const e2 = {timeline:{segments:[gen.newBatchSegment({first_pass_seed:'0',taskType:'r2v'})],output:{}}, selectedIndex:0,
      getTaskKey:()=> 'r2v', getFrameRate:()=>24, renderImageBatchGroups:()=>{}};
    batch.duplicateImageBatchGroup(e2);
    check(e2.timeline.segments[1].first_pass_seed === '0', 'r2v duplicate preserves zero');
    check(gen.newBatchSegment({taskType:'t2v'}).first_pass_seed === null, 'legacy new row inherits');
    const source = {id:1,type:'CineStackH3DirectorGroupImageToVideo',inputs:[],widgets:[{name:'prompt',value:'a'}]};
    const director = {id:2,inputs:[{name:'i2v_groups',link:10}]};
    const graph = {_nodes:[source,director],links:{10:{origin_id:1,origin_slot:0}}};
    source.graph = graph; director.graph = graph;
    witness.setExternalGroupSpecsProvider(() => [{node:source,nodeLabel:'1:group',durationSec:5,prompt:'a'}]);
    const before = witness.buildExternalGroupsWitness(director);
    source.widgets.push({name:'first_pass_seed',value:''});
    const after = witness.buildExternalGroupsWitness(director);
    check(JSON.stringify(before) === JSON.stringify(after), 'blank new external widget keeps legacy witness');
    source.type = 'MiniMaxH3DirectorGroupImageToVideo';
    witness.setExternalGroupSpecsProvider(() => [{node:source,nodeLabel:'1:MiniMaxH3DirectorGroupImageToVideo',durationSec:5,prompt:'a'}]);
    const legacyWitness = witness.buildExternalGroupsWitness(director);
    source.type = 'CineStackH3DirectorGroupImageToVideo';
    witness.setExternalGroupSpecsProvider(() => [{node:source,nodeLabel:'1:CineStackH3DirectorGroupImageToVideo',durationSec:5,prompt:'a'}]);
    check(JSON.stringify(legacyWitness) === JSON.stringify(witness.buildExternalGroupsWitness(director)), 'brand rename preserves external cache witness');

    witness.setExternalGroupSpecsProvider(() => [{node:source,nodeLabel:'1:group',durationSec:5,prompt:'a',firstPassSeed:'0'}]);
    check(witness.buildExternalGroupsWitness(director).groups[0].first_pass_seed === '0', 'external witness carries explicit seed');
    const { app } = await import('/scripts/app.js');
    const { api } = await import('/scripts/api.js');
    const refineNode = {id:39,type:'CineStackH3DirectorRefine',widgets:[
      {name:'mode',value:'refine'}, {name:'refine_only',value:true},
      {name:'confirm_first_pass',value:false}, {name:'seed_mode',value:'inherit'},
      {name:'seed',value:0}, {name:'sampler',value:'euler'}, {name:'passes',value:1}],
      inputs:[{name:'sigmas',link:200}],
      addDOMWidget(name, type, element, options){
        const w={name,type,element,options,value:''}; this.widgets.push(w);
        document.body.append(element); return w;
      }};
    const directorNode = {id:12,type:'CineStackH3Director',inputs:[{name:'refine',link:100}],
      widgets:[{name:'seed',value:999},{name:'timeline_data',value:JSON.stringify({segments:[{first_pass_seed:'18446744073709551615'}]})}]};
    app.graph = {_nodes:[directorNode,refineNode],links:{100:{origin_id:39}}};
    refineNode.graph = app.graph;
    let data={exists:true,matches:false,segment_total:5,cached_count:5,matched_count:4,
      refine_only:true,confirm_first_pass:true,can_confirm_refine:false,current_seed:999,
      segments:[{segment:3,selected:true,matches:false,expected_seed_text:'18446744073709551615',
        cached_seed_text:'100',diff_keys:['seed']}],diff_keys:['seed']};
    let posted = null;
    api.fetchApi = async (_url, options) => {
      posted = JSON.parse(options.body); return new Response(JSON.stringify(data),{status:200});
    };
    globalThis.extensions.find(e=>e.name==='ComfyUI.CineStackH3DirectorRefine').nodeCreated(refineNode);
    await new Promise(resolve=>setTimeout(resolve,400));
    check(posted.refine.refine_only===true, 'strict mode included in status request');
    let text=refineNode._mmxFirstPassCacheUI.body.textContent;
    check(text.includes('仅二采：当前不能执行') && text.includes('第 3 段') && text.includes('18446744073709551615'), 'status shows segment reason and exact expected seed');
    data={...data,matches:true,matched_count:5,can_confirm_refine:true,
      segments:[{...data.segments[0],matches:true,cached_seed_text:'18446744073709551615',diff_keys:[]}],diff_keys:[]};
    refineNode._mmxFirstPassCacheUI.refresh.click();
    await new Promise(resolve=>setTimeout(resolve,50));
    text=refineNode._mmxFirstPassCacheUI.body.textContent;
    check(text.includes('仅二采：缓存元数据匹配') && text.includes('缓存 seed：18446744073709551615'), 'status displays strict success without uint64 rounding');
    return checks;
  });
  if (errors.length) throw new Error(errors.join('\n'));
  if (process.env.QA_SCREENSHOT) await page.screenshot({path:process.env.QA_SCREENSHOT});
  console.log(JSON.stringify({passed: results.length, checks: results}, null, 2));
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
