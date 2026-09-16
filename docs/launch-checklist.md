# Launch checklist — Prompt 4

Senaste användarbesked: **”Gör allt deploymentklart; jag konfigurerar hosting och secrets.”** READY betyder verifierad leverans i arbetskatalogen, inte att en publik tjänst har driftsatts.

| Launch-item | Status | Underlag / återstående steg |
|---|---|---|
| Persistent Postgresimplementation | READY | Riktigt Postgres 17 testat lokalt, råbytes och snapshots sparade |
| Versionshanterade migrationer | READY | 001 + 002, transaktioner, checksumma, omkörning testad |
| Flytt av befintligt SQLitearkiv | READY | Importverktyg och verklig kopia till isolerad test-Postgres |
| Bookmakerprovider och konsensus A/B | READY | Matchnings-, quality-, fallback-, cache- och provenance-tester |
| Verifierad verklig bookmakerkonsensus | BLOCKED | Kräver användarens `ODDS_API_KEY`; inga live-bookmakers har påståtts |
| Automatisk insamlare utan webbläsare | READY | Verklig CLI-körning med Svenska Spel till Postgres |
| Resultat och payouts | READY | Separata tabeller, komplett facit stoppar fortsatt resultatpollning |
| GitHub Actions insamlingsworkflow | READY | Schema, manuell start, lås, quota, partial-status; syntax kontrollerad |
| Körning i GitHub Actions | NEEDS MANUAL CONFIG | Repository, environment-secrets och aktivering; sedan workflow_dispatch |
| GitHub Pages workflow och routing | READY | Produktionsbygge under repository-prefix, hash/reload testat |
| Publik frontend-URL | NEEDS MANUAL CONFIG | Pages och API_BASE_URL konfigureras av användaren |
| Containerbackend | READY | Byggd och startad med minimal runtime, `/health` och riktig analys testade |
| Publik backend-URL och TLS | NEEDS MANUAL CONFIG | Deploya image till vald host, port 8000 och HTTPS-ingress |
| Permanent molndatabas och backup | NEEDS MANUAL CONFIG | Skapa managed Postgres, kör migrationer, aktivera backup/provåterställning |
| Secrets och CORS | READY | Server-/CI-env, originlista, validering, inga providerkeys i frontend |
| Faktiska produktionssecrets | NEEDS MANUAL CONFIG | DATABASE_URL och ODDS_API_KEY sätts privat av användaren |
| Export till framtida dataset | READY | Konsekvent JSONL-export, manifest, separata input-/resultattabeller |
| Enkel svensk startsida | READY | System, budget, tre insikter, 13 matchkort och förklaringar |
| Mobil, tangentbord och felvyer | READY | Browserkontroller och skärmbilder; saknad data blir aldrig produktionsdemo |
| Aktiv modell och optimizer | READY | Market-policy och optimizer-objective bevarade |
| Publik end-to-end-slutkontroll | NEEDS MANUAL CONFIG | Utför steg 8 i deploymentguiden när hosting och secrets finns |

Exakta steg: [deployment.md](deployment.md). Begränsningar och verkliga mätvärden: [implementation-report-v4.md](implementation-report-v4.md).
