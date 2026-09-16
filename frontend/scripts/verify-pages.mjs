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
// Layout-only chart/table examples. Never written to the provider archive.
const marketHistory = {
  crowd:fixture.crowd.history,
  market:fixture.crowd.history.map(row => ({...row,consensus:fixture.analysis.matches[0].market})),
  predictions:[{id:'layout-test',predicted_at:fixture.analysis.analyzedAt,model:fixture.analysis.matches[0].model}],
};
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
async function assertNoHorizontalOverflow(page, state) {
  await page.evaluate(() => document.fonts.ready);
  const layout = await page.evaluate(() => {
    const viewport = window.innerWidth;
    const width = document.documentElement.scrollWidth;
    const overflowing = [...document.querySelectorAll('body *')].flatMap(el => {
      if (!el.checkVisibility()) return [];
      const r = el.getBoundingClientRect();
      if (r.right <= viewport + 1 && r.left >= -1) return [];
      const style = getComputedStyle(el);
      return [{element:el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().replace(/\s+/g,'.') : ''),
        left:r.left, right:r.right, width:r.width, minWidth:style.minWidth, grid:style.gridTemplateColumns,
        text:el.textContent.trim().replace(/\s+/g,' ').slice(0,80)}];
    });
    const containers = [...document.querySelectorAll('dialog[open]')].map(el => ({element:el.tagName.toLowerCase()+'.'+el.className,width:el.clientWidth,scrollWidth:el.scrollWidth})).filter(el=>el.scrollWidth>el.width);
    return {viewport,width,overflowing,containers};
  });
  if (layout.width > layout.viewport || layout.containers.length) console.error('Horizontal overflow detected:', JSON.stringify({state,...layout,overflowing:layout.overflowing.slice(0,20),totalOverflowing:layout.overflowing.length},null,2));
  assert(layout.width <= layout.viewport, `${state}: document width ${layout.width}px exceeds viewport ${layout.viewport}px`);
  assert.equal(layout.containers.length,0,`${state}: dialog content needs a local scroll wrapper`);
}
try {
  for (const [name, width, height] of [['desktop',1440,1050],['mobile',390,844],['mobile-small',320,740],['mobile-medium',375,812],['tablet',768,1024]]) {
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
      const data = path==='/api/config' ? config : path==='/api/coupon/current' ? fixture.state : path==='/api/coupon/analyze' ? fixture.analysis : path==='/api/coupon/cost' ? fixture.analysis.system : path==='/api/stryktipset/draws' ? fixture.archive : path==='/api/stryktipset/draws/4969' ? fixture.latestHistory : path.endsWith('/market') ? marketHistory : path.endsWith('/crowd') ? fixture.crowd : {};
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
    await assertNoHorizontalOverflow(page, `${name}: overview`);
    const budgetButtons = page.locator('.budget-main .segmented button');
    if(!process.env.VERIFY_API_ORIGIN) assert.equal(await budgetButtons.count(),config.budgetPresets.length);
    else assert(await budgetButtons.count()>0);
    assert(await budgetButtons.evaluateAll(buttons=>buttons.every(button=>{
      const r=button.getBoundingClientRect(), parent=button.parentElement.getBoundingClientRect();
      return r.left>=parent.left && r.right<=parent.right && r.width>=44 && r.height>=44;
    })),`${name}: every budget button must be readable and inside its wrapper`);
    await page.locator('.profile-options > summary').click();
    await assertNoHorizontalOverflow(page, `${name}: budget options`);
    await page.locator('.profile-options > summary').click();
    await page.getByLabel('Förklara 13-rättschansen',{exact:true}).click();
    await assertNoHorizontalOverflow(page, `${name}: probability help`);
    await page.getByLabel('Förklara 13-rättschansen',{exact:true}).click();
    if(process.env.VERIFY_SCREENSHOTS) {
      const destination=resolve(process.env.VERIFY_SCREENSHOTS);
      await mkdir(destination,{recursive:true});
      await page.screenshot({path:resolve(destination,`launch-v4-${name}.png`),fullPage:true});
      if(name==='mobile') await page.screenshot({path:resolve(destination,'launch-v4-mobile-fold.png')});
    }
    await page.locator('.optimal-cell').first().click();
    await page.getByRole('dialog').waitFor();
    await assertNoHorizontalOverflow(page, `${name}: match explanation`);
    if(process.env.VERIFY_SCREENSHOTS) await page.screenshot({path:resolve(process.env.VERIFY_SCREENSHOTS,`launch-v4-explanation-${name}.png`)});
    await page.getByText('Fördjupa jämförelsen',{exact:true}).click();
    await assertNoHorizontalOverflow(page, `${name}: comparison table`);
    await page.getByRole('tab',{name:'Data',exact:true}).click();
    await assertNoHorizontalOverflow(page, `${name}: match data`);
    await page.getByRole('tab',{name:'Historik',exact:true}).click();
    await page.locator('app-market-history').waitFor();
    await page.waitForLoadState('networkidle');
    if(!process.env.VERIFY_API_ORIGIN) assert.equal(await page.locator('.movement-chart polyline').count(),2);
    await page.getByText('Tidigare sparade sannolikheter',{exact:true}).click();
    await assertNoHorizontalOverflow(page, `${name}: chart and history tables`);
    if(process.env.VERIFY_SCREENSHOTS) await page.screenshot({path:resolve(process.env.VERIFY_SCREENSHOTS,`launch-v4-history-${name}.png`)});
    await page.keyboard.press('Escape');
    await page.getByRole('link',{name:'Anpassa tecken',exact:true}).click();
    await page.locator('.builder-row').last().waitFor();
    await page.waitForLoadState('networkidle');
    await assertNoHorizontalOverflow(page, `${name}: coupon builder`);
    await page.goto(url.replace('#/overview','#/analysis'));
    await page.locator('table').waitFor();
    await assertNoHorizontalOverflow(page, `${name}: analysis table`);
    await page.goto(url.replace('#/overview','#/history'));
    await page.reload();
    await page.locator('app-draw-archive').waitFor();
    await page.waitForLoadState('networkidle');
    assert(page.url().includes('#/history'));
    await assertNoHorizontalOverflow(page, `${name}: archive`);
    if(!process.env.VERIFY_API_ORIGIN) {
      await page.getByRole('button',{name:'4969',exact:true}).click();
      await page.locator('.payout-grid').waitFor();
      await assertNoHorizontalOverflow(page, `${name}: archive details`);
    }
    empty=true;
    await page.goto(url);
    await page.reload();
    await page.getByText('Ingen aktuell kupong finns tillgänglig. Försök uppdatera senare.',{exact:true}).waitFor();
    await page.getByText('DATA SAKNAS',{exact:true}).waitFor();
    assert.equal(await page.locator('.optimal-cell').count(),0);
    assert.equal(await page.getByText('DEMO DATA',{exact:true}).count(),0);
    await assertNoHorizontalOverflow(page, `${name}: empty state`);
    assert.deepEqual(errors,[]);
    report.checks.push({viewport:name, width, thirteen_matches:true, no_horizontal_overflow:true, budget_controls_unclipped:true, drawer_tables_and_chart:true, coupon_and_analysis:true, archive:true, hash_route_reload:true, missing_data_never_demo:true, page_errors:0});
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
