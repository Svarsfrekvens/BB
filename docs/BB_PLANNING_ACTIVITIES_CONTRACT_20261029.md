# BB: källstyrt aktivitetskontrakt v1 — 2026-10-29

## Besked och versionsgräns

Ett avgränsat motorstöd är implementerat och provat utan solver. Kontraktet är redo för verksamhetsbeslut, men Flora 131 är inte därmed körklar. Ingen faktisk Flora-request, liveprofil eller kunddata har använts i proven. Status för de fem aktuella aktiviteterna nedan utgår från uppgifterna i beställningen.

- Motorbas: `c7170d487d29ee9338014c44a6373e57096cc4c9`.
- Separat lokal gren: `codex/original-motor-plan-activities-20261029`.
- Lästa frontendtyper och flöden: `c815a7fdd11b1b7c22326bbd5cde008284e59a72`.
- Kontraktsversion: `bb-planning-activities/1.0`.
- Avsedd tjänst vid ett senare installationsbeslut: `bemanningsbalans-motor`.
- Exakt leveranscommit och patchhash finns i leveransens `DELIVERY.json`; inga självrefererande commithashar skrivs in i denna rapport.

Ingen push, deploy, merge, frontendändring, profiländring, secretändring, verklig jobbsubmission, verksamhetskörning eller ändring av Flora-arbetsytan har genomförts i detta uppdrag. Endast lokal kod, syntetiska prov och leveransfiler har skrivits.

## 1. Kontrakt: faktisk appinput och motorrepresentation

Appen skickar sin befintliga `settings.activities`-lista. Befintlig `normalize_request` flyttar inställningarna till `scenario.workspace.activities`. Ingen ny request-envelope eller omskrivning av originalunderlaget införs. Namn väljer aldrig beteende.

| Faktiskt frontendfält | Motorfält / hantering |
| --- | --- |
| `id` | `activity_id`, obligatorisk unik, icke-tom sträng |
| `name` | Bevarad text; ingen semantisk tolkning |
| `category` | `kundnara` eller `verksamhet`; ger aldrig automatisk kundtäckning |
| `on` | Måste vara boolesk. `false`: inga förekomster, inga modellposter, 0 aktivitetstid |
| `minutes` | Positivt heltal i minutmodellen. Noll, bråktal och okänt avvisas för aktiv rad |
| `freq` | Bevaras som `frequency`: `per_shift`, `per_customer_week`, `per_customer_month`, `per_week`, `per_month` |
| `occurrences` | Bevaras; positivt explicit antal krävs för aktiv månadsfrekvens. `null` blir aldrig 0 |
| `shift_override` | Bevaras i mottagna värden; icke-null avvisas. Ett manuellt antal är inte passbevis |
| `anchor` | `shift_start` / `shift_end` endast med `per_shift`; alternativ till slots, aldrig båda |
| `person_id` | Null innebär ingen vald person. Ett angivet ID måste finnas och överensstämma med slot. Ankare använder alltid den verifierade passgruppens faktiska person |
| `customer_id` | Angivet ID måste finnas. Null ger ingen konkret kundkoppling i förekomsten. Ingen kund fördelas automatiskt |
| `slots` | Explicit lista av ActSlot; se nedan |
| `strength` | `hard` eller null stöds som obligatorisk kapacitetsreservation. `soft` kräver separat stöd och stoppas, aldrig tyst uppgraderad till hard |
| `competence` | Icke-null fri text stoppas med `COMPETENCE_MAPPING_REQUIRED`. Text får aldrig ge kompetens eller delegation |
| `window_from`, `window_to` på aktiviteten | Bevaras i mottagna värden men stoppas i v1: odaterat fönster är inte en daterad förekomst |

Okända fält på aktiva aktiviteter/slots avvisas. Felaktiga eller dubbla identiteter ger strukturerat fel. Avstängda sparade slots aktiverar aldrig en aktivitet. Enbart OFF-rader skapar ingen `planning_activity_contract` i resultatet. Vid blandad lista redovisas OFF-identiteter separat, utan förekomster.

### ActSlot

Faktiska fält: `id`, `date`, `start`, `window_from`, `window_to`, `minutes`, `person_id`, `customer_id`.

