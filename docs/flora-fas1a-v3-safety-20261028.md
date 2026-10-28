# Flora Fas 1A v3 – tekniska spärrar, inte installerat

Bascommit: 94aa367c15bf25d82679b4a413555a6b671b0e52.
Detta är en separat granskningsgren. Inget körmandat, ingen deploy eller registerändring ingår.

## Requestkontrakt

POST /api/engine/jobs kontrollerar bindningen före normalisering, prepare och get_manager.
Serverns autentiserade owner väljer en workspace-bindning. Dataset måste finnas exakt i
binding.dataset_profiles; fallback till grundprofilen är borttagen. Klientens profil-ID/hash
är förväntningar, aldrig profilväljare. Motstridiga profil-ID/hash i nästlad requestmetadata
nekas också före normalisering, inklusive fält som annars skulle försvinna där.

Registret måste separat kompletteras med `request_contracts[dataset_id]`:

```json
{
  "version": "bb-request-binding/1.0",
  "source_file_sha256": "19e777012ea1e5df4c53d08258386e96aba9f645d001cf2b13c1a15e05ba22f7",
  "dataset_id": "FLORA-RADATA-20261024",
  "business_id": "9b4cd08f-82fc-4e40-856a-04ce6dc4ec41",
  "period": {"id":"P2","start":"2026-05-11","end":"2026-06-07","timezone":"Europe/Stockholm"},
  "profile_id": "flora-raw-historical-input-20261024-24h-test",
  "profile_hash": "264b72d35b606a8b8c0583383d992dfc3ca513b0f73b0a222d5dcb347eda2794",
  "data_use": "development",
  "schema_version": "flora-bb-input/1.0"
}
```

Requestens `input.metadata` måste innehålla motsvarande fält, inklusive `period`.
Den befintliga `periods`-listans P2 måste matcha och `metadata.timezone` måste matcha.
Registrets `version` är inte ett nytt inputschema; requesten behåller `flora-bb-input/1.0`.
Alla påståenden är skiftlägeskänsliga och exakt jämförda. Inget nytt verksamhetsbeslut införs.
Serverkontraktet jämförs även med serverprofilens källhash, period, profilhash och organisation.

Felkoder är 422 för requestfel, 503 för saknad/inkonsistent serverkonfiguration.
Saknad autentisering behåller befintlig HTTP401. Okänd owner ger 422.
Befintliga klienter behöver komplettera metadata innan de kan skapa nya jobb med denna kod.
Även andra registrerade dataset behöver ett eget uttryckligt kontrakt; inga värden här får ärvas.
Historiska D1-läs-/registreringsfunktioner behåller sin separata artefaktkontroll och använder
serverprofilval utan att låtsas vara en ny jobbrequest. Inga registreringsprov kördes.

## Skrivskyddat profilbevis

GET /api/engine/profile-attestation?dataset_id=FLORA-RADATA-20261024
kräver befintlig serverautentisering samt X-BB-Job-Owner för verifierad organisation.
Kräver också konsekvent serverkontrakt. Skickas server-till-server, aldrig med service-token i webbläsaren.
Returnerar endast schema, faktisk profilfil-SHA, kanonisk profilhash, profil-ID,
business_id, dataset, period, data_use, motorcommit och kontraktsversion.
Inga sökvägar, privata profildetaljer eller credentials returneras.
Om filen ändras mellan profilval och bytekontroll nekas läsningen.
Motorcommit hämtas ur RENDER_GIT_COMMIT; saknat värde får inte räknas som verifierad revision.
Denna route är endast lokalt testad. Ingen live-monterad filhash intygas i v3.

## Whole-duty-bevis

En gemensam funktion används av aritmetik och dygnsvila. Endast uttrycklig källgrupp med
fullständigt, oförändrat arbetsmedlemskap/person/koder/start/slut blir VERIFIED_WHOLE_DUTY.
Klientetiketter, genererade kandidater och scenarioöverlagringar skapar inte nytt passbevis.
Övriga källcellssamlingar märks UNVERIFIED_GROUPING. Tidernas min/max beskriver en teknisk
samling och godkänns inte som nya passgränser. Ingen tidsnärhet används för medlemskap.

Regler för helt pass, mellanpassvila och jourdiagnostik blir UNKNOWN utan gruppbevis.
Dygnsvilofönster som berör sådan gruppering blir UNKNOWN. Kända överlapp/fel i oberoende
segmentkontroller förblir kontrollerade. Aggregerad FAIL för verifierade fel maskeras inte av UNKNOWN.
780 minuter gäller fortfarande endast verifierade Ar-only-pass i no-break-scenariot, startande i P2.
Global maxpass är UNKNOWN/NOT_SELECTED i Flora. Ingen 24h-regel aktiveras på antagande.

## Validering och begränsningar

32 negativa lokala ASGI-prov + korrekt baslinje med stopp före original-get_manager.
Felstatus OCH felkod verifieras. Fil-/DB-/nät-/modell-/solver-/registreringsspärrar är aktiva.
14 rena regressions-/säkerhetstester; två solverberoende dygnsvilotester körs uttryckligen inte.
Historiskt resultat återanvänds endast som validatorfixture; ingen ny schemakandidat skapas.
Bred jobblivscykel-/solver-/registreringssvit har inte körts och är inte godkänd genom dessa tester.

V3-delivery innehåller osänd request, privat föreslaget register, samtliga segmentstatusar,
negativprov och checksummor. V1/v2 ska förbli byte-identiska. Separat mandat krävs för installation,
appgatewayanpassning och runtimeattestation. Testisolering/budget/stoppägare från v2 kvarstår.
