/** Real ESM loading through Comfy-style discovery while old URLs serve stale JS. */
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const require = createRequire(import.meta.url);
const {chromium} = require('playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(execFileSync(process.env.PYTHON || 'python3', ['-c', `
import importlib,json,sys,types
from pathlib import Path
p=types.ModuleType('asset_browser');p.__path__=[str(Path.cwd())];sys.modules[p.__name__]=p
m=importlib.import_module('asset_browser.frontend_assets')
a=m.get_frontend_assets()
print(json.dumps({'token':a.token,'version':m.PLUGIN_VERSION,'files':{k:v.decode() for k,v in a.files.items()}}))
`], {cwd:root, maxBuffer:8*1024*1024}));
const base = `/extensions/ComfyUI-CineStack-H3/${manifest.token}/`;
const requests=[];
const server=http.createServer((req,res)=>{
  requests.push(req.url);
  res.setHeader('Cache-Control','no-store');
  if(req.url==='/extensions') {res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(Object.keys(manifest.files).filter(x=>x.endsWith('.js')).map(x=>base+x)));}
  if(req.url==='/cinestack/h3/version'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({package:'cinestack-h3',version:manifest.version,frontend_asset_version:manifest.token}));}
  res.setHeader('Content-Type',req.url.endsWith('.js')?'text/javascript':'text/html');
  if(req.url==='/scripts/app.js')return res.end('export const app={graph:{_nodes:[]},registerExtension(x){(globalThis.extensions||=[]).push(x)}};');
  if(req.url==='/scripts/api.js')return res.end('export const api=new EventTarget();api.fetchApi=(url,options)=>fetch(url,options);');
  if(req.url.startsWith(base)){
    const source=manifest.files[req.url.slice(base.length)];
    if(source!==undefined)return res.end(source);
    res.statusCode=404;return res.end();
  }
  if(req.url.startsWith('/extensions/'))return res.end('throw new Error("STALE FRONTEND CACHE WAS USED");');
  res.end('<!doctype html><meta charset="utf-8"><p>Versioned frontend fixture</p>');
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser;
try{
  browser=await chromium.launch({headless:true,...(process.env.CHROME_BIN?{executablePath:process.env.CHROME_BIN}:{})});
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  const results=await page.evaluate(async ({base,version})=>{
    const checks=[];const check=(ok,name)=>{if(!ok)throw new Error(name);checks.push(name);};
    const urls=await (await fetch('/extensions')).json();
    await Promise.all(urls.map(url=>import(url)));
    check(urls.length===17,'all 17 production modules discovered through versioned paths');
    const names=globalThis.extensions.map(x=>x.name);
    check(new Set(names).size===names.length,'each extension registers exactly once');
    const migration=globalThis.extensions.find(x=>x.name==='CineStack.H3.WorkflowMigration');
    await migration.setup();
    const graph={nodes:[{id:56,type:'CineStackH3Director',properties:{ver:'0.1.1'},widgets_values:['18446744073709551615']}],links:[[1,2,0,56,0,'MODEL']]};
    await migration.beforeConfigureGraph(graph);
    check(graph.nodes[0].properties.ver===version,'old workflow gets actual backend version through versioned module');
    check(graph.nodes[0].widgets_values[0]==='18446744073709551615'&&graph.links[0][3]===56,'old workflow exact seed and link preserved');
    const node={comfyClass:'CineStackH3Director'};migration.nodeCreated(node);
    check(node.properties.ver===version,'new node version synchronized');
    const source=await (await fetch(base+'minimax_timeline.js')).text();
    check(source.includes('out-rolling-generation')&&source.includes('mountDirectorOverview'),'new director has rolling switch and segment overview');
    check(source.includes('rollingGeneration')&&source.includes('executionMode'),'rolling and first/refine mode wiring retained');
    const modules=await Promise.all([import(base+'minimax_refine.js'),import(base+'minimax_refine.js')]);
    check(modules[0]===modules[1],'entry and dependency use same cached ESM instance');
    return checks;
  },{base,version:manifest.version});
  if(errors.length)throw new Error(errors.join('\n'));
  if(requests.some(url=>url.startsWith('/extensions/')&&!url.startsWith(base)))throw new Error('unversioned extension requested');
  if(requests.filter(url=>url==='/scripts/app.js').length!==1||requests.filter(url=>url==='/scripts/api.js').length!==1)throw new Error('host modules instantiated more than once');
  console.log(JSON.stringify({passed:results.length+2,checks:[...results,'no stale fixed URLs requested','one canonical host app/api instance'],asset_version:manifest.token},null,2));
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
