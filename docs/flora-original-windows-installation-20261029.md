# Flora – originalintervall och låsning, granskningsunderlag 2026-10-29

**INTE installationsklart.** Källbindningen och ett strukturerat stopp är färdigställda. Den senaste kompletteringen klargör att originalintervallet inte ger rätt att flytta behovets start. För 1 275 behov saknas verifierad låst starttid eller tillräckligt avgränsat flyttbeslut. Inga starttider har gissats.

Denna rapport ersätter installationsbedömningen i den tidigare lokala leveransen `BB_FLORA_ORIGINAL_WINDOWS_20261029`. Den äldre leveransen bevaras som historik. Dess positiva tekniska exportprov visar fönsteröverensstämmelse, inte flytträtt.

## Versioner och befintligt arbete

Gren: `codex/original-motor-need-window-contract-20261029`. Föregående commit: `b8e227234fae8871130a9b690853afb3a1ccaafd`. Bas och rapporterad rollback: `d60b518922040771016a6335f8d1310a6fbe249a`. Frontend oförändrad: `c6d2c810de8628a33177c35c70a6e7e0ddd6081d`. Slutlig lokal granskningscommit anges i DELIVERY.json och slutrapporten. Ingen push, installation, deploy, merge, solver eller verklig jobbsubmission.

Det tidigare källbeviset för 1 451 behov och +4-kopplingen återanvänds. Beslutsfilen använder fysisk Excel-rad; appen använder det bevarade `source_row`. Båda referenssystemen och fil-/radhasherna finns i den nya serverbevisfilen. Ingen mekanisk fyraraderskorrigering eller omskrivning av källfiler görs.

## Bemanningsbibeln – version och jämförelse

Den senaste tillgängliga huvudversionen i arbetsytans underlag är **v16, reviderad 24 oktober 2026**:
`/workspace/attachments/ac42aa48-c507-4bfc-8029-64d3c6b43c90/Bemanningsbibeln_v16_2026-10-24_fulltext.md`.
Textuttaget anger att det återger v16:s huvuddel, inte en ny revision. Ingen senare version finns i de tillgängliga bibelfilerna. V15.2 är ett beslutat tillägg daterat samma dag och har jämförts separat:
`/workspace/attachments/3a1fba2f-5bb4-495b-b268-0ca1abdfc5ae/Bemanningsbibeln15_2.pdf`.

- **V15.2, avsnitt 2, PDF-sidor 10–11:** ”En insats ligger på sin tid om inget annat anges (lås by default).” Samt: ”inget flyttas förrän verksamheten bekräftat insatsen som flyttbar, dess fönster och ev. tillåten roll.” Flyttbarhet härleds aldrig ur klockslag eller schema.
- **V16, avsnitt 2:** ”Behov är låsta om inget annat är beslutat.” ”Ett förslag från BB är inte en bekräftad flyttbarhet.” Tabellen skiljer starttidsfönster, genomförandefönster och fast verifierad starttid.
- **Skillnad:** v16 förtydligar att en senare uttrycklig, avgränsad tidsregel kan gälla för de behov den avser, exempelvis Galaxens T07. Detta ger ingen överförd rätt för Flora. Grundkravet på verksamhetsstöd för flyttbarhet är oförändrat.
- V15.2:s tillägg om historiska utvecklingsprov är inte ett uttryckligt insatsvis flyttbeslut. Användarens aktuella komplettering klargör dessutom att intervallgränser inte ska behandlas som fri placering.

Filhashar och exakt jämförelse finns i `bible-lock-audit.json`.

## Floras befintliga beslut

Följande underlag har kontrollerats:

1. `FLORA-INTERVALL-20261024`: EXECUTION_WINDOW för 1 451 behov. Beslutets scope anger uttryckligen **”Ingen ändring av andra verksamheter eller separat flytträtt.”** Beslutet anger därmed tidsgränser, inte frihet att välja start.
2. `FL-B01`/`FL-B02`: allmänt flyttfönster 08–20 för aktiviteter som inte är låsta. De avgör inte vilka behov som är upplåsta.
3. `FL-B03`: låsta insatser ska bevaras; ingen automatisk upplåsning via titel, status eller historiskt schema.
4. VC-källorna `A9:E9` och `A32:E32`: allmänna formuleringar om att kunna flytta förmiddagsinsatser och planera på kväll. De saknar entydig need_id-omfattning, verifierad låst start eller bekräftat fönster för varje tillämplig grupp och står som `ORIGINALTEXT_EJ_REGEL` i underlaget. De har inte ignorerats, men kan inte automatiskt göras till en radvis behörighet.
5. De 286 analysutvidgningarna har exakt teknisk koppling men kvarstående reservation om individuell verksamhetsbekräftelse. De är inaktiva, liksom de åtta K3-testundantagen.

Samtliga 1 451 källbehov saknar uttryckligt `fixed_or_flexible`-värde. Profilens tidigare etiketter FAST/FLEXIBEL och `flex=False` är inte tillräckliga bevis för en låst klocktid: det äldre numeriska beteendet gav även med flex=False startdomänen `[fönsterstart, fönsterslut − duration]`.

## Exakt återstående lucka

