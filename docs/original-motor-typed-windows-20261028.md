# Typade behovsfönster – avgränsad motorpatch 2026-10-28

Motorpatchen korrigerar START_WINDOW och exporterar appens befintliga fönsterkontrakt. Giltigt syntetiskt motorresultat accepteras av båda provade frontendvägarna. Installationsgrinden är ändå **INTE REDO**: fyra negativa prov visar att frontendens `engineWorkingCopy` accepterar motsägande fönsterkontrakt när `placement_domain_contract` saknas. Frontend har inte ändrats.

## Identiteter och omfattning

- Bascommit: `95b54487192bc76a11008044a78cb9052875a058`.
- Separat lokal motorgren: `codex/original-motor-typed-windows-20261028`.
- Frontend läst och provad oförändrad på `585c3a12356dc5e3a05f6a00d4f6cf2dc3f3950d`.
- Målservice för ett senare installationsbeslut: `bemanningsbalans-motor`, `https://bemanningsbalans-motor.onrender.com`.
- Tidigare verifierad live deployment: `dep-dbchmnlg1s2s73bl2t10`, på bascommit ovan. Den har inte ändrats eller verifierats om av denna lokala patchkontroll.
- Patchens slutcommit och SHA för patchfilen redovisas i leveransens `LEVERANS.json` respektive `SHA256SUMS`.

Inga verksamhetsfiler har använts. Testdata är uppdiktade, även där befintliga syntetiska testhjälpare återanvänds. Ingen serverprofil, frontendfil, databas eller Render-inställning har ändrats. Ingen deployment, solver, verklig jobbsubmission, registrering eller publicering har gjorts. Lokala HTTP-prov kördes mot ASGI i minnet, med jobbhanterare och solver spärrade.

## Rotorsak och exakt semantik

Båda motoradaptrarna behandlade den högra fönstergränsen som senaste **avslut**, oavsett explicit typ. Importen krävde att durationen rymdes i fönstrets bredd. Startdomänen slutade vid `fönsterslut - duration`. Oberoende validering följde samma utförandefönstertolkning. Normaliserat resultat saknade dessutom `need_window_contract` och motsvarande fält på interventionerna.

| Fall | Tidigare | Patch |
| --- | --- | --- |
| START_WINDOW, vänster L, höger R, duration D | L ≤ start ≤ R−D | L ≤ start ≤ R, avslut = start+D |
| EXECUTION_WINDOW | L ≤ start och avslut ≤ R | Oförändrat; L ≤ start ≤ R−D |
| Duration längre än startfönstrets bredd | Nekades | Tillåts för START_WINDOW om övriga begränsningar uppfylls |
| Helt otypat äldre underlag | Befintlig profil-/utförandefönsterlogik | Bevarad; ingen typ eller nytt kontrakt hittas på |

Båda startgränserna är inklusiva. Utförandeintervall och planeringsperiod är halvöppna. Hela den typade insatsens duration ska rymmas i planeringsperioden; senaste start begränsas därför också av `periodslut - duration`. Det ändrar inte källfönstrets exporterade gränser. Positiv heltalsduration och positiv fönsterbredd krävs, i linje med appens kontroller. Ett nollbrett startfönster får alltså inte automatiskt bli ett nytt accepterat format.

Flora-adaptern behåller lokal väggklocka i hela minuter från periodstart. Availability-adaptern behåller absoluta tidsminuter. Exporten använder periodens tidszon och ISO-tid med offset. Prov omfattar Stockholm vintertid (+01:00), sommartid (+02:00), UTC till lokal tid, dygnsövergång och periodens sista möjliga start. Detta är inte ett bevis för alla DST-övergångar eller en ny tidszonsimplementation.

En uttrycklig typ får komma från källan eller den redan granskade profilen. Två motstridiga uttryckliga typer nekas. Profilen väljs fortfarande på servern. Befintlig flexbegränsning får begränsa en typad startdomän, men inte i tysthet vidga källfönstret. Äldre helt otypad flexhantering är bevarad.

