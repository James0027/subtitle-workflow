// Real application assets; isolated intercepted fixture responses, no live server/cloud.
const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const root=process.cwd(),dir=path.join(root,'docs/08-test-reports/20261022');
 const fixture=JSON.parse(fs.readFileSync(path.join(dir,'translation-ui-fixture.json'),'utf8'));
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});
 const result={scope:'SIMULATED fixture UI, intercepted local HTTP, no model calls',requests:[],errors:[]};
 page.on('pageerror',e=>result.errors.push(e.message));
 page.on('dialog',async d=>{result.dialog=d.message();await d.dismiss();});
 await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url());
  if(url.pathname.startsWith('/api/')){
   let value={};
   if(url.pathname.endsWith('/auth/session'))value={authenticated:true,actor:{operator_id:'SIMULATED',display_name:'SIMULATED',role:'media_operator'}};
   if(url.pathname.endsWith('/source-transcript'))value=fixture.source;
   if(url.pathname.endsWith('/translations'))value=fixture.translations;
   if(req.method()!=='GET'){
    result.requests.push({path:url.pathname,method:req.method(),body:req.postDataJSON()});
    await route.fulfill({status:422,contentType:'application/json',body:JSON.stringify({detail:[{loc:['body','source_revision'],msg:'Field required'}]})});return;
   }
   await route.fulfill({contentType:'application/json',body:JSON.stringify(value)});return;
  }
  let name=url.pathname==='/'?'index.html':path.basename(url.pathname);
  if(!['index.html','app.js','style.css'].includes(name)){await route.abort();return;}
  await route.fulfill({contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html',body:fs.readFileSync(path.join(root,'code/web',name))});
 });
 await page.addInitScript(task=>localStorage.setItem('active_task_id',task),fixture.task_id);
 await page.goto('http://127.0.0.1:8878/');
 await page.waitForTimeout(800);
 const save=page.locator('.btn-save-trans').first();
 await save.scrollIntoViewIfNeeded();
 await save.click();
 await page.waitForTimeout(200);
 result.missing_source_revision=result.requests.some(r=>r.method==='PATCH'&& !r.body?.source_revision);
 await page.screenshot({path:path.join(dir,'translation-ui-missing-revision.png'),fullPage:true});
 fs.writeFileSync(path.join(dir,'translation-ui-review.json'),JSON.stringify(result,null,2));
 await browser.close();console.log(JSON.stringify(result));
})().catch(e=>{console.error(e.message);process.exitCode=1});
