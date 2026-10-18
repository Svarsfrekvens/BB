# Gemensam motor för verksamheterna

Alla verksamheter använder samma importkontroll, solver, oberoende validator och
beständiga jobbhantering. Uppladdningar är underlag, inte automatisk träning:
nya exempel ska leda till granskade kodförbättringar och regressionstester.
Ingen uppladdning ändrar en annan verksamhets beslut eller en sparad profil.

## Gemensamma principer och lokala beslut

`bb.rule_policy` är motorns gemensamma, versionsmärkta principregister
(`bb-shared-principles/1.0`). Både Flora-vägen och den gemensamma vägen använder
samma importerare, solver och oberoende validator. Deras nya körningsresultat
innehåller `rule_policy`: profil-ID, profilkälla, verksamhetskoppling när sådan
finns, faktiskt använda regelvärden, individuella dygnsbryt, planeringsval och
ett fingeravtryck. Principregistret ingår också i motorns kodfingeravtryck;
en gammal beräkning återanvänds inte som resultat av en ny regelversion.

Gemensam metod: bevarade källor, hela arbetstillfällen, separata tidskategorier,
historik över periodgräns, uttryckliga behörigheter, isolerade verksamheter och
separat validering. Lokala värden hämtas från just den granskade profilen och
det aktuella scenariot. Inga Flora-personer, jourtider, dygnsbryt, lokala undantag
eller kostnadssatser flyttas till en annan verksamhet.

### Explicit maxpass i ett planeringsscenario

Ett dokumenterat planeringsval kan anges i en privat profil som
`planning_limits`, eller i `scenario.workspace.unit_rules.planning_limits`:

```json
{
  "max_whole_duty_minutes": 1200,
  "source": "Verksamhetens beslut att pröva ett 20-timmarsscenario",
  "confirmed_at": "2026-10-18"
}
```

1200 respektive 1440 betyder 20 respektive 24 timmar. Ett scenario får skärpa
en profilgräns, men inte höja den. Valet gäller hela arbetstillfällen med start
i planeringsperioden, inklusive fasta och omfördelade pass; inkommande historik
skrivs inte om. Solvern begränsar längden och den oberoende validatorn kontrollerar
resultatet på nytt. Okända eller odokumenterade värden avvisas.

Valet är inte ett avtalsgodkännande. Motorn delar inte automatiskt ett fast
24-timmarspass för att klara en vald 20-timmarsgräns: om underlagets låsningar
hindrar detta blir försöket `INFEASIBLE`, aldrig ett tyst kapat pass. För en fri
20/24-jämförelse behöver kandidatprofilen först medge de granskade alternativen.
Utan uttryckligt val visas `NOT_SELECTED` och det befintliga beräkningskontraktet
bevaras. Profilens gamla `max_reassigned_minutes` gäller bara omfördelning och
redovisas inte felaktigt som ett beslutat max för samtliga pass.

Principerna kan läsas i `/api/engine/capabilities` och i Flora-delen av
`/api/health`. Det är stöd i koden, inte bevis för att arbetsytorna är anslutna.

## Vad som är implementerat

- `GET /api/engine/capabilities`: status för den verifierade arbetsytan.
- `POST /api/engine/jobs`: granska normaliserat underlag, välj rätt profil och köa.
- `GET /api/engine/jobs/{id}`: läs endast samma arbetsytas och användnings körning.
- `bb-input/1.0`: verksamhetsneutralt namn på den befintliga inmatningsstrukturen.
  `flora-bb-input/1.0` stöds för kompatibilitet, med samma explicita koppling.
- Resultatets `provenance.engine_context` dokumenterar verksamhet, profil och
  användning. `automatic_learning` är alltid `false`.

Gamla `/api/flora/jobs` och `/api/optimize` finns kvar med tidigare kontrakt.
De nya skydden och kopplingarna gäller den gemensamma `/api/engine`-vägen.
Lovables befintliga Flora-proxy växlar inte API-väg av denna backendändring.

## Verifierad arbetsyta, separata profiler

Appservern kontrollerar inloggning och verksamhetsbehörighet före varje anrop.
Den sätter `Authorization: Bearer <serverhemlighet>` och `X-BB-Job-Owner`.
Ägarvärdet ska vara det stabila arbetsyte-/organisations-ID som servern har
verifierat, exempelvis `org:<organisationens UUID>`. Webbläsaren får aldrig
bestämma ett betrott owner-värde eller få motorns serverhemlighet.

`BB_ENGINE_REMOTE_ENABLED=1` aktiverar den gemensamma API-vägen för externa
serveranrop. `BB_ENGINE_PROFILE_REGISTRY` anger en privat JSON-fil på servern:

```json
{
  "schema_version": "bb-business-profiles/1.0",
  "workspaces": {
    "org:VERIFIERAT-ID": {
      "business_id": "STABILT-VERKSAMHETS-ID",
      "data_use": "development",
      "profile_path": "/var/data/profiles/verksamhet.json"
    }
  }
}
```

Lägg in en uttrycklig post för varje godkänd arbetsyta. Inga verkliga
organisations-ID eller profiler uppfinns av implementationen. `development`
och `operational` ger olika jobbutrymmen även för samma verksamhets-ID.
En produktionsarbetsyta ska ha en separat granskad driftprofil.

Varje profil har det befintliga formatet `bb-analysis-input-profile/1.0` med
verksamhetens egna personkopplingar, datum, insatsbeslut, tillgänglighetsfönster,
nettomål och regelkonfiguration. Den ska dessutom ha:

