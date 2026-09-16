import {writeFileSync} from 'node:fs';
if(process.argv.includes('--development')) {
  writeFileSync('src/deployment.ts',"export const deployment = { apiBaseUrl: '', production: false, hashRouting: false };\n");
  process.exit(0);
}
const api=process.env.API_BASE_URL;
if(!api || new URL(api).protocol!=='https:' || new URL(api).username || new URL(api).password || new URL(api).search || new URL(api).hash) throw Error('Set public HTTPS API_BASE_URL without credentials, query parameters or fragments');
writeFileSync('src/deployment.ts',`export const deployment = ${JSON.stringify({apiBaseUrl:api.replace(/\/$/,''),production:true,hashRouting:true})};\n`);
