# Lansering: GitHub Pages, container och Postgres

Prompt 4 är förberedd för deployment. Användaren konfigurerar hosting, repository och secrets. Lokal produktionsverifiering är inte en publik lansering. Se [checklistan](launch-checklist.md) och [verifieringsrapporten](implementation-report-v4.md).

## 1. Lägg projektet i ditt GitHub-repository

Fork/klona ett repository med projektfilerna, eller skapa ett nytt repository och lägg in dem. Arbetskatalogen vid denna leverans saknade `.git` och remote. Standardbranch i Pages-workflow är `main`; ändra filtret om din branch heter något annat. Behåll `.gitignore`: miljöfiler, dataarkiv, modellbinärer och exporter ska inte checkas in.

## 2. Aktivera GitHub Pages

Välj **Settings → Pages → Build and deployment → Source: GitHub Actions**. Workflow `.github/workflows/deploy-pages.yml` publicerar `frontend/dist/stryktipset/browser`. Repository-sökvägen kommer från `configure-pages`; produktionsroutern använder hash, exempelvis `https://USERNAME.github.io/REPOSITORY/#/overview`. Refresh på Historik kräver därför ingen serverbaserad SPA-fallback. Se [GitHubs dokumentation om Pages-workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## 3. Skapa persistent Postgres och konfigurera secrets

Välj en vanlig managed Postgres, exempelvis Supabase Postgres. Använd en direkt anslutning eller **session pooling**. Datainsamlarens PostgreSQL advisory locks är sessionsbundna; transaction pooling stöds inte. Extern databasanslutning bör använda leverantörens TLS-inställningar, exempelvis `sslmode=require` i URL:en. Använd leverantörens lösenord och åtkomstkontroll.

Skapa GitHub Environment **production**. Lägg `DATABASE_URL` och `ODDS_API_KEY` som environment secrets där. Samma värden sätts som privata backendmiljövariabler. Undvik environment-regler som kräver manuell granskning av varje schemalagd insamlingskörning.

| Inställning | Backend | GitHub Actions |
|---|---|---|
| `ENVIRONMENT` | `production` | Sätts av insamlingsworkflow |
| `DATABASE_URL` | Privat Postgres-URL | Secret i `production` |
| `ODDS_API_KEY` | Privat The Odds API-nyckel | Secret i `production` |
| `ALLOWED_ORIGINS` | `https://USERNAME.github.io` | Repository variable med samma origin |
| `ODDS_REGIONS` | `uk` som standard | Valfri repository variable, standard `uk` |
| `MIN_BOOKMAKERS_FOR_CONSENSUS` | Standard `3` | Behåll samma värde i collect-workflow om du ändrar det |
| `ADMIN_API_TOKEN` | Valfri privat token för delade skrivningar | Behövs inte av insamlingen |
| `API_BASE_URL` | Behövs inte av API:t | Publik repository variable för frontendbygget |

`ALLOWED_ORIGINS` innehåller origin utan repository-sökväg. Lägg även till eventuell egen frontenddomän, kommaseparerad. Inga jokertecken används. `.env.example` är en mall; Python laddar inte `.env` automatiskt. Varken databas-URL, administratörstoken eller oddsnyckel ska ligga i `API_BASE_URL`, frontendkällkod eller webbläsarlagring.

## 4. Ange frontendens API-adress

Sätt repository variable **API_BASE_URL** till backendens publika HTTPS-adress, exempelvis `https://api.din-doman.se`. Buildskriptet avvisar HTTP, användarnamn/lösenord, query och fragment. Frontend kontaktar endast detta API för data; leverantörsanrop sker på servern.

## 5. Bygg och deploya backend

Från projektroten:

```sh
docker build -t stryktipset-predictor:launch .
```

Deploya bilden på en container-host med privat miljökonfiguration från steg 3, offentlig HTTPS-ingress, containerport **8000** och health path **/health**. Standardkommandot startar Uvicorn utan reload eller URL-baserad accesslogg. Processen körs som användare 10001. Hostingens externa port kan vara valfri; routa till containerport 8000.

För en lokal kontroll med redan satta miljövariabler:

```sh
docker run --rm -p 8000:8000 -e ENVIRONMENT -e DATABASE_URL -e ODDS_API_KEY -e ALLOWED_ORIGINS stryktipset-predictor:launch
```

Produktionsstart kräver Postgres och explicit HTTPS-origin. Historik och råa providerbytes lagras i Postgres; en backendomstart behöver ingen lokal datavolym. Databasfel ger `/health` 503 med ett kort fel utan anslutningshemligheter. Providerproblem redovisas separat; giltiga märkta fallbackdata kan fortfarande användas.

Runtimebilden använder `backend/requirements-runtime.lock.txt`. Aktiv policy är fortfarande **market**, med `P_model = P_market`. Historiska utvärderingsmetadata och en kanonisk laglista finns med som små versionshanterade JSON-filer. Runtime tränar ingen modell och hittar inte på form/Elo när den lokala träningsartefakten saknas. Full utveckling och träning använder `requirements.lock.txt` och befintliga ML-skript. News foundation är oförändrad och ingår inte i denna lanserings permanenta datainsamling.

## 6. Kör migrationerna

Använd en engångsprocess på samma image, med `DATABASE_URL` injicerad privat:

```sh
docker run --rm -e DATABASE_URL stryktipset-predictor:launch python scripts/migrate.py
```

Migrationer `001_draw_archive.sql` och `002_market_collection.sql` körs i ordning, transaktionellt och med checksumma/lås. Befintliga data raderas inte. Kör före första API-/insamlingsstart; appen ändrar inte produktionsschema automatiskt. Ändra aldrig redan applicerade migrationsfiler: lägg till nästa version.

Vill du flytta det befintliga lokala arkivet, kör från `backend` med Pythonmiljön och privata `DATABASE_URL` satt:

```sh
python scripts/import_sqlite_archive.py --source data/stryktipset/stryktipset.sqlite3
```

Detta är en initial migration, inte tvåvägssynk. Källans SQLite öppnas read-only, snapshot-ID och verkliga observationstider bevaras och råa filer kopieras till Postgres. En omkörning hoppar över redan kopierade identiteter. Fortsatt insamling ska sedan ske till mål-Postgres.

## 7. Aktivera och kontrollera Actions

Kör först **Verify**. Kör därefter **Collect live data → Run workflow**, med `force=true` för första kontrollen. Bekräfta att körningen visar aktuell omgång, crowd, market, prediction och optimizer samt att `/health` visar samma senaste run-ID. En saknad oddsnyckel ger `partial` och märkta Svenska Spel-fallbacks, aldrig påhittad konsensus.

Workflow triggas var femte minut med minutoffset 3. Scriptet avgör om ny insamling behövs:

| Tid till spelstopp | Insamlingsintervall |
|---|---|
| Mer än 48 timmar | 6 timmar |
| 24–48 timmar | 2 timmar |
| 6–24 timmar | 1 timme |
| Sista 6 timmarna | 30 minuter |
| Sista 30 minuterna | 5 minuter |

Misslyckad Svenska Spel-hämtning får kontrollerat återförsök efter fem minuter. Avslutade omgångar utan komplett facit kontrolleras oberoende av prematchintervall. Kompletta resultat stoppar vidare resultatpollning för den omgången. API-uppdateringar har också cache, minimiintervall och databaslås.

GitHub garanterar inte exakt schemastart: körningar kan försenas eller utebli vid hög belastning. Scheman körs på defaultbranch, och publika inaktiva repositories kan få schemat avstängt. Kontrollera Actions regelbundet eller kör samma CLI från hostingens scheduler med övervakning. Pre-close betyder senaste giltiga kompletta observation/system **före** spelstopp, inte en garanterad exakt minut. Se [GitHubs schedule-regler](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## 8. Publicera frontend och kontrollera produkten

Kör **Deploy GitHub Pages → Run workflow**. Öppna URL:en i workflowresultatet. Kontrollera 13 matcher, spelstopp, Svenska Folket, källa och ålder för oddsen, budgetbyte, matchförklaring, Historik samt reload av `#/history` på mobil. Utan komplett data ska ingen rekommenderad rad visas; produktion faller aldrig tillbaka till DEMO.

Med oddsnyckeln på plats: kontrollera verkliga bookmakerantal, matchningsfel, sparade konsensus-A/B och quota i `/health`, matchens Data/Historia och databasen. Slutlig bookmakerverifiering kan endast göras efter detta steg; testfixture-bookmakers är inte livebevis.

## Export, backup och drift

Från backendmiljön med `DATABASE_URL` satt:

```sh
python scripts/export_live_dataset.py --output exports/launch-check
```

Exporten läser en konsekvent databassnapshot och separerar crowd, marknad, bookmakerobservationer, predictions, systems, resultat, payouts och request-ledger i JSONL. Manifestet innehåller UTC-tid, schemaversion och radantal. Välj en ny exportkatalog varje gång. Råbytes refereras via hash; full backup kräver Postgresbackup inklusive `provider_raw_blobs`.

Använd managed backups och provåterställning. Med PostgreSQL-klient kan en full logisk backup göras med `pg_dump --format=custom --file=stryktipset.backup` och återställas med `pg_restore --no-owner --dbname=<tom-testdatabas> stryktipset.backup`; konfigurera anslutningen privat med klientens miljö/servicefil, inte med lösenord i kommandot. Återställ först till en separat tom testdatabas och kontrollera migrationsversion, antal och rådatahashar.

Följ `/health`, Actions-fel och oddsproviderns quota. SQL/API-diagnostik hör till driftvyn, inte startsidan. Aliasändringar i produktion görs i versionshanterad `backend/app/team_aliases.json` och redeployas. Delade manuella odds kräver serverns administratörstoken; publik frontend visar inte denna skrivfunktion.