- `id`: unik inom aktiviteten, icke-tom sträng.
- `date`: verkligt kalenderdatum `YYYY-MM-DD` inom periodens tillåtna tidsdomän.
- `minutes`: positivt heltal, slotens uttryckliga varaktighet. Ersätter inte aktivitetens frekvensomfattning eller grundminuter.
- Antingen exakt `start` (`HH:MM`) eller komplett `window_from` + `window_to`. Inte båda. Nollbrett fönster avvisas; `to < from` betyder över midnatt.
- Ett slotfönster är ett **utförandefönster**: hela varaktigheten måste rymmas. Motorns startdomän blir `[fönsterstart, fönsterslut − minutes]`, begränsad av aktivt pass och kända raster.
- Explicit `person_id` krävs på sloten i denna version, även om person finns på aktiviteten. Ingen arvning eller bemanningsgissning.
- Kund får vara null. Angiven kund måste finnas. Om aktivitetens person/kund har angivits måste sloten ha samma bindning.
- Aktiv fast Ar med korrekt person måste stödja hela förekomsten. Jour, rast och enbart teknisk närhet mellan segment ger ingen aktiv kapacitet.
- En slot får inte tyst hoppas över. Om en enda slot saknar stöd nekas dess aktivitet tillsammans med övriga felaktiga aktiviteter.

### Källa, period och profil

`planning_activity_contract.binding` innehåller:

```text
profile_id, profile_hash, business_id, data_use, dataset_id,
source_file_sha256, input_hash, settings_sha256,
period {id, start, end, timezone}
```

Hashfunktionen är SHA-256 över UTF-8 JSON med sorterade nycklar, kompakta separatorer, `ensure_ascii=false`, `allow_nan=false`. `input_hash` avser oförändrat normaliserat källunderlag; `settings_sha256` avser hela mottagna aktivitetslistan. De två får inte blandas ihop. Befintlig request-/idempotenshantering bevaras. Profilhashen beräknas från serverns laddade profilobjekt; klienten väljer ingen ny profil via aktiviteter.

Varje aktivitet har `basis.kind=EXPLICIT_SETTINGS_ACTIVITY`, `basis.path=settings.activities`, `activity_sha256`. Varje förekomst har ett stabilt härlett ID, aktivitetens ID, slot-ID eller verifierat pass-ID, person/kund, minuter, startdomän, underliggande segment-ID och källhash. Kontraktet binder till den importerade källan och beslutade profilen; det påstår inte att befintliga legacy-kontroller är striktare än i motorbasen.

## 2. Vilka former v1 faktiskt stöder

### Ankare i verifierade fasta pass

`per_shift` + explicit ankare skapar en förekomst per verifierad hel passgrupp. Gruppbeviset är källans `sequence_id` som exakt matchar profilens `whole_duty_id`; befintlig import kontrollerar samma person och sammanhängande gruppgränser. Intilliggande klockslag skapar inte bevis.

Varje relevant Ar/Jo-segment för vald person, eller alla personer när person saknas, måste tillhöra verifierad fast grupp. Ett enda osäkert eller omfördelningsbart pass stoppar aktiviteten. Variabla/nya kandidater för samma person stoppar också ankaret. Även källans Ar/Jo-pass utan genererad kandidat kontrolleras mot fasta segment; saknat stöd stoppar ankaret. Därmed utelämnas inga sådana pass tyst från ett påstått fullständigt per-pass-resultat.

Startankare placeras vid gruppens verkliga start. Slutankare placeras `minutes` före gruppens slut. Hela aktiviteten måste stödjas av fast aktiv Ar inom gruppen; ankare i jour/rast eller över periodgräns stoppas. Ingen extra Ar-rad eller längre arbetstid skapas.

### Slots på verifierad fast aktiv tid

Fast källstyrkt Ar kan stödja en slot även när bevis för ett helt pass saknas. Då märks passreferensen `VERIFIED_FIXED_AR_SEGMENT_NOT_WHOLE_DUTY`; den får inte användas som whole-duty-bevis. Omfördelningsbara fasta segment räknas inte som stöd.

Exakta kollisioner mellan aktiviteter för samma person stoppas samlat före jobbhanteraren. För tidsfönster byggs en riktig startdomän, `NoOverlap` med personens aktiviteter/raster och en reservation i motorns befintliga kapacitetspool. Ingen starttid gissas vid import. Modellens allmänna lösbarhet för flera flexibla fönster är **inte** bevisad utan solver.

