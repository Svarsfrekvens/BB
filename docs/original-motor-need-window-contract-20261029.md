# Joint need-window-kontrakt – 2026-10-29

**Installationsstatus: INTE REDO för befintlig Flora-profil.** Kodens solverfria prov passerar, men det bevarade, exakt bundna Flora-underlaget saknar uttryckliga fönstertyper. Att gissa dem skulle strida mot källbeviset. Inga verksamhetsbeslut eller profilvärden har ändrats.

## Versioner och avgränsning

- Gren: `codex/original-motor-need-window-contract-20261029`.
- Direkt bas: `d60b518922040771016a6335f8d1310a6fbe249a`.
- Frontend testad oförändrad: `c6d2c810de8628a33177c35c70a6e7e0ddd6081d`.
- Aktivitetspatch `c5148cb54feba0e98c405c2dde883fb3a71307c2` ingår inte i anor eller diff.
- Ingen push, deploy, frontendändring, profiländring, registrering, databasanslutning, solver eller verkligt jobb. Inga befintliga produktionsresultat har ändrats.
- De två workerfallen är minnesfixturer med en deterministisk adapter. `synthetic-local-need-window-patch` i deras provenance är en testmarkör, inte en driftsatt commit.

## Ändrade filer

| Fil | Ändring |
| --- | --- |
| `motor/bb/need_windows.py` | Återanvänder `bb-need-window/1.0`, inför obligatorisk fullständighet för joint-metoden, kontroll av ID-mängd mot fryst periodunderlag, jämförelse mot modellerade fält samt kontroll av råa och exporterade placeringar. |
| `motor/bb/flora/__init__.py` | Kontrollerar kontraktsförutsättningarna före jobbhanteraren via `check_case` och igen i `_normalize`; exporterar kontraktet obligatoriskt och kontrollerar JSON-placeringarna före retur. |
| `motor/tests/test_typed_windows_contract.py` | Anpassar joint-metodens tidigare tysta legacy-frånvaro till förväntat stopp; felaktiga resultat får inte längre exporteras. Tillgänglighetsmetodens befintliga legacy-prov bevaras. |
| `motor/tests/test_joint_window_export.py` | Tolv riktade regressioner för fullständighet, periodurval, modellmatchning, gränser, personalantal, export och API-stopp. |
| `motor/tests/run_joint_window_checks.py` | Reproducerbar solverfri testsvit och verklig resultatexport via minnesadapter; spärrar databas, nätverk, solver och verklig jobbhanterare. |
| `motor/tests/frontend_joint_window_contract.mts` | Läser exakt exporterad JSON med frontendens faktiska parser och arbetskopiefunktioner i minnet; positiva och muterade negativa fall. |
| `motor/tests/check_joint_window_profile.py` | Läsande lokal kontroll av uttryckligt angiven privat input-/profilsnapshot. Skriver endast sammanfattning, hashar och räknare. |
| `docs/original-motor-need-window-contract-20261029.md` | Denna leverans och installations-/rollbackplan. |

## Export och felhantering

Befintliga `resolve`, `bounds`, `row`, `export` och `placement` återanvänds. START_WINDOW begränsar start, EXECUTION_WINDOW hela insatsen. Inga fönster flyttas och ingen typ härleds från klockslag eller tidigare modellbeteende.

Kontraktet omfattar alla periodbehov, även oplacerade. Importören kontrollerar redan profilens behovsmängd mot perioden. Den nya kontrollen verifierar dessutom samma mängd mot den frysta inputen, unika externa ID:n och överensstämmelse mellan `source_needs` och de modellerade behoven. Källtyp, gränser, duration, personalantal och startdomäner måste stämma.

Om fönstertyp saknas i både källa och granskad profil svarar den befintliga API-vägen HTTP **422**, `detail.code=INPUT_REVIEW_REQUIRED`, med meddelandet `NEED_WINDOW_CONTRACT_REQUIRED`. Detta sker i förkontrollen före `get_manager`, köläggning och solver. Motsägelser i modell eller export stoppas med ValueError; ett workerfel får den befintliga strukturerade koden `INPUT_OR_MODEL_ERROR`, inte ett lyckat resultat utan kontrakt. Blandade kända/okända typer stoppas enligt den befintliga kontrollen.

Tillgänglighetsmetoden använder fortsatt det frivilliga exportläget. Ingen profil eller verksamhetssemantik ändras för att kringgå spärren.

## Exakt positivt syntetiskt kontrakt

