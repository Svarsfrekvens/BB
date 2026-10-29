# Joint-method: exakt källbevis — 2026-10-29

## Besked

En isolerad motorrättning exporterar ett komplett `source_basis` för `joint-shifts-breaks-needs/v1` när hela indatan och originalfilens checksumma matchar serverprofilens granskade bindning. Rå exporterad JSON accepteras av frontendens faktiska funktioner i `69cfd6a476742713488a45e46bb33486ec7a3cd9`, utan fältöversättning.

**Kodrättningen är klar lokalt. Liveblockeraren är inte stängd:** den konfigurerade originalprofilen saknar en fullständig indatapin. Profilnamn och workbook-hash bevisar inte att en ändrad arbetskopia är original. Ingen sådan pin har gissats eller installerats i uppdraget.

## Versioner och avgränsning

- Direkt motorbas: `c7170d487d29ee9338014c44a6373e57096cc4c9`.
- Separat gren: `codex/original-motor-source-basis-20261029`.
- Frontend läst och testad oförändrad: `69cfd6a476742713488a45e46bb33486ec7a3cd9`.
- Aktivitetspatch `c5148cb54feba0e98c405c2dde883fb3a71307c2` ingår inte. Ingen aktivitetsmodul eller reservation tillagd.
- Exakt lokal leveranscommit, filhashar och patchverifiering finns i `DELIVERY.json`.
- Inga frontendfiler, affärsregler, jobb-/solverlogik eller befintliga resultat ändras.
- Ingen push, merge, deploy, solver, faktisk jobbsubmission, profiländring, databasändring eller secretändring.

## Varför enbart ett nytt exportfält inte räcker

Flora-importörens befintliga `segment_decisions.expected` och behovsbeslut granskar identiteter och semantik, men tillåter ändrade tider och durationer. Det befintliga importtestet `test_uploaded_values_and_generic_period_ids` visar detta uttryckligen. Fil-SHA som appen för vidare från originalarkivet kan fortfarande vara samma när arbetskopians rader ändras.

Read-only GET av originaltjänstens Render-konfiguration visade att `flora-morning-plan-profile.gz.b64` saknar full inputpin/source_identity. Den installerande koden och `flora-historical-pass-overlay-20261021.json` lägger till historiskt profil-ID och whole-duty-ID:n; de tillför ingen full indatapin. Profilens `source` innehåller en workbook-hash och en hash för ett annat numeriskt case. Dessa är inte hash för appens kompletta normaliserade input. Ingen av dem får återanvändas som sådan.

Detta är observation av konfigurationen via Render API, inte nytt bevis från faktiskt monterad runtimefil. Inga privata profiler eller payloads bifogas leveransen.

## De två ändrade motorfilerna

### `motor/bb/flora_import.py`

Efter befintlig full import/förkontroll byggs källbeviset endast om serverprofilen innehåller `reviewed_input_sha256`.

Bindningen är:

```text
reviewed_input_sha256 = SHA-256(
  UTF-8(JSON(normaliserat input utan source_archive,
            sort_keys=true, separators=(",", ":"),
            ensure_ascii=false, allow_nan=false))
)
```

Det är samma algoritm/indatascope som `integration.input_sha256`. Hela indatan ingår, inklusive metadata, perioder, dataset, organisation/användning när de finns, källsegment, behov, otidsatta rader och andra kvarvarande inputfält. Radordning bevaras och ingår i denna exakta pin. Requestens körbudget och scenarioinställningar utanför `input` ingår inte och förblir separat provenance. Detta är inte availability-metodens projekterade source_identity-algoritm.

Dessutom måste:

- mottaget `metadata.source_file_sha256` vara en giltig 64-teckens SHA-256,
- serverprofilens befintliga `source.raw_workbook_sha256` vara giltig,
- dessa två hashvärden vara identiska.

Saknad full inputpin ger inget verifierat `source_basis`; tidigare profilbeteende bevaras, och frontendens spärr ligger kvar. En konfigurerad men ogiltig/motstridig pin, eller saknat/motstridigt filbevis vid konfigurerad pin, ger förkontrollfel före jobbhanteraren (`422 INPUT_REVIEW_REQUIRED` i engine-rutten). Klientens metadata kan inte tillföra serverpinnen eller låsa upp certifikatet.

Källsegment hämtas från importens orörda råa `schedule_segments`, **före** scenarioförkortningar, ersättningspass, solverplaceringar eller filtrering till fasta/importerade referenspass. Därför bevaras också P1, frånvaro och källrader som inte ingår i resultatets arbetsschema.

### `motor/bb/flora/__init__.py`

Resultatexporten kopierar importens verifierade bevis och kontrollerar först att snapshotens fullständiga hash fortfarande matchar. Resultatändringar får inte ändra originalbeviset. Exporten tillför endast `source_basis`; övriga resultatfält har jämförts identiskt med samma valideringsunderlag.

```ts
source_basis: {
  kind: "VERIFIED_UPLOADED_ORIGINAL";
  verification: "EXACT_SERVER_REVIEWED_INPUT";
  source_identity: string;       // exakt serverpin för normaliserat input
  source_file_sha256: string;    // identisk med serverns granskade workbook-hash
  segments: {
    segment_id: string;
    person_id: string | null;
    start: string;
    end: string;
    code: string;               // rå source_code, ingen omklassning
  }[];
}
```