Oberoende resultatkontroll kräver exakt förväntad förekomstmängd, korrekt person, varaktighet, domän, period och samma stödjande källsegment. Den kontrollerar aktivitet–aktivitet, aktivitet–rast och kvarvarande minutkapacitet för kundbehov. Aktivitetstid ligger kvar som aktiv Ar och i veckotid; den dras enbart från tillgänglig kundutförarkapacitet. Aktiviteter räknas inte som fler täckta behov. Resultatsignaturen inkluderar aktivitetsplaceringarna när sådana finns; legacy-signaturen utan aktiviteter bevaras.

### Omfattning och uttryckliga begränsningar

Appens `activityTotal` skiljer mellan frekvensomfattning och faktiska slots. Det gör även detta kontrakt:

- Ankare: `scope=VERIFIED_FIXED_DUTIES`, `frequency_extent_status=ENUMERATED_VERIFIED_DUTIES`.
- Slots: `scope=EXPLICIT_SLOTS_ONLY`, `frequency_extent_status=NOT_FULLY_PLACED_OR_VERIFIED`.
- En enda veckoslot är **inte** bevis för att fyra veckors frekvensomfattning har planerats. Originalets frequency/occurrences bevaras och den återstående omfattningen anges under `outside_claims`. Ingen implicit återkommande slot genereras.
- Stöd för aktiva aktiviteter finns endast i befintlig Flora-strategi med dessa fasta källbevis. Availability-strategin avvisar aktiva rader samlat med `ACTIVITY_STRATEGY_NOT_IMPLEMENTED`.
- Fri kompetenstext, mjuka önskemål, manuell passräkning, odaterade aktivitetsfönster och rörliga/omfördelade stödpass kräver separat beslut/implementering. De ignoreras inte.
- Kundens egen tillgänglighet/direct-contact-klassning är inte verifierad. Även en explicit kundkoppling är en koppling, inte automatiskt bevis för direkt kundtid.

## 3. De fem aktuella aktiviteterna

| Aktivitet från beställningen | Status i kontraktet | Kvarvarande underlag eller beslut |
| --- | --- | --- |
| read_journal, 10 min, per_shift, shift_start | Formen stöds. Faktisk körbarhet **inte verifierad** | Kräver fullständigt verifierade fasta whole-duty-grupper för berörda personer; ingen gissad gruppering. Rörliga/omfördelningsbara pass stoppar v1 |
| write_journal, 15 min, per_shift, inget ankare/slot | **Blockerad**, strukturerat 422 | Verksamheten väljer ankare eller daterade placeringar/fönster. Namnet innebär inte automatiskt passlut |
| contact_person, 30 min, en slot | Explicit slot stöds villkorat. Den faktiska slotens datum/tider/passbevis har inte tillhandahållits här | Verifiera mottagen slot och fast personkapacitet. Besluta hur oplacerad veckoomfattning ska hanteras; en slot intygar inte hela frekvensen |
| weekly_customer, 60 min, inga slots | **Blockerad**, strukturerat 422 | Daterade slots/utförandefönster och deras underlag behövs; kund/person i sig är inte tidsplacering |
| gp, 60 min, per_customer_month, occurrences=null, inga slots | **Blockerad**, strukturerat 422 | Explicit antal tillfällen, avsedd kundomfattning, person och daterad placering. En månad får inte antas vara 28 dagar |

Ingen av de fem verkliga raderna har automatiskt stängts av eller ändrats. Provets två syntetiska kompletta rader accepteras, och dess tre ofullständiga rader redovisas i samma fel. Detta betyder inte att verkliga read_journal/contact_person redan är validerade.

## 4. Separat resultatkontrakt

Resultatet får ett nytt toppfält `planning_activity_contract`. Befintligt `schedule.interventions`, kundbehov, täckningsnämnare, `need_window_contract` och `placement_domain_contract` används fortsatt för kundbehoven och fylls inte med planeringsaktiviteter.

```text
planning_activity_contract:
  version, frontend_commit, binding
  activities[]:
    activity_id, name, category, minutes, frequency, occurrences,
    shift_override, anchor, person_id, customer_id, slots, strength,
    competence, basis, occurrence_ids, modeled_occurrences,
    total_minutes, scope, frequency_extent_status, outside_claims
  placements[]:
    id, activity_id, slot_id, pass_id, person_id, customer_id, minutes,
    start, end, placement_domain[], pass_evidence[], basis,
    customer_link_status, direct_customer_minutes
  expected_occurrences, placed_occurrences, total_minutes
  disabled_activity_ids, outside_claims
  direct_customer_minutes: null
  included_in_customer_need_coverage: false
  review_required: true
  business_schedule_approved: false
```

