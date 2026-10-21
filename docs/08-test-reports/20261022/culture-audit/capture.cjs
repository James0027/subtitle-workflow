const path = require('path');
const fs = require('fs');
const {chromium} = require('C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.route('**/*',r=>r.request().url().startsWith('http://127.0.0.1:8765/')?r.continue():r.abort());
  await page.goto('http://127.0.0.1:8765/',{waitUntil:'networkidle'});
  await page.screenshot({path:path.join(__dirname,'current-app-not-culture-integrated.png'),fullPage:true});
  const body=await page.locator('body').innerText();
  const route=await page.request.get('http://127.0.0.1:8765/api/v1/culture/sources');
  fs.writeFileSync(path.join(__dirname,'browser-results.json'),JSON.stringify({url:page.url(),culture_sources_status:route.status(),culture_text_present:body.includes('文化检测'),note:'正式现有应用截图，非文化通过截图；未操作任何云调用。'},null,2));
  await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