Flora-modellen använder redan de importerade startdomänerna och hela insatsintervall; optimizerkoden behöver därför inte ändras. Availability-modellens heltalsdomän och stödpruning får den rättade senaste starten. Båda oberoende validatorvägarna skiljer mellan start- och utförandefönster. Modellbygge har provats; ingen sökning har körts.

## Filer i motorpatchen

| Fil | Ändring |
| --- | --- |
| `motor/bb/need_windows.py` (ny) | Gemensam explicit typkontroll, fullständighetskontroll, startgränser och exakt exportformat. |
| `motor/bb/flora_import.py` | Typad import, START_WINDOW-domän, periodgräns och bevarat källfönster; legacylogik separat. |
| `motor/bb/flora/__init__.py` | Kontroll av importerad domän mot källfönster; kontrakt och interventionsfält i faktisk normalisering. |
| `motor/bb/flora/arithmetic.py` | Oberoende kontroll mot typat källfönster även om modellens numeriska domän skulle vara fel. |
| `motor/bb/availability_import.py` | Explicit typ från källa/granskad profil, källvärdeskontroll och inga dolda typade tidsöverlägg. |
| `motor/bb/availability/model.py` | Rätt senaste start, periodklippning och kandidatstöd för START_WINDOW. |
| `motor/bb/availability/validator.py` | Separat start-/utförandefönsterkontroll samt kontroll av typade källgränser och period. |
| `motor/bb/availability/__init__.py` | Kontrakt och interventionsfält i faktisk resultatexport, även kontraktsrader för oplacerade behov. |
| `motor/bb/flora_jobs.py` | Tar med nya hjälparfilen i metodfingeravtrycket. Jobb-/idempotenslogiken ändras inte. |
| `motor/tests/test_typed_windows_contract.py` (ny) | 18 riktade, syntetiska tester. |
| `motor/tests/run_typed_windows_checks.py` (ny) | Spärrad testkörning, syntetiska ASGI-prov och export av maskinläsbart bevis. |
| `motor/tests/frontend_typed_windows.mts` (ny) | Extern kontroll mot oförändrad frontend, positiva prov och avsiktligt korrupta kontrakt. |
| `docs/original-motor-typed-windows-20261028.md` (ny) | Detta granskningsunderlag. |

## Exakt exporterad kontraktsform

Följande kommer från motorns riktiga import, validator och normalisering av ett syntetiskt behov. Starten 09:20 och avslutet 10:20 accepteras med START_WINDOW 09:00–09:20 och duration 60.

```json
{
  "need_window_contract": {
    "version": "bb-need-window/1.0",
    "needs": [
      {
        "need_id": "source-need",
        "window_semantics": "START_WINDOW",
        "source_window_start": "2027-01-04T09:00+01:00",
        "source_window_end": "2027-01-04T09:20+01:00",
        "duration_minutes": 60,
        "personnel_count": 1
      }
    ]
  }
}
```

Varje tillhörande `schedule.interventions[]` innehåller samma fem fönster-/duration-/personalfält, tillsammans med befintliga `need_id`, `person_id`, `start`, `end`, `customer_id` och `source_ref`.

Frontenddefinitioner på angiven commit:

- `src/lib/flora/engine-contract.ts:49`: exakt `EngineRun.need_window_contract` och interventionsfält på rad 46.
- `src/lib/flora/proposal-copy.ts:30`: motsvarande sparat kontrakt `need_windows`.
- `src/lib/flora/proposal-transfer.ts:174`: komplett behovslista, version och bindning till källbehov; rad 214: placeringens bindning till kontraktet.
- `src/lib/flora/engine-working-copy.ts:95`: krav på kontrakt för typade behov; rad 98: villkorad källkontroll.
- `src/test/window-semantics.test.ts` och `src/test/placement-domain-binding.test.ts`: befintliga typ-/överförings-/domänprov som lästs.