Start/slut och startdomäner exporteras med samma tidsstämpelfunktion/tidszon som övriga motorresultatet. `pass_evidence` innehåller källsegment, passreferens, beviskategori och tillåtna starter. Exakt maskinläsbart syntetiskt exempel finns i `checks/synthetic-activity-result.json`. Ingen kunddata ingår.

Aktivitetskontrollen är en separat valideringsregel. Befintliga UNKNOWN för otidsatt stöd/verksamhetsgodkännande görs inte om till PASS genom ett godkänt aktivitetsprov. `direct_customer_minutes=null` får inte presenteras som 0 verifierade minuter eller som kundtäckning.

## 5. Samlat fel före jobbhanteraren

Faktisk FastAPI-envelope: HTTP 422, `detail.code=ACTIVITY_REVIEW_REQUIRED`. Fältlista: `activity_id`, `name`, `missing_fields`, `unsupported_reason`, `received`. `received` är mottagna aktivitetsfält, aldrig servermiljö, token eller profilinnehåll. Det innehåller användarens verksamhetsfält i ett verkligt anrop och ska därför inte läggas i publik logg eller telemetri.

Exempel från det riktiga lokala ASGI-provet, enbart syntetiska uppgifter:

```json
{
  "http": 422,
  "body": {
    "detail": {
      "code": "ACTIVITY_REVIEW_REQUIRED",
      "message": "Aktiviteterna behöver kompletteras före körning; inga aktiverade aktiviteter har ignorerats.",
      "contract_version": "bb-planning-activities/1.0",
      "activities": [
        {
          "activity_id": "write",
          "name": "Syntetisk aktivitet write",
          "missing_fields": [
            "anchor_or_dated_slots"
          ],
          "unsupported_reason": "INCOMPLETE_ACTIVITY",
          "received": {
            "id": "write",
            "name": "Syntetisk aktivitet write",
            "category": "kundnara",
            "on": true,
            "minutes": 15,
            "freq": "per_shift",
            "occurrences": null,
            "shift_override": null,
            "anchor": null,
            "person_id": null,
            "customer_id": null,
            "slots": []
          }
        },
        {
          "activity_id": "weekly",
          "name": "Syntetisk aktivitet weekly",
          "missing_fields": [
            "dated_slots_or_placement_domain"
          ],
          "unsupported_reason": "INCOMPLETE_ACTIVITY",
          "received": {
            "id": "weekly",
            "name": "Syntetisk aktivitet weekly",
            "category": "kundnara",
            "on": true,
            "minutes": 60,
            "freq": "per_customer_week",
            "occurrences": null,
            "shift_override": null,
            "anchor": null,
            "person_id": "person-a",
            "customer_id": "customer-a",
            "slots": []
          }
        },
        {
          "activity_id": "gp",
          "name": "Syntetisk aktivitet gp",
          "missing_fields": [
            "occurrences",
            "dated_slots_or_placement_domain",
            "customer_id_or_explicit_slot_customers",
            "person_id_or_explicit_slot_persons"
          ],
          "unsupported_reason": "INCOMPLETE_ACTIVITY",
          "received": {
            "id": "gp",
            "name": "Syntetisk aktivitet gp",
            "category": "kundnara",
            "on": true,
            "minutes": 60,
            "freq": "per_customer_month",
            "occurrences": null,
            "shift_override": null,
            "anchor": null,
            "person_id": null,
            "customer_id": null,
            "slots": []
          }
        }
      ]
    }
  }
}
```

## 6. Filer och ansvar

| Motorfil | Ändring |
| --- | --- |
| `motor/bb/planning_activities.py` (ny) | Versionskontrakt, samlad förkontroll, källbindning, förekomster/domäner, modellreservation, oberoende validering och export |
| `motor/bb/flora_import.py` | Ersätter första-rad-stopp med full aktivitetsförkontroll efter källstyrd import |
| `motor/bb/availability_import.py` | Fail-closed för aktiva aktiviteter i ännu ej stödd strategi |
| `motor/bb/engine_api.py` | Strukturerat 422 före jobbhanterare |
| `motor/bb/flora_api.py` | Motsvarande förkontroll på legacy-rutten när aktiviteter skickas |
| `motor/bb/flora/optimizer.py` | Bygger personbundna kapacitetsreservationer; exporterade aktiviteter och signatur. Byggt, aldrig löst i uppdraget |
| `motor/bb/flora/arithmetic.py` | Separat kontroll och kapacitetsavdrag före kundutförartäckning; Ar/veckotid bevarad |
| `motor/bb/flora/__init__.py` | Separat valideringsregel och normaliserad aktivitetsexport |
| `motor/bb/flora_jobs.py` | Ny moduls kod ingår i befintligt method_fingerprint; ingen jobblogik ändrad |
| `motor/tests/test_planning_activities.py` (ny) | 31 riktade solverfria aktivitetsprov |
| `motor/tests/run_activity_checks.py` (ny) | Testkörning med hårda spärrar för solver, manager, SQL, subprocess och nätanslutning |
| `docs/BB_PLANNING_ACTIVITIES_CONTRACT_20261029.md` (ny) | Detta kontrakt, beslut, provbevis och installationsplan |