```json
{
  "business_id": "STABILT-VERKSAMHETS-ID",
  "data_use": "development",
  "profile_id": "GRANSKAD-PROFILVERSION",
  "review_provenance": {
    "source": "Beslutsunderlag och versionsreferens",
    "reviewed_at": "2026-10-18"
  }
}
```

Detta är bindningsfält, inte en komplett beräkningsprofil. Samma `business_id`
och `data_use` krävs i underlagets `metadata`. Profilen väljs aldrig från en
sökväg, ett namn eller ett profilobjekt som skickas av klienten. Saknad profil
eller felkoppling stoppar just den arbetsytans begäran; Flora används aldrig
som generell reservprofil. Registrerade profiler ligger utanför Git-repot.

## Import och kända begränsningar

Appens import behöver läsa verkliga Medvind-/Sekoia-exporter och normalisera
personer, kunder, tidssegment, behov och källreferenser till BB-kontraktet.
Motorn tar JSON, inte råa XLSX-filer. Nytt filformat kräver en importerare;
den här ändringen implementerar inte en ny Excel-import i Lovable.

Befintliga profilkontroller gäller: nya/ändrade personkopplingar, perioder,
segment-ID, behovs-ID eller semantiska beslut måste granskas innan de används.
Tider och durationer tas från det aktuella underlaget inom profilens granskade
ramar. Profilen får inte innehålla ett gammalt solverresultat som facit.
Det finns ingen automatisk överföring av Floras lokala regler till Galaxen
eller Vintergatan.

Den delade metoden har fortfarande dokumenterade metodbegränsningar: bl.a.
angränsande 28-dagarsperioder, inga DST-skiften i väggtidsmodellen och granskad
behörighet för insatserna. Full dygnsvila, undantagens tillämplighet, praktisk
samplanering, full arbetstidsavräkning och okända periodkanter är fortsatt
öppna kontroller. Gemensamt API betyder inte fullständigt regelgodkännande.

## Render och verifiering

Starta med `cd motor && python -m bb.startup && python -m uvicorn bb.api:app
--host 0.0.0.0 --port $PORT`. Startmodulen försöker köra den befintliga privata
Flora-installationen om den är konfigurerad. Ett fel där stoppar inte andra
verksamheters profiler. Installationsutdata loggas inte. `/` visar liveness;
arbetsytans capabilities visar om dess profil kan läsas. Saknade profiler är
uttryckligen NOT_CONFIGURED, aldrig ett grönt beredskapsbesked.

`tests/test_business_engine.py` kör tre syntetiska verksamheter genom verklig
import, solver, validator och jobbdatabas med samma person-/kund-ID men olika
behov och dygnsbryt. Testerna verifierar separata resultat, profilval,
behörighet, idempotens, ändrade underlag, bevarade profiler och UNKNOWN-status.
Det är regressionstester för gemensam kod; de bevisar inte att tre verkliga
verksamheters produktionsunderlag är verifierade eller anslutna.

## Granskade passkopplingar vid ny underlagsversion

En profilmigrering behöver jämföra faktisk källsemantik, passgränser, raster,
personal, behov och beslut. Byte av rad-ID räcker inte som granskning.
Privata profiler och verkliga källexporter ska fortsatt ligga utanför Git.

En granskad `segment_decisions`-post kan ange `whole_duty_id`, som måste matcha
källradens `sequence_id`. Gruppen ska avse en person och sammanhängande tider.
Solver och oberoende validator använder denna verifierade koppling i stället
för att gissa gruppen från rad-ID:ts suffix. Validatorn läser kopplingen från
det importerade underlaget, aldrig från ett ändringsbart resultatfält.

`model_type` kan explicit normalisera Ar + ARBETE_BRUTTO till AKTIVT_ARBETE och
Jo + JOUR till SOVANDE_JOUR för beräkningen. Kod och kategori måste stödja
översättningen; källraden och dess separata funktionstyp bevaras. Det innebär
inte ett beslut om dagpass, kvällspass eller vaken natt.

När ett redan granskat förslag lämnas som nytt beräkningsunderlag avser
motorns Före-värden just detta underlag. Det får inte märkas som den orörda
ursprungsfilen. Nettoreferenser härleds spårbart från det aktuella underlagets
arbetstid och raster; de är inte ett nytt SSG-beslut. Nya beräkningsresultat
förblir separata förslag och skriver aldrig automatiskt över arbetsytan.
# Re-importing original data alongside an existing proposal

A workspace binding may include `dataset_profiles`, a server-owned map from
an imported `metadata.dataset_id` to an absolute private profile path. The
existing `profile_path` remains the default. This permits a reviewed original
workbook and an earlier reviewed proposal to coexist without replacing the
saved workspace or invalidating access to older jobs.

The dataset ID only selects among profiles registered for the authenticated
workspace. Each selected profile must still match the business and data use,
have review provenance, and pass the complete input review before a job is
queued. No path, foreign business profile, or relaxed validation can be supplied
by an upload. Unknown dataset IDs retain the default profile's strict review.

A profile may carry `reviewed_day_boundaries` with the same validated structure
as `scenario.workspace.unit_rules.day_boundaries`. They are used only when a
fresh import has no such local setting. Explicit overrides, including an empty
object, take precedence. Recording these decisions does not claim a complete
daily-rest validation.