```json
{
  "needs": [
    {
      "duration_minutes": 60,
      "need_id": "source-need",
      "personnel_count": 1,
      "source_window_end": "2027-01-04T09:20+01:00",
      "source_window_start": "2027-01-04T09:00+01:00",
      "window_semantics": "START_WINDOW"
    },
    {
      "duration_minutes": 10,
      "need_id": "unplaced-need",
      "personnel_count": 1,
      "source_window_end": "2027-01-04T09:20+01:00",
      "source_window_start": "2027-01-04T09:00+01:00",
      "window_semantics": "EXECUTION_WINDOW"
    }
  ],
  "version": "bb-need-window/1.0"
}
```

**2 kontraktsrader, 2 unika need_id.** `source-need` är placerat med start 09:20 och slut 10:20, vilket är tillåtet för START_WINDOW. `unplaced-need` finns med trots att det är oplacerat. Ett tredje källbehov från historikperioden ingår inte. Ett separat EXECUTION_WINDOW-prov slutar exakt 09:20. Personalantal 2 kontrolleras också i motorproven.

## Verifiering

| Kontroll | Utfall | Bevis/avgränsning |
| --- | --- | --- |
| Motorprov | PASS | 83 tester, 0 fel; inklusive source_basis, profilbindning, import och typed windows. |
| Frontend | PASS | 28/28, exakt commit ovan. |
| Fullständighet/unikhet | PASS | Två periodbehov, varav ett oplacerat, en utesluten historikrad; borttagna, dubbla, extra och ommappade rader avvisas. |
| Fönster och placering | PASS | För tidig/sen start och för sent EXECUTION_WINDOW-slut avvisas; tillåten START_WINDOW-start med senare slut godtas. |
| Mutationer | PASS | Typ, båda gränserna, duration, personalantal och saknat obligatoriskt kontrakt avvisas av faktisk frontendväg. |
| Source basis | PASS | Exakt samma source_basis som basens export för båda identiska syntetiska indatafallen. Produktionsfunktionen för källbeviset är oförändrad. |
| API-regression | PASS | Tolv HTTP-/profil-/autentiseringsprov på uttryckligt typade fixturer är identiska med basversionens svar. Källa, dataset, profil och period täcks även av source_basis-regressionerna. |
| Jobbstatus | PASS | Oförändrade publicerade statusar queued/running/succeeded/failed; minnesworker publicerar oförändrat statusformat. |
| Idempotens | Begränsat verifierad | Nyckelkontrollen och koden för lagring/idempotens är oförändrade; ogiltig nyckel stoppas efter korrekt typad förkontroll. Ingen faktisk databasbaserad deduplicering testades eftersom jobb/databas uttryckligen är förbjudna. |
| Solver/jobb/databas/nät | PASS | Samtliga spärrräknare 0; inga riktiga jobb eller databasanslutningar. |
| Flora-snapshot | BLOCKERAR | 1 451 periodbehov saknar uttrycklig typ; korrekt HTTP 422 före jobbhanteraren. |

Frontendvägen är `readEngineJob → jobResponse → computationOf/proposalOf → engineWorkingCopy → checkNeedWindowContract/checkPlacementWindow → validateProposalCopy/placementDomainErrors → proposal_copy`. Rå resultatexport transporteras oförändrad i ett minnessvar, utan fältöversättning eller sparning. Källan och arbetsytans indata är oförändrade; endast returvärdet från den rena funktionen granskas.

Placeringarna ligger inom typade källfönster. Ett positivt undantagsfall med breddande `placement_domain_contract` ingår inte: denna patch producerar inte ett sådant kontrakt. Utanför-fönster-mutationer utan domänbevis avvisas.

## Kvarvarande profilblockerare

Den lokala kontrollen använder den bevarade profilsnapshoten med hash `0ed6b1aae7b91f8f94d79d2ce30263c45cbfc5b31501f98cc90af9363abdf00a`, source_identity `0c8fb9635f4a8562fb1b592702c30eb9c955e48937e5ba2f39ac81a6a05390c4` och fil-SHA `5bd741c2a7f6e9058b32e3d6858b0f8951c1d1816eccd85c3cee1a1f5fd1ca38`. Detta är **inte en ny avläsning av liveprofilen eller jobb c88ee2…**.

- 3 235 källbehov totalt, **1 451 periodbehov/unika ID:n**.
- Samtliga 1 451 saknar uttrycklig fönstertyp i både input och profilbeslut.
- 286 har profilbeslut om flyttbarhet och startdomäner utanför originalets EXECUTION_WINDOW.
- Källbevisets 292 segment finns kvar oförändrade i importen.

