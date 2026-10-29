# FLORA-RADATA: färdig source_basis och serverprofilbindning

Denna leverans ersätter instruktionen i 04664b6 om `reviewed_input_sha256`. Det fältet används inte. Bindningen följer användarens verifierade `source_identity`-projektion och lägger exakt två fält till den servervalda Flora-profilen.

## Versioner och status

- Gren: `codex/original-motor-source-basis-20261029`.
- Föregående patchcommit: `04664b679e63079d6459cbe526efa8b164c389e3`.
- Motorbas: `c7170d487d29ee9338014c44a6373e57096cc4c9`.
- Kanonisk frontend, läst och provad oförändrad: `ce9668eab9a2e048dd5a7c142fbd28e42ed6d701`.
- Aktivitetspatchen `c5148cb54feba0e98c405c2dde883fb3a71307c2` ingår inte.
- Leveranscommit, publicerad fjärr-SHA, patch och filhashar redovisas i leveransens `DELIVERY.json` efter commit/push.
- Ingen deploy, merge, solver, jobbsubmission, historisk registrering eller databas-/secretändring har gjorts.

## Exakt serverprofil och hur bindningen installeras

Render-konfigurationen lästes med GET. Befintligt register väljer:

```text
service: bemanningsbalans-motor
owner: org:9b4cd08f-82fc-4e40-856a-04ce6dc4ec41
business_id: 9b4cd08f-82fc-4e40-856a-04ce6dc4ec41
data_use: development
dataset_profiles[FLORA-RADATA]:
  /var/data/profiles/flora-historical-pass-reviewed-20261021.json
profile_id: flora-original-upload-morning-plan-historical-pass-20261021
```

Den befintliga profilens bytes återskapades lokalt från den konfigurerade basprofilen och det befintliga historiska passtillägget. Bas-/tilläggskontroller och installerarens förväntade slutchecksumma verifierades. Ingen remote installer kördes.

- Befintlig profilfil SHA-256: `96a2f0e3aca08e15cfd5bd2b107646bf442c870f9113427e8ed84f0d50649eed`.
- Befintligt kanoniskt profilobjekt SHA-256: `49b7fe16d33fa6daffd5e425d37af2ee47350dcd56b433fb2b41a0f6508605ac`.
- Effektivt profilobjekt med exakt två nya fält SHA-256: `0ed6b1aae7b91f8f94d79d2ce30263c45cbfc5b31501f98cc90af9363abdf00a`.

**Inga filer på Render har skrivits om.** Den versionsbundna serverkonfigurationen `motor/bb/flora_source_binding.json` följer med denna kodgren. Vid en senare godkänd installation applicerar `business_profiles.profile_for` tillägget i minnet på exakt den profil registret redan valt. Det effektiva profilobjektet och dess nya profilhash lämnas vidare genom den befintliga jobbvägen. Ingen klient får välja tillägget eller dess värden.

Tillägget ändrar endast:

```json
{
  "source_identity": "0c8fb9635f4a8562fb1b592702c30eb9c955e48937e5ba2f39ac81a6a05390c4",
  "source_file_sha256": "5bd741c2a7f6e9058b32e3d6858b0f8951c1d1816eccd85c3cee1a1f5fd1ca38"
}
```

Hela det övriga profilobjektet måste ha den fastställda basprofilhashen. Ändrade regler, fönster, grupp-ID:n, perioder, underlag eller tidigare motstridiga bindningar stoppar tillägget med konfigurationsfel, aldrig en automatisk ombindning. Redan korrekt tillagd bindning är idempotent. Andra profil-ID:n lämnas oförändrade.

Historiska fält under `profile.source`, inklusive äldre referenskällor, bevaras. Den aktuella exakt godkända filbindningen är det nya toppfältet `source_file_sha256`; en gammal referenskällas workbook-hash återanvänds inte som denna bindning.

## Verifierad motorindata

Den uppladdade filen `flora_3_uppdaterad (2).xlsx` har exakt fil-SHA enligt beställningen. Den konverterades lokalt genom **frontendens faktiska** `xlsxToContract` och `engineInput` från ce9668e. Verksamhets-ID och `data_use` tillfördes som de uttryckligt godkända autentiserade routningsvärdena. Ingen app-/arbetskopieimport utfördes.

Resultatet gav exakt:

```text
business_id = 9b4cd08f-82fc-4e40-856a-04ce6dc4ec41
data_use = development
dataset_id = FLORA-RADATA
planning_period_id = P2
source_file_sha256 = 5bd741c2a7f6e9058b32e3d6858b0f8951c1d1816eccd85c3cee1a1f5fd1ca38
source_identity = 0c8fb9635f4a8562fb1b592702c30eb9c955e48937e5ba2f39ac81a6a05390c4
staff = 9
customers = 5
schedule_segments = 292
customer_needs = 3235
business_rules = 34
vc_answers = 32
```

