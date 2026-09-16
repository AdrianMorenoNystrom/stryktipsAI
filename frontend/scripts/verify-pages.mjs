// Verify the production artifact under a repository prefix, including hard reload.
// Default API responses are recorded fixtures; VERIFY_API_ORIGIN uses a real test API.
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';

const root = resolve('dist/stryktipset/browser');
const index = await readFile(resolve(root, 'index.html'), 'utf8');
const prefix = index.match(/<base href="([^"]+)"/)?.[1];
assert(prefix?.startsWith('/') && prefix.endsWith('/'));
const fixture = JSON.parse(await readFile('e2e/fixtures/live.json', 'utf8'));
const config = {budgetPresets:[64,128,256,512,1024], costPerRow:1, leagues:['E0','E1','E2'], environment:'production', demoEnabled:false, crowdTolerance:1, valueFloor:0.01};
const types = {'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.ico':'image/x-icon'};
const server = createServer(async (req,res) => {
  try {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    if (!pathname.startsWith(prefix)) { res.writeHead(404).end(); return; }
    const path = resolve(root, decodeURIComponent(pathname.slice(prefix.length)) || 'index.html');
    if (!path.startsWith(root+sep)) { res.writeHead(403).end(); return; }
    res.writeHead(200, {'Content-Type':types[extname(path)] || 'application/octet-stream'});
    res.end(await readFile(path));
  } catch { res.writeHead(404).end(); }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const browser = await chromium.launch();
const report = {verified_at:new Date().toISOString(), prefix, api:process.env.VERIFY_API_ORIGIN ? 'real local production API' : 'recorded test responses', checks:[]};
try {
  for (const [name, width, height] of [['desktop',1440,1050],['mobile',390,844]]) {
    const page = await browser.newPage({viewport:{width,height}});
    const errors=[];
    let empty=false;
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => {if(r.url().startsWith('http://127.0.0.1:') && r.status()>=400) errors.push(`Asset ${r.status()}: ${r.url()}`);});
    await page.route('https://api.example.invalid/api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if(empty && path==='/api/coupon/current') {
        await route.fulfill({json:{...fixture.state, draw:null, coupon:null, analysis_ready:false, message:'Ingen aktuell kupong finns.', available_draws:[]}}); return;
      }
      if(process.env.VERIFY_API_ORIGIN) {
        const response=await route.fetch({url:route.request().url().replace('https://api.example.invalid',process.env.VERIFY_API_ORIGIN), headers:{...route.request().headers(), origin:'https://example.github.io'}});
        // Only this local test proxy rewrites CORS for its ephemeral localhost port.
        // The API's configured production origin is independently checked below.
        assert.equal(response.headers()['access-control-allow-origin'],'https://example.github.io');
        await route.fulfill({response,headers:{...response.headers(),'access-control-allow-origin':route.request().headers().origin}}); return;
      }
      const data = path==='/api/config' ? config : path==='/api/coupon/current' ? fixture.state : path==='/api/coupon/analyze' ? fixture.analysis : path==='/api/stryktipset/draws' ? fixture.archive : path.endsWith('/market') ? {market:[],crowd:fixture.crowd.history,predictions:[]} : {};
      await route.fulfill({json:data});
    });
    const url=`http://127.0.0.1:${server.address().port}${prefix}#/overview`;
    await page.goto(url);
    await page.locator('.optimal-cell').last().waitFor({timeout:30000}).catch(async error => {
      console.error(JSON.stringify({page_errors:errors, body:await page.locator('body').innerText()}));
      throw error;
    });
    assert.equal(await page.locator('.optimal-cell').count(),13);
    assert.equal(await page.getByText('DEMO DATA',{exact:true}).count(),0);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if(process.env.VERIFY_SCREENSHOTS) {
      const destination=resolve(process.env.VERIFY_SCREENSHOTS);
      await mkdir(destination,{recursive:true});
      await page.screenshot({path:resolve(destination,`launch-v4-${name}.png`),fullPage:true});
      if(name==='mobile') await page.screenshot({path:resolve(destination,'launch-v4-mobile-fold.png')});
      await page.locator('.optimal-cell').first().click();
      await page.getByRole('dialog').waitFor();
      await page.screenshot({path:resolve(destination,`launch-v4-explanation-${name}.png`)});
      await page.getByRole('tab',{name:'Historik',exact:true}).click();
      await page.locator('app-market-history').waitFor();
      await page.screenshot({path:resolve(destination,`launch-v4-history-${name}.png`)});
      await page.keyboard.press('Escape');
    }
    await page.goto(url.replace('#/overview','#/history'));
    await page.reload();
    await page.locator('app-draw-archive').waitFor();
    await page.waitForLoadState('networkidle');
    assert(page.url().includes('#/history'));
    empty=true;
    await page.goto(url);
    await page.reload();
    await page.getByText('Ingen aktuell kupong finns tillgänglig. Försök uppdatera senare.',{exact:true}).waitFor();
    await page.getByText('DATA SAKNAS',{exact:true}).waitFor();
    assert.equal(await page.locator('.optimal-cell').count(),0);
    assert.equal(await page.getByText('DEMO DATA',{exact:true}).count(),0);
    assert.deepEqual(errors,[]);
    report.checks.push({viewport:name, thirteen_matches:true, no_horizontal_overflow:true, hash_route_reload:true, missing_data_never_demo:true, page_errors:0});
    await page.unrouteAll({behavior:'wait'});
    await page.close();
  }
  if(process.env.VERIFY_REPORT) await writeFile(process.env.VERIFY_REPORT,JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
} catch (error) {
  console.error(error);
  process.exitCode=1;
} finally {
  for (const context of browser.contexts()) for (const page of context.pages()) await page.unrouteAll({behavior:'wait'});
  await browser.close();
  await new Promise(done=>server.close(done));
}
