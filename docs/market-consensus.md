# Live bookmakerkonsensus och jämförbarhet

Aktiv policy är oförändrad: **market**, alltså `P_model = P_market`. Folkets rörelse, nyheter och medianvarianten ändrar inte prognosen.

## Källa och matchning

Implementationen använder [The Odds API v4](https://the-odds-api.com/liveapi/guides/v4/), ligavis `GET /v4/sports/{sport}/odds`, med `markets=h2h`, decimalodds, ISO-tider och region `uk` som konfigurerbar standard. E0/E1/E2 mappas centralt till `soccer_epl`, `soccer_efl_champ` och `soccer_england_league1`; se [providerlistan över sporter](https://the-odds-api.com/sports-odds-data/sports-apis.html). Providergränssnittet stödjer även enskilda events.

Varje liga hämtas en gång per uppdatering. Kanoniska hemma-/bortalag måste matcha i rätt ordning, sport/competition måste stämma och kickoff får skilja högst 15 minuter. Exakt ett kandidat-event med provider-ID krävs. Okända alias, motsägande identiteter och flera kandidater ger `MARKET MATCH UNRESOLVED`. Ingen fuzzy ensamträff accepteras.

## Två definitioner

För varje bookmaker sparas kompletta 1/X/2-decimalodds och `p_k = (1/o_k) / Σ_j(1/o_j)`.

**A, aktiv standard:** beräkna aritmetiskt medel av varje utfalls decimalodds över godkända bookmakers. De-vigga sedan dessa tre medelodds. Det är A som används till `P_market` när kvaliteten räcker.

**B, diagnostik:** ta medianen per utfall av bookmaker-normaliserade sannolikheter. Normalisera medianvektorn till summa ett. B sparas parallellt och påverkar inte optimizer/prognos.

Kvalitet innehåller bookmakerantal, standardavvikelse per sannolikhetsutfall, äldsta/nyaste bookmakeruppdatering och en deterministisk coverageklass. Standardkravet är minst tre olika bookmakers; konfiguration tillåter inte färre än två. Alla tre odds måste vara ändliga tal större än 1 och högst 10 000. Ofullständig 1X2, dubbletter, framtida eller mer än sex timmar gamla bookmakeruppdateringar utesluts. Betfair exchange-varianter och Matchbook utesluts; ingen börsvolym blandas med bookmakerodds.

## Fallback och ålder

1. Giltig konsensus hämtad inom 30 minuter, utan senare providerfel: `bookmaker_consensus`.
2. Senast giltiga konsensus upp till sex timmar gammal, eller vid senare providerfel: `cached_consensus`.
3. Observerade odds i aktuell Svenska Spel-kupong: `svenska_spel_odds`.
4. Giltiga registrerade manuella odds för samma match: `manual`.
5. Annars `unavailable`, vilket blockerar fullständig systemanalys.

Tiderna är policygränser, inte en garanti att bookmakerpriser alltid är aktuella. Även en aktuell hämtning kan innehålla äldre bookmakerpriser; äldsta/nyaste källtid sparas och visas separat. Matchidentiteten kontrolleras även vid återanvändning av cache. Svenska Folket används aldrig som ersättning för odds.

## Provenance och point-in-time

Rå respons sparas före parsning. I Postgres ligger bytes i `provider_raw_blobs`, adresserade med SHA-256. Ledger `odds_requests` innehåller provider, nyckelfri endpoint med queryinställningar, liga, event-ID vid eventanrop, requested/retrieved UTC, HTTP-status, schemautfall, antal events och quotaheaders. Om en felrespons återger nyckeln maskas just nyckeln före lagring och `credential_redacted` blir true. HTTP-bibliotekens URL-loggning är avstängd för dessa anrop.

Även misslyckade requests sparas. Cache är fem minuter per liga/endpoint/region, inklusive misslyckade försök. Anslutningsfel, 429 och tillfälliga serverfel har högst två försök med begränsad paus. Lägg inte till fler regioner utan att bedöma kontots anropsbudget; providerredovisad quota lagras för uppföljning.

`consensus_snapshots` sparar A/B, medelodds, kvalitet, provider-event, råreferens, request-ID, fixture-identitet och alla tider. `bookmaker_observations` sparar varje godkänd bookmakers odds och sannolikhet. Marknadsförändring sedan föregående/första snapshot sparas; crowd/market-grafen jämför observerade tidsserier över gemensamt intervall och tillskriver inte nyheter en orsak.

Prognoser innehåller exakt crowd-/market-ID, fullständiga indata och modellmetadata. System innehåller prognosset, budget, profil och optimizer-version. Val vid tid T kräver recorded/retrieved/source-tider ≤ T; facit lagras separat och får inte bli prognosfeature. Historiska slutstreck som hämtas i efterhand bakdateras inte.

## Skillnader mot Football-Data

Projektets historiska primära marknadsfält är Football-Data `AvgH/AvgD/AvgA`; tillgängliga fallbackkolumner och opening/closing-separation beskrivs i README. Live-A har samma matematiska form: genomsnittliga decimalodds, sedan de-vig. **Det gör inte populationerna identiska.**

Liveurvalet är de bookmakers som den valda API-regionen returnerar och som passerar våra kvalitetsfilter. Antal och namn kan variera mellan liga, match och hämtning. Sex timmars bookmakergräns, exchangefilter och hämtningstid påverkar urvalet. Historiskt leverantörsurval, publiceringstid och täckning kan skilja sig. Det finns därför ingen verifierad identitet mellan livekonsensus och Football-Data-genomsnittet, och historiska modellresultat bevisar inte liveavkastning.

Vid lokal launchverifiering saknades `ODDS_API_KEY`: **noll verkliga bookmakerobservationer och noll livekonsensus**. Samtliga 13 aktuella matcher använde riktiga Svenska Spel-odds som märkt fallback. Tre bookmaker-fixtures per match används endast i tester, i isolerade databaser. Ett verkligt bookmakerurval och numerisk jämförelserapport måste samlas efter att användaren konfigurerat nyckeln.