Samtliga stabila ID:n är unika och giltiga. `source_layout` och `history_period_id` är fortfarande frånvarande, inte tillagda i input.

### Identitetsalgoritm

Samma befintliga `availability_import.source_identity` används för båda motorstrategierna. Projektionen omfattar metadatafälten:

`schema_version`, `dataset_id`, `timezone`, `periods`, `planning_period_id`, `history_period_id`, `source_layout`, `source_file_sha256`.

Saknade fält representeras av JSON null **i hashprojektionen**, utan att originalindatan skrivs om. `staff`, `customers`, `schedule_segments`, `customer_needs` sorteras på respektive stabilt ID; alla radfält följer med. `business_rules` och `vc_answers` följer med i given ordning. SHA-256 beräknas över kanonisk UTF-8 JSON (`sort_keys`, kompakta separatorer, `ensure_ascii=false`, inga NaN).

Routningsfälten `business_id` och `data_use` ingår enligt denna befintliga definition inte i source_identity. De kontrolleras separat mot den autentiserade registerbindningen **och** mot den servervalda profilen vid källcertifieringen. Ett ändrat routningsvärde får därför inte godkännas bara för att source_identity är oförändrad.

Tomma/blankstegs-ID:n avvisas nu också av den gemensamma identitetsfunktionen. Befintligt stöd för sorteringsoberoende identitet bevaras. Det kompletta importerade snapshotet har fortsatt egen `input_sha256` som kontrolleras igen vid export; det värdet förväxlas inte med source_identity.

## Positiv export: exakt source_basis

Den lokala positiva kontrollen använder den verkliga inputen, verkligt registerurval och det kontrollerade serverprofilobjektet med två tillagda fält. Import och normalisering passerar utan solver.

```text
kind: VERIFIED_UPLOADED_ORIGINAL
verification: EXACT_SERVER_REVIEWED_INPUT
source_identity: 0c8fb9635f4a8562fb1b592702c30eb9c955e48937e5ba2f39ac81a6a05390c4
source_file_sha256: 5bd741c2a7f6e9058b32e3d6858b0f8951c1d1816eccd85c3cee1a1f5fd1ca38
segments: 292 originalrader, exakt segment_id/person_id/start/end/source_code→code
```

**Hela oförkortade JSON-objektet** finns i den lokala privata leveransfilen `private/positive-source-basis.json`. Dess kanoniska SHA-256 är `01649303aed407c00f9d6cd66db36de3567fe5815a725cef9e717012359cd789`; bytefilens SHA finns i `DELIVERY.json`. Originalrader och privata profiler publiceras inte på GitHub.

Alla 292 källrader bevaras, inklusive historik och källrader utanför den föreslagna arbetstiden. P2-raderna matchar frontendens originalperiodsegment exakt. Inga modifierade motorpass används som original. `source_basis` ger inga nya schemaplaceringar och är inte ett verksamhetsgodkännande.

Den riktiga positiva källexporten skapades av `_normalize` utan kandidat/resultatschema. Därför har den inga föreslagna schemarader och frontendens `proposalOf` returnerar null, som avsett. Detta är ett källbevisprov, inte en ny körning eller ett påhittat solverresultat. Ett separat syntetiskt solverfritt schema används i frontendens fulla parserregression.

## Godkända kontroller

- **71 motor-/profiltester PASS, 0 FAIL**: source_basis, serverprofilens tvåfältstillägg, korruptions-/idempotenskontroller, komprimerad profil, befintlig import, START_WINDOW/EXECUTION_WINDOW och berörda availability-identitetsprov.
- **32 lokala API-kontroller med den exakta Flora-indatan PASS**. Rätt input når nästa förkontroll och stoppas av avsiktligt ogiltig idempotensnyckel före manager. Negativa input stoppas tidigare. Registret väljer också sin verkliga fallbackprofil vid fel dataset; den felaktiga inputen nekas där.
- **17 syntetiska frontendkontroller PASS** mot ce9668e, utan fältöversättning.
- **Verkligt Flora-källbevis i frontend PASS**: `parseFloraText`, `originalRunBasis`, originalperiodens radmatchning och avsaknad av förslag utan schema. Rå JSON ändras inte.
- **12 befintliga legacy-API-observationer oförändrade** mot basen c7170d4.
- Övervakade solver-, manager-, JobStore-, SQL-, subprocess- och nätanrop i motorproven: **0**. Frontendens nät-/lagringsanrop: **0**.