Det går därför inte att leverera ett sanningsenligt positivt kontrakt för denna befintliga profil genom att bara lägga till en resultatrad. Ett blanketval av EXECUTION_WINDOW skulle inskränka 286 startdomäner. Ett blanketval av START_WINDOW skulle göra ett nytt påstående om källans betydelse. Inget av detta har gjorts.

Minsta fortsättning är ett separat källstyrt beslut/underlag om fönstertyp och hur redan beslutade flyttdomäner ska representeras. Om flyttdomänerna ska finnas kvar utanför källfönstret behövs dessutom ett uttryckligt, verifierat placeringsdomänkontrakt; det är inte infört i detta avgränsade uppdrag. Profilbindningen får inte försvagas för att lösa detta.

## Reproducera utan solver eller tjänsteåtkomst

```bash
python motor/tests/run_joint_window_checks.py /tmp/bb-joint-window-checks
# FRONTEND_ARCHIVE ska vara en oförändrad checkout/archive av c6d2c810…
esbuild motor/tests/frontend_joint_window_contract.mts --bundle --platform=node --format=esm \
  --alias:@app="$FRONTEND_ARCHIVE" --alias:@="$FRONTEND_ARCHIVE/src" \
  --outfile=/tmp/bb-frontend-joint-window.mjs
node /tmp/bb-frontend-joint-window.mjs /tmp/bb-joint-window-checks
# Endast om operatören redan har de privata snapshotsen lokalt:
python motor/tests/check_joint_window_profile.py "$PRIVATE_SNAPSHOT_DIR" /tmp/bb-profile-blocker.json
```

Den sista kontrollen förväntar sig `exact-input.json` och `selected-profile-bound.json` och intygar ett stopp, inte att profilen är installationsklar. Privata källfiler eller profiler ingår inte i grenen.

## Installations- och rollbackplan – ej genomförd

1. **Stopp nu:** installera inte med den nuvarande otypade Flora-profilen. Nya joint-jobb skulle avvisas redan i förkontrollen. Befintliga resultat blir inte retroaktivt rättade.
2. När källtyper och eventuella domänundantag är uttryckligt verifierade: ge separat mandat för den exakta färdiga committen, kontrollera aktuellt gateway-/profilkontrakt och kör dessa solverfria regressioner på nytt för den ändrade profilen.
3. Publicera/installera först efter separat installationsbeslut. Bevara tjänst, profilbindningar, secrets, databaser och inställningar. Ingen aktivitetspatch, frontendändring eller merge behövs för denna patch.
4. Verifiera livecommit, health/capabilities och förkontrollspärrar med skydd mot jobbskapande. En verklig verksamhetskörning kräver separat mandat.
5. Rollback: återställ exakt motorcommit `d60b518922040771016a6335f8d1310a6fbe249a`. Patchen gör ingen schema-/databasmigrering eller profilskrivning. Verifiera återställd commit och health utan jobb. Rollback återinför den kända tysta kontraktsfrånvaron för otypade behov; den får inte beskrivas som en lösning på kontraktsfelet.

## Lokala bevisfiler och SHA-256

Leveranskatalog: `/workspace/deliveries/BB_NEED_WINDOW_CONTRACT_20261029/checks`.

| Fil | SHA-256 |
| --- | --- |
| `motor-evidence.json` | `a2bc52180bc591cf41b7ec7e8c935b21ae0764b768fbb685b5c0db357a74d5db` |
| `frontend-evidence.json` | `1b62336d32317efe9b41230a4b0af5a6129d711a6cf2a6cd8e52b46713bbf5ec` |
| `baseline-comparison.json` | `e9a2371290a1feec37ae62685aca0d08939dd623545080d6449375136819068e` |
| `profile-blocker.json` | `69d98c9301a701ba4962bcb35213f69e0031e5879f3dfb657186e3e37fafa767` |
| `start_window/result.raw.json` | `c051fc68a563407499b87e6880e06017f2db92173cb58ca07f95c3830e0201e5` |
| `execution_window/result.raw.json` | `e9028adc43cc700966122d8e485c0e066938ba26136254ff9695eddc9b515370` |

NEED_WINDOW_CONTRACT INTE REDO – befintlig Flora-profil saknar uttrycklig fönstertyp för 1 451 periodbehov; 286 beslutade flyttdomäner går utanför originalfönstren.