## 7. Testresultat och bevisets gräns

**69 PASS, 0 FAIL, 0 ERROR:** 31 aktivitetsprov + 18 befintliga typed-window-prov + 20 befintliga importprov. Därutöver 12 API-regressionsobservationer, exakt samma status och body som basens sparade kontroll. `checks/test-results.json`, `checks/test-run.log` och `checks/baseline-comparison.json` innehåller utfallet.

| Krav | Resultat |
| --- | --- |
| 10 minuter per verifierad passstart, en grupp med flera segment och flera separata grupper | PASS |
| Ofullständig write_journal, weekly_customer och gp | PASS: alla tre i samma 422 |
| Explicit slot på fast Ar; slot utanför pass, fel person/kund/period eller oklart fönster | PASS: giltig form accepteras, övriga nekas |
| Exakta tider respektive flexibla utförandefönster | PASS: domain bevarad, deterministisk testtid uttryckligen vald i testadapter |
| OFF → 0, ingen aktivitetspost; ingen tyst borttappning | PASS |
| Ingen gissning från namn, shift_override, kompetenstext eller otydliga whole-duty-grupper | PASS |
| Aktivitet belastar kapacitet, skapar inte pass och minskar inte Ar/veckotid | PASS |
| Resultat tappar aktivitet, ändrar person/tid, krockar med rast eller annan aktivitet | PASS: oberoende validator ger FAIL |
| Befintligt need_window_contract identiskt utan kundkontraktsmutation | PASS |
| START_WINDOW och EXECUTION_WINDOW inklusive gränser och motstridiga uppgifter | PASS i befintliga riktade prov |
| Organisations-/profil-/period-/schema-/inputhash-regressioner | PASS för oförändrat kontrakt |
| Positiv aktivitetsrequest | PASS: når nästa förkontroll och stoppas med avsiktligt ogiltig idempotensnyckel före manager |
| Misslyckad aktivitetsförkontroll | PASS: stopp före manager både engine- och legacy-rutt |
| Solver, jobbhanterare, JobStore, SQL-anslutning, subprocess, nätanslutning | 0 anrop i övervakad lokal process |

Viktigt: basens legacy-prov för fil-SHA/dataset/profilpåståenden går vidare till den avsiktliga idempotensspärren. Oförändrade svar är regressionsbevis, **inte** ett påstående att originalmotorn har Fas 1A:s striktare profilspärrar. Availability-importens befintliga source_identity-kontroller provas oförändrade. Inga befintliga säkerhetsregler har utökats eller kringgåtts av aktivitetsstödet.

Ingen faktisk jobbdatabas eller runtime-räknare har öppnats. Nollräknarna avser spärrade funktionsanrop i testprocessen. Ingen faktisk registrering eller verksamhetsskrivning har gjorts. Modellen har byggts och validerats strukturellt; `CpSolver.solve` och alternativa solve-entrypoints var spärrade. Syntetiska resultat kommer från deterministisk testadapter och är inte optimeringsresultat.

Reproduktion från leveranscommitten med motorberoenden installerade:

```bash
python motor/tests/run_activity_checks.py --out /tmp/bb-activity-checks
```

Detta skriver endast testbevis till vald lokal outputkatalog. Frontendens gamla fyra FAIL används inte som aktuell status. Frontend har endast lästs; dess tester/build har inte körts om eftersom ingen frontendkod ändrats.

## 8. Nödvändigt frontendarbete — Lovable

Ingen frontendändring är utförd. Följande är konkreta integrationsbehov i läst commit c815a7f:

1. `src/lib/engine-proxy.server.ts` vidarebefordrar redan HTTP-body/status. Bevara detta och autentisering/organisationsbindning. Ingen ny tokenkoppling behövs.
2. `src/lib/flora/engine-client.ts` (`jobResponse`) och `engine-errors.ts` behöver känna igen `ACTIVITY_REVIEW_REQUIRED` och bära den strukturerade aktivitetslistan vidare. Visa alla berörda rader säkert, inte bara ett generiskt fel. Automatisk avstängning är förbjuden.
3. `src/lib/flora/engine-contract.ts` behöver den versionsbundna `planning_activity_contract`-typen och kontroll av bindning, förekomster, antal, tider, domäner och outside_claims. Saknat/okänt/inkonsekvent kontrakt får inte tyst accepteras när requesten innehöll aktiva aktiviteter.
4. `src/lib/flora/engine-working-copy.ts` / ProposalCopy bevarar i dag kundinterventioner och befintliga behovskontrakt, men kopierar inte detta nya fält. Lägg till separat bevarande och kapacitetskontroll för planeringsaktiviteter. Alternativt blockera skapandet av arbetskopia för sådant resultat tills stödet finns. Bevara vid spara, direktlänk och omladdning.
5. Bevara Dashboard, Kundschema, Medarbetarschema, Före & efter, navigation, kundbehovs-KPI, historiska D1-flöden, design och övriga beviskedjor. Aktiviteter får inte stoppas in i kundbehovslistan för att få dem att synas.
6. Appens `shiftGroups` grupperar berörande Ar/Jo för beskrivande omfattning. Det är inte motorprofilens verifierade whole-duty-bevis. Visa skillnaden och använd inte UI-grupperingen som ersättning för käll-/profilbevis.
7. Skilj frekvensomfattning från `EXPLICIT_SLOTS_ONLY`. Visa kvarstående omfattning som ej verifierad, inte som fullständigt planerad.

Efter sådant separat frontendmandat behövs riktade tester för alla felrader, kontraktsbevarande/parser, aktiviteter separata från behov, source/profilbindning, slotkollisioner, arbetsschemakopia, omladdning, OFF/null samt befintliga typed-window-, gateway- och engine-working-copy-regressioner. Ingen ny frontenddesign behövs.

## 9. Installations- och rollbackplan — EJ GENOMFÖRD

1. Fatta verksamhetsbeslut för de ofullständiga aktiviteterna, frekvensomfattningen och vilka verifierade fasta pass som får omfattas. Verifiera faktiska slots och passunderlag läsande. Om v1:s fasta-pass-avgränsning inte passar: stoppa och besluta separat utökning, inte tyst exkludering.
2. Lovable inför eller uttryckligen blockerar hantering av det nya resultatkontraktet enligt ovan. Verifiera app-/motorintegration solverfritt före installationsbeslut.
3. Vid separat godkännande: verifiera aktuell deployment/commit för originaltjänsten, köstatus, miljö och befintlig profilbindning. Förväntad kodbas är c7170d4. Om faktisk bas avviker behövs ny granskning; denna leverans har inte verifierat liveinstallation.
4. Publicera först då exakt lokal leveranscommit på dess separata gren, utan rebase, squash eller merge. Läs tillbaka SHA och patchfiler från GitHub.
5. Ta referens till föregående godkända deployment och dess miljö innan installation. Återställningskandidat för denna patch är `c7170d487d29ee9338014c44a6373e57096cc4c9`, endast om den verifierats som faktisk godkänd föregångare. Ingen databas-/profilschemamigration eller ny secret krävs.
6. Installera efter uttryckligt mandat exakt leveranscommit på befintlig `bemanningsbalans-motor`; bevara profiler, tokens, databaser, jobbrutter, resurser och skala. Ingen ny tjänst.
7. Verifiera livecommit, health/capabilities, oförändrad profil/hash och befintliga rutter. Gör endast uttryckligt godkända solverfria förkontroller. Ett positivt POST får inte skickas förbi manager utan separat jobbmandat.
8. Stoppa vid fel commit, ändrad profilbindning, tappat aktivitetskontrakt, förändrad behovstäckningstolkning, oväntade jobb eller felaktig förkontroll. Vid separat rollbackmandat återställ exakt föregående godkända deployment/commit; ingen rensning, databasåterställning, secretrotation eller ändring av arbetskopior ingår.

Kvarvarande blockerare för verksamhetskörning: verksamhetsbeslut enligt tabellen, faktiskt pass-/slotbevis, Lovables nya resultat-/felhantering och separat installations-/körmandat. Lokal kontraktsleverans är inte ett drift- eller körgodkännande.

AKTIVITETSKONTRAKT REDO FÖR VERKSAMHETSBESLUT