| Prov | HTTP | Felkod/kontroll | Resultat |
| --- | --- | --- | --- |
| correct_input_preflight | 422 | DELIBERATE_IDEMPOTENCY_STOP | PASS |
| source_file_sha256 | 422 | INPUT_REVIEW_REQUIRED | PASS |
| dataset_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| business_id | 422 | BUSINESS_MISMATCH | PASS |
| data_use | 422 | DATA_USE_MISMATCH | PASS |
| timezone | 422 | INPUT_REVIEW_REQUIRED | PASS |
| planning_period_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| source_layout | 422 | INPUT_REVIEW_REQUIRED | PASS |
| history_period_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| schema_version | 422 | INPUT_REVIEW_REQUIRED | PASS |
| period | 422 | INPUT_REVIEW_REQUIRED | PASS |
| segment_time | 422 | INPUT_REVIEW_REQUIRED | PASS |
| segment_person | 422 | INPUT_REVIEW_REQUIRED | PASS |
| segment_code | 422 | INPUT_REVIEW_REQUIRED | PASS |
| need_row | 422 | INPUT_REVIEW_REQUIRED | PASS |
| staff_duplicate | 422 | INPUT_REVIEW_REQUIRED | PASS |
| staff_missing_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| staff_blank_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| staff_missing_row | 422 | INPUT_REVIEW_REQUIRED | PASS |
| customers_duplicate | 422 | INPUT_REVIEW_REQUIRED | PASS |
| customers_missing_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| customers_blank_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| customers_missing_row | 422 | INPUT_REVIEW_REQUIRED | PASS |
| schedule_segments_duplicate | 422 | INPUT_REVIEW_REQUIRED | PASS |
| schedule_segments_missing_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| schedule_segments_blank_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| schedule_segments_missing_row | 422 | INPUT_REVIEW_REQUIRED | PASS |
| customer_needs_duplicate | 422 | INPUT_REVIEW_REQUIRED | PASS |
| customer_needs_missing_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| customer_needs_blank_id | 422 | INPUT_REVIEW_REQUIRED | PASS |
| customer_needs_missing_row | 422 | INPUT_REVIEW_REQUIRED | PASS |
| missing_auth | 401 | AUTH_REQUIRED | PASS |

Detaljer finns i `checks/motor-tests.json`, `checks/bound-flora-proof.json`, `checks/frontend-tests.json`, `checks/frontend-bound-flora.json` och `checks/baseline-comparison.json`. API-proven kördes i lokal ASGI-process mot kod och profilsnapshots, inte som live-POST på Render. Bara läsande Render-GET användes för att fastställa konfigurationen.

## Ändrade filer i färdig rättning

Profilkonfiguration:

- `motor/bb/flora_source_binding.json` — versionsbundet, serverägt tillägg med exakt profil, verksamhet, dataset, basprofilhash och de två godkända hashvärdena. Inga privata rader.

Motor:

- `motor/bb/business_profiles.py` — applicerar tillägget efter befintligt autentiserat registerurval; bevarar övriga profilfält och låter profilhashen omfatta bindningen.
- `motor/bb/flora_import.py` — verifierar exakt source_identity, fil-SHA och separat organisation/användning; bygger källbevis från orörd originalinput.
- `motor/bb/flora/__init__.py` — exporterar källbevis och kontrollerar komplett snapshotintegritet.
- `motor/bb/availability_import.py` — gemensam source_identity avvisar också tomma stabila ID:n; projektion och hashdefinition är i övrigt oförändrade.
- `motor/bb/flora_jobs.py` — inkluderar bindningsfilen i befintligt method_fingerprint. Jobb-/solverlogik oförändrad.

Prov och underlag:

- `motor/tests/test_source_basis.py`
- `motor/tests/test_source_profile_binding.py`
- `motor/tests/run_source_basis_checks.py`
- `motor/tests/check_bound_flora_source.py`
- `motor/tests/frontend_source_basis.mts`
- `motor/tests/frontend_bound_flora_source.mts`
- `docs/original-motor-source-basis-20261029.md`

## Installation och rollback — endast plan

Ingen separat uppladdning av privat profil krävs för denna lösning. Vid ett senare godkänt införande används samma register och monterade profilfil; kodens versionsbundna tillägg skapar det effektiva bundna profilobjektet. Om den monterade profilen inte har förväntad basprofilhash stoppas profilen, i stället för att andra beslut skrivs över.

Inför installation: verifiera aktuell service, livecommit, registerurval och faktiskt monterad profilhash mot denna leverans; installera därefter endast uttryckligt godkänd commit. Ingen aktivitetspatch eller merge till main/pilot ingår.

Rollback till föregående godkända motorcommit tar bort tillägget ur den effektiva profilen; den monterade profilfilen har inte ändrats. Inga databasposter behöver skrivas om. Tidigare jobb/resultat behåller sina egna profil-/metodhashar och blir inte automatiskt uppgraderade eller nyverifierade.

Befintligt jobb `649630a6ca9e4517bf4da6be65c11902` har inte ändrats. Read-only källbevisprov är klart; ingen ny körning eller deploy är godkänd genom denna leverans.

SOURCE_BASIS OCH PROFILBINDNING REDO FÖR INSTALLATION