Kontraktsraden kräver inget separat `basis`- eller undantagsfält. Befintliga `source_ref` och result/profil-proveniens bevaras; nya fält eller undantag uppfinns inte. `placement_domain_contract` är ett annat, separat kontrakt och läggs inte till för att kringgå den konstaterade parserbristen.

Appens v1-kontrakt kräver alla behov i planeringsperioden när kontraktet finns, även oplacerade. Blandat typat/okänt underlag stoppas därför före sökning om inte redan granskad profil ger en explicit typ för varje behov. Okänd betydelse omvandlas inte till EXECUTION_WINDOW. Detta är en avsiktlig säker avgränsning, inte bevis för att godtyckliga blandade arbetskopior stöds.

Typade availability-behov med beslutade överlägg som ändrar källfönster, duration eller personalantal stoppas: denna patch exporterar källkontraktet, inte ett nytt undantagskontrakt. Äldre otypade överlägg är oförändrade.

## Genomförda prov

| Kontroll | Resultat | Bevis |
| --- | --- | --- |
| Nya motorprov | 18 PASS, 0 FAIL | `checks/python-checks.json` och testfilen |
| Befintliga rena importregressioner | 20 PASS, 0 FAIL | Samma runner: `test_flora_import.ImportTest` |
| API-kontrakt mot bascommit | 12/12 identiska HTTP-/felutfall | `checks/baseline-comparison.json`, båda `python-checks.json` |
| Statusformat | queued/running/succeeded/failed bevarade | Minnesrader genom `JobStore.public` på bas och patch |
| Riktiga exporter mot oförändrad frontend | 18 PASS, **4 FAIL** | `checks/frontend-checks.json` |
| Solver, jobbhanterare, jobbskapande, SQL och nätanslutning i Pythonproven | 0 anrop | Runnerns explicita spärrräknare |
| Frontendens nätanrop och lagringsanrop | 0 anrop | Frontendharnessens spärrräknare |

`UNKNOWN`, `review_required=true` och `business_schedule_approved=false` bevaras. PASS i en kontraktskontroll är inte ett godkänt schema. Syntetiska jobbkuvert och frontendobjekt skapas endast i testminne; inget faktiskt jobb, ingen arbetskopia i appen och ingen sparning genomförs.

API-provens begränsning: de körs i minnet, inte på driftsatt motor. En avsiktligt ogiltig idempotensnyckel stoppar korrekt kropp efter förkontroll och före jobbhanteraren. Organisationsfel ger 422/BUSINESS_MISMATCH, data_use 422/DATA_USE_MISMATCH, periodfel 422/INPUT_REVIEW_REQUIRED, okänt schema 422 med befintlig text och saknad autentisering 401. Fel serverprofilbindning redovisas som 200/NOT_CONFIGURED/PROFILE_BINDING_MISMATCH på capabilities, oförändrat från basen.

Flora-basens prov för fel klientfil-SHA, dataset och klientens profil-/hashanspråk når den avsiktliga idempotensspärren. De är **inte** bevis för strikt avvisning av dessa metadata. Samma utfall finns på bascommit. Patchen ändrar inte den äldre säkerhetsmodellen. Availability-adapterns befintliga bindning av fil-SHA, dataset, period och källidentitet har separata negativa prov. Ingen ny säkerhetsgren har installerats eller blandats in.

## Kvarvarande frontendavvikelse och ägare

Utan `placement_domain_contract` accepterar `engineWorkingCopy` följande ändringar i ett annars oförändrat giltigt kontrakt:

| Ändring i `need_window_contract.needs[0]` | Förväntat | Faktiskt jobbparser | Filförhandsgranskning |
| --- | --- | --- | --- |
| window_semantics: START_WINDOW → EXECUTION_WINDOW | Nekas | **Accepteras** | Nekas |
| source_window_start: 09:00 → 08:00 | Nekas | **Accepteras** | Nekas |
| duration_minutes: 60 → 59 | Nekas | **Accepteras** | Nekas |
| personnel_count: 1 → 2 | Nekas | **Accepteras** | Nekas |

Saknat kontrakt, fel version, saknad behovsrad, dubbel behovsrad och okänd typ avvisas i båda parservägarna.

Rotorsaken är att källjämförelsen i `engine-working-copy.ts:98–109` ligger under `if (domains)`. `validateProposalCopy` kontrollerar delar av formen men gör inte den saknade fullständiga jämförelsen mellan källbehov, kontraktsrad och placering när domänkontraktet saknas.

**Ägare: Lovable.** Minsta nästa rättning är att kontrollera källbehov ↔ need_window_contract ↔ intervention oberoende av det valfria placeringsdomänkontraktet. Domänspecifika kontroller ska fortsatt ligga separat. Återanvänd om möjligt den rena käll-/placeringskontrollen från filöverföringen. Inget behov av ändrad design, ny arbetskopia eller sänkt överföringsspärr. Ingen sådan frontendrättning ingår här.

## Reproduktion utan solver

Från motorgrenens rot, med projektets Pythonberoenden installerade:

```bash
PYTHONDONTWRITEBYTECODE=1 python motor/tests/run_typed_windows_checks.py --out /tmp/bb-window-checks
```

För jämförelse: kör samma runner med `--probes-only` i en separat arkivkopia av bascommit. Testfilen får kopieras till arkivets `motor/tests/`; produktionsfilerna ska vara oförändrade. Jämför `probes` exakt. Alla spärrräknare ska vara noll.

Arkivera frontendcommit till separat katalog. Med frontendberoendena tillgängliga, sätt `APP_ARCHIVE` till arkivet och kör från motorgrenens rot:

```bash
esbuild motor/tests/frontend_typed_windows.mts --bundle --platform=node --format=esm \
  --alias:@app="$APP_ARCHIVE" --alias:@="$APP_ARCHIVE/src" \
  --outfile=/tmp/bb-frontend-windows.mjs
node /tmp/bb-frontend-windows.mjs /tmp/bb-window-checks/synthetic-flora-export.json
```

På den nu angivna appcommitten ska det sista kommandot ge exitkod 1 och de fyra redovisade FAIL. Testet ska inte ändras för att dölja dem. Ingen frontendbyggnad, persistens eller verklig motoranslutning krävs för att reproducera avvikelsen.

## Senare riktad verifiering och stopp

1. Lovable rättar den verifierade parserbristen separat. Kör om den externa harnessens 22 kontroller och de befintliga testerna för window-semantics, placement-domain-binding och motorarbetskopia. Samtliga negativa kontraktsprov ska då neka innan någon appskrivning.
2. Besluta om installation först därefter. Den här patchen ger inget installations- eller körmandat.
3. Vid en senare godkänd installation: verifiera exakt livecommit och hälsokontrakt samt att organisation, serverprofil, profilhash och driftinställningar är oförändrade. Kontrollera att metodfingeravtrycket ändrats med koden; idempotenslogiken ska vara oförändrad och gamla resultat får inte återanvändas som nya patchbevis.
4. Kör riktade START_WINDOW-/EXECUTION_WINDOW-/legacyprov på den installerade revisionen i isolerad syntetisk miljö med jobb-/solver-/lagringsspärrar. Verifiera källfält, period, tidszon, status och parserutfall. Inget solverjobb behövs för detta kontraktsbevis.
5. Eventuell verklig sökning, appdataskrivning eller verksamhetskörning kräver ett separat mandat och ingår inte i dessa steg.

MOTORPATCH INTE REDO – frontendens jobbresultatparser accepterar motsägande need_window_contract utan placement_domain_contract (typ, källgräns, duration och personalantal).