Segmentvärden kopieras direkt; inga genererade pass, profilnamnsheuristiker eller inferred originaltider används. Den nuvarande importörens regler för personreferenser ändras inte av att frontendtypen tillåter null.

Exporten är ett käll-/identitetsbevis, inte ett verksamhetsgodkännande. `review_required=true`, `business_schedule_approved=false` och befintliga UNKNOWN kvarstår. Den gör ingen ny kontroll av Excel-bytes på motorservern: bindningen måste i förväg granskas mot ett betrott original och dess normaliserade projektion.

## Prov och resultat

**52 motorprov PASS, 0 FAIL:** 14 nya riktade källbevisprov, 18 typed-window-regressioner och 20 befintliga importprov.

Nya prov omfattar komplett export, alla originalrader, P1/frånvaro, avsaknad av pin, missvisande profilnamn, klientförsök att skicka pin, ändrade källtider/durationer med samma fil-SHA, ändrat dataset, ogiltiga hashvärden, motstridigt serverfilbevis, muterat snapshot, originaldata som skiljer sig från resultatsegmenten och att bara exportfältet tillkommer.

Ett lokalt ASGI-prov visar att korrekt exakt input passerar importen men stannar vid avsiktligt ogiltig idempotensnyckel före manager; ändrad duration stoppas tidigare med `422 INPUT_REVIEW_REQUIRED`. Därutöver är 12 befintliga legacy-API-observationer identiska med basens status/body. Det senare betyder oförändrat beteende, inte att legacy-profiler fått striktare identitetskontroller utan pin.

**17 frontendkontroller PASS:** verkliga `computationOf`, `proposalOf`, `originalRunBasis` och `engineOriginalChanges` från den exakta appcommitten tar emot rå motor-JSON. Komplett bevis och identiska källrader accepteras. Saknat bevis, ogiltig markering/hash/form, ändrad person/tid/kod/ID, saknad rad och dubblerad rad avvisas. Ingen fältöversättning eller efterhandskomplettering av motorresultatet görs.

Alla uppgifter i proven är syntetiska. En deterministisk befintlig solverfri adapter skapar testschemat. Testernas status-envelope är ett objekt i minnet, ingen jobbpost. Solver-entrypoints, jobbhanterare, SQL, subprocess och nätanslutning var spärrade i motorproven; samtliga räknare är 0. Frontendprovet hade spärrar för nätverk och lagring, också 0. Inga faktiska runtime-/databasräknare har öppnats.

Maskinläsbara bevis:

- `checks/motor-tests.json` och `checks/motor-tests.log`
- `checks/frontend-tests.json` inklusive SHA-256 för den råa exporterade JSON-filen
- `checks/motor-result.json` — exakt syntetisk resultatexport
- `checks/synthetic-input.json` — enbart syntetiskt input
- `checks/baseline-comparison.json`

## Exakt filförteckning

1. `motor/bb/flora_import.py` — villkorad serverbunden källcertifiering.
2. `motor/bb/flora/__init__.py` — separat export av certifikatet.
3. `motor/tests/test_source_basis.py` — riktade negativa/positiva prov.
4. `motor/tests/run_source_basis_checks.py` — solverfri testkörning och exportbevis.
5. `motor/tests/frontend_source_basis.mts` — extern harness mot oförändrad frontend.
6. `docs/original-motor-source-basis-20261029.md` — detta underlag.

## Reproduktion

Med motorberoenden installerade och frontendcommitten extraherad oförändrad till APP_ROOT:

```bash
python motor/tests/run_source_basis_checks.py --out /tmp/bb-source-basis-checks
esbuild motor/tests/frontend_source_basis.mts --bundle --platform=node --format=esm \
  --alias:@app="$APP_ROOT" --alias:@="$APP_ROOT/src" \
  --outfile=/tmp/bb-source-basis-frontend.mjs
node /tmp/bb-source-basis-frontend.mjs /tmp/bb-source-basis-checks
```

## Nästa minsta steg — inte genomfört

1. Läs ut den exakt avsedda normaliserade originalindatan från en betrodd källa och stäm av mot originalfilens bytes/checksumma. En godtycklig senast inskickad arbetskopia får inte automatiskt bli granskad referens.
2. Efter separat mandat: bind den berörda serverprofilen med `reviewed_input_sha256` enligt algoritmen ovan. Verifiera också befintlig `source.raw_workbook_sha256`; byt inte den blint om det är en annan fil. Ingen hash har föreslagits utan detta underlag.
3. Verifiera profilen och rå export solverfritt mot samma frontendcommit. Bevara övriga inställningar, regler och jobbvägar.
4. Först efter installationsmandat: publicera/installera exakt denna separata patch på originalmotorn. Ingen aktivitetspatch får ingå. Säkerställ att faktiskt föregående deployment är godkänd c7170d4 och dokumentera rollback till den samt dess då gällande profilkonfiguration.
5. Befintligt jobb `649630a6ca9e4517bf4da6be65c11902` får inget nytt certifikat bara för att kod deployas. Ingen databaspost eller tidigare resultatexport har skrivits om. Eventuell omexport med bevarat källunderlag eller en ny körning kräver separat beslut; detta uppdrag startar ingen solver.

**Kvarstående blockerare:** fullständigt servergranskat indatabevis saknas i den observerade profilkonfigurationen. Kodändringen ensam får därför inte presenteras som att Excel → gateway → live motor → befintligt resultat → frontend nu är verifierat.
