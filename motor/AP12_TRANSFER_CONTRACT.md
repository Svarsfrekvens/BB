# AP12 · versionsbevis och överföringskontrakt

## Driftsatt motor vid läskontrollen 2026-10-20

Render tjänst `srv-dagip8740ujc73fcnt00` (`bemanningsbalans-motor`) rapporterade live-deploy `dep-dbb7alc9v7es73adigjg` från `Svarsfrekvens/BB`, grenen `pilot-snapshot-2026-09-15`, full commit `99a156b97f60e589f838c88a8bc9645402138852`. Detta är Render-deploymetadata, inte bara API-versionen `1.0.0`. Den separata mappen/repon `bemanningsbalans-motor` är **inte** tjänstens deploykälla.

Detta är en historisk läskontroll, inte ett påstående om tjänstens aktuella driftsversion. Render-beviset gäller tjänstens live-version vid kontrollen, inte automatiskt varje äldre jobb. Äldre jobb utan sparad byggcommit ska fortsatt ha okänd byggversion; metodfingeravtryck och tidigare deploytider är inte samma sak som bevis för ett enskilt historiskt jobb.

## Nytt privat läskontrakt, endast efter installation

`GET /api/engine/jobs/{job_id}/submitted-source` använder samma verifierade arbetsyteägare och serverprofilbindning som `GET /api/engine/jobs/{job_id}`. Ett annat verksamhetskonto får 404. Ett ej färdigt eller korrupt jobb ger fel utan privata rader. Svaret `bb-engine-submitted-source/1.0` innehåller exakt sparad normaliserad `request` (inklusive `input`, scenario och servergenererad `engine_context`), `input_hash`, `profile_hash`, metodfingeravtryck och eventuellt sparad full byggcommit. Kontrollsummorna för begäran, profil och resultat kontrolleras före utlämning. Profilens innehåll lämnas inte ut; dess hash identifierar den sparade serverprofilen.

SHA-256-regeln för `input_hash` är UTF-8-kodad JSON med sorterade nycklar, kompakta separatorer, `ensure_ascii=False` och `allow_nan=False`. En konsument ska jämföra **den sparade begäran**, inte rekonstruera historisk indata från dagens arbetskopia. `source_archive` finns inte i motorbegäran och får inte läggas till här.

Nya jobb lagrar `RENDER_GIT_COMMIT` som `build_commit` endast om variabeln innehåller en full 40-teckens SHA-1. Saknas den blir fältet `null`; ett metodfingeravtryck får aldrig etiketten byggcommit. Jobbet stoppas om en annan byggcommit kör arbetaren. Befintliga jobb får `null` och ändras inte retroaktivt.

## Pass och raster i nya svar

`bb-engine-transfer-anchors/1.0` lägger till `pass_id` och `pass_id_basis` per schemarad. Flora-metoden sätter pass-ID endast från uttryckligt granskat `whole_duty_id`, en granskad omplaceringsenhet eller ett valt modellgenererat kandidatpass. När dessa bevis saknas är `pass_id=null` och `pass_id_basis=UNVERIFIED`. Rad-ID-prefix, angränsande tider och `source_ref` används aldrig för att gissa ett helt arbetstillfälle.

Varje rast har `break_id`, `anchor_segment_id`, `anchor_status` och `pass_id`. Ankaret sätts endast när **exakt en** schemarad för samma person innehåller hela rasten. Annars är ankare och pass-ID `null`, med `anchor_status=UNRESOLVED`. Det äldre `duty_id`-fältet behålls för kompatibilitet men är inte ensamt överföringsbevis. Tillgänglighetsmetodens valda arbetstillfällen har egna modell-ID och inga raster i det beslutade scenariot.

`transfer_contract.pass_ids_complete` och `break_anchors_complete` anger endast om dessa identiteter finns i svaret. De är inte ett schema- eller regelgodkännande. `approval_inherited=false` gäller alltid. BB måste dessutom verifiera exakt sparad begäran mot den arbetskopia som ska skapas, källans behov/personer/period, hela segment- och tilldelningsmängden samt ett separat aktuellt kontrollresultat. Om något saknas ska överföringen vara atomärt blockerad.