- **176 behov:** intervallets bredd är exakt lika med durationen. Tidsgränserna lämnar en enda möjlig start; ingen fri startdomän behövs. Detta är en matematisk konsekvens av det verifierade intervallet, inte ett nyuppfunnet verksamhetsbeslut.
- **1 275 behov:** intervallet lämnar fler än en möjlig start. Underlaget styrker varken en exakt låst start eller tillräckligt avgränsad flytträtt inom intervallet. Av dessa har 981 tidigare etiketten FAST och 294 FLEXIBEL. 274 av de 286 inaktiva analysutvidgningarna ligger i denna mängd.

`missing-timing-evidence.csv` redovisar exakt alla 1 275 need_id, källreferens, ursprungliga gränser, duration och vilken uppgift som saknas. Början på intervallet eller en historisk utförandetid används inte som antagen låst start.

**Minsta nästa underlag:** antingen verifierade låsta starttider, eller ett uttryckligt befintligt/verksamhetsbekräftat beslut om flyttbarhet, omfattning och tillåtet fönster för berörda behov. Ett entydigt avgränsat gruppbeslut kan täcka flera behov; 286 individuella beslut begärs inte för de inaktiva analysutvidgningarna. När uppgifterna finns ska kopplingen mappas källstyrt och endast påverkade prov köras om.

## Färdigställda tekniska delar

- `flora_window_binding.json`: versionsbundet serverbevis för samtliga 1 451 behov, ursprungligt intervallbeslut, båda källreferenserna, radhasher och inaktiva undantag.
- `flora_window_binding.py`: servervalt profilpålägg i minnet, exakt kontroll av profil/source_identity, källrader och period; inga monterade filer ändras.
- `business_profiles.py`: ansluter beviset efter den befintliga servervalda source_basis-bindningen.
- `flora_import.py`: verifierar bindningen och bevarar en uttrycklig `locked_by_default`-markering för denna profil.
- `need_windows.py`: stoppar den bundna modellen när fönstret lämnar flera möjliga starter utan verifierat tidsbeslut. Kontroll före jobbhanteraren och på nytt före resultatexport. Att snäva in en intern startdomän till en godtycklig punkt löser inte spärren: kontrollen använder det ursprungliga källfönstret.
- `flora_jobs.py`: ny kod och bevisfil ingår i metodfingeravtrycket.

HTTP-förkontrollen på de exakta Flora-snapshoten ger **422 / INPUT_REVIEW_REQUIRED** med `NEED_TIMING_DECISION_REQUIRED: 1275`. Noll jobb skapas. `_normalize` avvisar även direkt försök att exportera ett accepterat jobbresultat för detta olösta underlag.

`bb-need-window/1.0` återanvänds. Det fullständiga kontraktet kan verifieras som **källprojektion**, men presenteras inte som resultat av en godkänd modellerings-/körväg. Inget `placement_domain_contract` och inga undantag har aktiverats. Source_basis-objektet och samtliga 292 originalsegment matchar det tidigare beviset exakt.

## Riktade kontroller

- **12 motorprov PASS**, inklusive fullständig bindning, saknade/ändrade källfält, profil-/bevismutationer, inaktiva undantag, oförändrat source_basis och strukturerat stopp för de 1 275 oavgjorda tiderna. Flera prov innehåller separata negativa subfall.
- **10 frontendkontroller PASS** på c6d2c810. Representativ positiv export använder en syntetisk insats där intervall och duration ger en enda start. Rå JSON går oförändrad genom riktig parser och arbetskopiefunktion i minnet; ingenting sparas.
- Frontendens verkliga kontraktskontroll accepterar även alla 1 451 källrader. Detta verifierar fönsterformatet, inte flytträtt eller ett genomförbart Flora-schema.
- Tidigare 83 motorprov, 28 frontendkontroller och åtta koordinat-/domänkontroller återanvänds för oförändrade delar. De har inte körts om i sin helhet. Proven som berördes av användarens låsningsförtydligande har ersatts/uppdaterats och körts riktat.
- Noll solveranrop, verkliga jobb, databasanslutningar, nätverksanrop, registreringar eller verksamhetsskrivningar.

## Installation/rollback

Installera inte denna granskningsversion som färdig Flora-lösning: den stoppar det aktuella underlaget korrekt. Källbindningen är bevarad så att arbetet kan fortsätta när de saknade tidsbesluten finns. Ingen aktivitetspatch eller frontendändring ingår.

Efter komplettering krävs separat mandat för push och installation av en exakt godkänd commit. Befintligt register, secrets och databas ska bevaras. `motor/Dockerfile` kopierar redan hela `bb`-katalogen. Den effektiva profilen får hash `8070ff1f86f6e17a7175d679259a8511e87ed97338ffd4ff3d71811163fea101` för denna förberedda fönsterbindning, men det är inte ett intyg om kompletta tidsbeslut.

Rapporterad rollback är `d60b518922040771016a6335f8d1310a6fbe249a`. Ingen migration görs. Liveversionen har inte återkontrollerats i detta lokala uppdrag. En verklig körning och schemagenomförbarhet kräver separat mandat efter korrekt installation.

FLORA INTE FÄRDIG – 1 275 behov saknar verifierad låst starttid eller tillämpligt uttryckligt flyttbeslut; komplettera dessa uppgifter eller ett entydigt avgränsat gruppbeslut innan körvägen kan öppnas.
