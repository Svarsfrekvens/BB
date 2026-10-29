# Flora – gemensamt tidsbeslut, 2026-10-29

## Gällande status efter Patricias uttryckliga intervallbeslut

**Den tidigare spärren som krävde separat exakt start för 775 förekomster är borttagen.** Beslut `PATRICIA-FLORA-TIMING-20261029-v2` ersätter v1:s krav i denna fråga. Hela insatsen ska rymmas i originalets EXECUTION_WINDOW: `start >= window_start`, `start + duration <= window_end`. Senaste start är `window_end - duration`. Ett 10-minutersbehov i 08:00–09:00 får starta 08:00–08:50.

Alla 775 tidigare blockerade intervall har fått serverbunden behörighet. Totalt finns **1 275 behov med valbar start inom originalintervallet och 176 med en enda möjlig start**. Ingen separat originalstart efterfrågas för dessa intervall. Motorns äldre fält `original` betyder fortsatt intervallstart; det är inte ett verifierat originalplaceringsbevis och används inte för att legitimera flytt.

**Separat kvarstår 132 explicita händelsevillkor i nio tidigare granskningsgrupper.** Dessa är inte kvarvarande krav på exakta starter:

| Källvillkor | Antal | Befintliga grupper | Kvarvarande information |
|---|---:|---|---|
| Medicin ges endast när kunden är på väg att lägga sig | 28 | FL-TID-G039, G040 | Styrkt koppling till läggdagshändelsen; intervallet är redan godkänt. |
| Erbjud vatten då kunden går ut och röker | 84 | FL-TID-G142–G147 | Styrkt koppling till rökhändelsen; ingen fritt vald minut får påstås uppfylla villkoret. |
| Kontrollera dörren då kunden gått till jobbet | 20 | FL-TID-G139 | Styrkt relation till avfärden. |

Källtexten bevaras genom den exakta källbindningen. Händelserna har inte egna verifierade tider eller modellerade länkar i aktuellt underlag. Därför stoppas ett fullständigt jobb med **HTTP 422 / INPUT_REVIEW_REQUIRED / NEED_DEPENDENCY_EVIDENCE_REQUIRED: 132** före jobbhanteraren. Detta bevarar användarens uttryckliga undantag för individuella beroenden. Lösningen är en händelsekoppling eller ett uttryckligt besked om hur just villkoret gäller i planeringen, inte 132 nya exakta starttider. Generella hänvisningar till läkemedelslista används inte längre som skäl att kräva en extra klocktid; ordination och utförandekrav bevaras oförändrade.

De 63 påminnelsernas intervall tillåts: 15 slutar senast vid separat aktivitet kl. 19 och 48 senast vid aktivitet kl. 11. Aktivitetstiden blir inte påminnelsens start. Ingen måltid delas upp och ingen förberedelse flyttas över dygnsgränsen genom antagande.

### Kod och riktade kontroller i denna ändring

- `motor/bb/flora_timing_decisions.json`: versionsbundet ersättningsbeslut, behörighet för exakt de 775 tidigare blockerade ID:na och separata källbundna händelsevillkor. Ingen runtimeklassning på aktivitetstitlar.
- `motor/bb/flora_timing_decisions.py`: ny förväntad beslutshash och överföring/återkontroll av händelsevillkoret med befintlig hashkontrollerad serverbindning.
- `motor/bb/need_windows.py`: skiljer saknad tidsbehörighet från ett uttryckligt ännu olöst händelseberoende. Klienten får inte ta bort villkoret eller godkänna det själv.
- `motor/tests/test_flora_timing_decisions.py`, `test_flora_original_windows.py`, `run_flora_timing_checks.py`: uppdaterade för ändrat beslut och felutfall samt riktade nya prov.

**22 motorprov PASS**, inklusive första start, senaste start med avslut exakt på slutgränsen, avvisning före/efter intervallet, avvisning av 21 minuter i ett 20-minutersintervall, tillåten 20-minutersinsats i samma intervall, bevarande av händelsevillkor och avvisning av borttaget/förfalskat servervillkor. De berörda tidigare proven kördes om eftersom versionsbunden profil och förkontroll ändrats; ingen bred omkörning av äldre sviter.

**Två parserkontroller PASS** mot faktisk frontend `95b9c43ee92751397ddd066b2379e28a54a33df9`, med ny rå solverfri motorexport helt utan fältöversättning. Tillåten placering går igenom parser och arbetskopiefunktion i minnet; avslut utanför intervallet avvisas. Ingen persistens, nättrafik eller ny browserrunda. Äldre giltigt webbläsarprov återanvänds.

Bevis: samtliga **1 451 behov**, ursprungliga intervall/durationer/personalantal, båda källreferenserna, `source_basis` och **292 originalsegment** är oförändrade. Source_basis kanonisk SHA är fortsatt `01649303aed407c00f9d6cd66db36de3567fe5815a725cef9e717012359cd789`. De 286 analysutvidgningarna och åtta K3-undantagen förblir inaktiva. Vakter visar noll solveranrop, verkliga jobb, registreringar eller databasanslutningar. Aktivitetspatchen ingår inte.

Beslutets kanoniska SHA: `c07413cddfed163067812b739b6970e5da86342e394f09cc9efb3f19f3457da0`.
Effektiv profilhash: `0cebc45b73bcf40bffe209795da15ef660b36842fe03b2139a060ddaa1e93eb7`.
Rå syntetisk resultatexport SHA: `bd634c021fc6842014a7d868fb6bde87be8130e3229a826fa5737ff1f02f3f49`.

Leverans: `/workspace/deliveries/BB_FLORA_EXECUTION_INTERVAL_DECISION_20261029/`, med motor-/parserbevis och privat medlemslista för de nio återstående händelsegrupperna. Slutcommit finns i DELIVERY.json. Tidigare leveranser lämnas oförändrade som historik.

### Nästa steg och installationsgräns

Intervallrättningen är kodmässigt färdig och kontrollerad. Ingen ny bekräftelse av intervallregeln behövs. Fullständigt Flora-prov är ännu inte verifierat eller körklart eftersom de tre konkreta händelsekopplingarna ovan saknar underlag. Den tidigare beställningen av exakta tider för 775 förekomster är **återkallad**; den ska inte skickas eller besvaras.

Efter att händelsevillkoren kan bindas: kontrollera endast ändrade beroenden, frys installationscommit/profilhash och begär separat installations-/körmandat med isolering och kostnadsgräns. Den rapporterade rollbackbasen är fortsatt `d60b518922040771016a6335f8d1310a6fbe249a`, ej på nytt liveverifierad här. Den lokala föregångaren till denna kodändring är `2ae3cf7d093717a14d5a0c6494018f5f932ac0a9`. Ingen push, merge, installation, deploy, solver eller verklig jobbsubmission har gjorts. VC ska fortfarande granska ett senare förslag före godkännande; kodprov visar inte genomförbar optimering.

## Historik före ersättningsbeslutet – inte aktuell spärr eller beställning


**Kodbindningen är färdig och riktat provad. Ett verkligt Flora-förslag är inte beräknat och full körning är fortfarande spärrad för kvarvarande tidsluckor.**

Arbetet fortsätter från `e92b1b040f2bfa66d06cb1e621697014d267fa29` på `codex/original-motor-need-window-contract-20261029`. Slutlig lokal commit anges i leveransens DELIVERY.json. Aktuell frontend är `95b9c43ee92751397ddd066b2379e28a54a33df9`, inte den äldre c6d2c810-basen. Ingen push, installation, deploy, merge, solver eller verklig jobbsubmission.

## Tillämpat beslut

Patricias gemensamma beslut är versionsbundet som `PATRICIA-FLORA-TIMING-20261029-v1`:

- Frukost, lunch, middag och medicinering behåller sina bestämda tider.
- Städning, tvätt och andra insatser utan bunden tid får föreslås flyttade.
- Måltider skiljs från förberedelser. Lunch får förberedas före lunch och frukost kvällen innan.
- Individuella krav, beroenden och omfattning bevaras.

Detta ersätter den tidigare bristen på flyttbeslut där beslutet faktiskt är tillämpligt. Ingen ytterligare individuell bekräftelse krävs för de 500 nedan. Andra befintliga regler/profilantaganden har inte ändrats.

## Exakt tillämpning

| Status i de 1 451 periodbehoven | Antal | Konsekvens |
|---|---:|---|
| Gemensamt beslut tillåter förslag inom originalintervallet | 500 | Ny serverstyrd behörighet `MOVABLE_WITHIN_SOURCE_WINDOW` |
| Endast en möjlig start enligt originalintervall och duration | 176 | `UNIQUE_SOURCE_START`, ingen tid gissas |
| Egen låst start eller händelsekoppling saknas | 775 | `REVIEW_REQUIRED`, förkontrollen stoppar hela det verkliga jobbet |

De 500 fördelas på 400 städ-/tvätt-/hushålls-/administrativa rader, 56 icke-ordinationsbundna påminnelser om tandborstning, 28 köp av matlåda, 8 personliga omsorgsinsatser utan uttrycklig fast klocktid i källan och 8 uppgifter före hämtning av avfall/återvinning. För de sistnämnda bevaras den ursprungliga tisdagen respektive söndagen före källans onsdags-/måndagshämtning; ingen hämtningstid uppfinns.

Tillståndet gäller enbart originalets EXECUTION_WINDOW, samma datum, full duration och oförändrat personalantal/utförarkrav. Det aktiverar inte en generell 08–20-domän. De 286 äldre analysutvidgningarna och åtta K3-undantagen är fortsatt inaktiva, även om en del av samma behov nu omfattas av det nya, snävare verksamhetsbeslutet.

Runtime gör ingen generell titelklassning. Varje behov är uttryckligen kopplat med stabilt ID till en granskad beslutsgrupp i `flora_timing_decisions.json`. Befintligt rad-/källbevis skyddar hela behovsraden, inklusive beskrivning och individuella krav. Ändrat underlag eller ett förfalskat beslut stoppas.

## Måltid och förberedelse hålls isär

- Frukost/lunch/middag klassas som måltid, även när insatsen omfattar tillsyn, transport eller finfördelning av maten. Hela insatsen och personalbehovet bevaras.
- Matlagning som också innehåller måltidstillsyn klassas som **sammansatt förberedelse och måltid**. Den får inte flyttas som om allt vore fristående matberedning.
- Ren lunchberedning, kundgemensam överenskommen matlagning och tillagning av matlådor klassas separat. De aktuella radernas duration fyller respektive originalintervall; de ger därför inte nya fria startminuter utan ett källstyrkt alternativt beredningsfönster.
- Köp av matlåda är inte samma sak som måltiden. De 28 köpraderna får flyttförslag inom befintligt inköpsintervall; innehåll och kundvillkor bevaras.
- **Rätten att förbereda frukost kvällen före är beslutad.** Däremot finns ingen separat frukostberedningsrad med styrkt egen duration och kvällsintervall. Den nuvarande frukostraden blandar måltidstillsyn och förberedelse. Därför skapas ingen ny rad, ingen varaktighet delas och ingen tidigare kvällstid antas. Detta är ett underlags-/uppdelningsbehov, inte krav på ett nytt principiellt flyttgodkännande.

## Återstående konkreta tidsluckor

| Kategori | Rader | Befintliga granskningsgrupper | Exakt saknad uppgift |
|---|---:|---:|---|
| Måltider | 92 | 12 | Egen bestämd start/måltidsankare. Exempelvis 07–08 med duration 5 minuter anger inte en unik låst start. Ingen gräns väljs som start på känsla. |
| Medicin/ordination | 516 | 56 | Ordinerad tid eller exakt tillämpligt ordinationsfönster. 432 har läkemedelsflagga; 84 tandborstningsrader hänvisar uttryckligen till läkemedelslistan trots falsk flagga och får inte ärva vanlig hushållsflyttbarhet. |
| Påminnelse inför bestämd aktivitet | 63 | 16 | Egen tid/frihet för påminnelsen. Aktiviteten kl. 11 eller 19 är inte påminnelsens start. |
| Händelsebundna insatser | 104 | 7 | 84 kopplade till när kunden går ut och röker, 20 till att kunden lämnat hemmet. Händelsens koppling/tid får inte uppfinnas. |

De 775 förekomsterna finns i **91 granskningsgrupper och 19 kund-/aktivitetsfamiljer**. Det är inte 775 krav på nya verksamhetsbeslut. En befintlig verifierad tidsmall, ordinationskoppling eller ett avgränsat gruppbesked kan omfatta flera datum och grupper. Exakta medlemmar finns i den privata leveransen `remaining-timing-groups.json`; ingen ny +4-jämförelse har gjorts.

Förkontrollen ger HTTP **422 / INPUT_REVIEW_REQUIRED**, med `NEED_TIMING_DECISION_REQUIRED: 775`, före jobbhanteraren. Ett syntetiskt, entydigt verksamhetsbeslut som tillåter flytt kan däremot passera normalisering och export utan att sänka kontrollen för verkliga Flora.

## Kod och bevis

- `motor/bb/flora_timing_decisions.json`: exakt medlemslista, beslutstext, kategorier och begränsningar. Kanonisk SHA-256: `cd66471a9f0ffca75558444a5b80f0bcd9a9547f76bc4786b90376244d0bb868`.
- `motor/bb/flora_timing_decisions.py`: versions-/hashkontroll, servervalt profilpålägg, återkontroll vid modell/resultat och verifierad återställning för baskontrollen.
- `motor/bb/flora_window_binding.py`: kopplar det nya beslutet efter oförändrad fönsterbindning och kontrollerar att inga andra profilregler ändrats.
- `motor/bb/flora_import.py`: bär beslutsbeviset till modellen utan att skriva om originalfönster, personantal, källindata eller source_basis.
- `motor/bb/need_windows.py`: godtar fria startminuter enbart med rätt serverbeslut; oavgjorda låsta tider och placering utanför originalintervallet stoppas.
- `motor/bb/flora_jobs.py`: inkluderar beslutskod/-fil i metodfingeravtrycket.
- Testfiler: `test_flora_original_windows.py`, `test_flora_timing_decisions.py`, `run_flora_timing_checks.py`, `run_flora_original_windows.py`, `frontend_flora_timing_decision.mts`.

Effektiv profilhash efter bindning: `e5cd4c570913f5d5bdc63ac3ab108d38e1a25704dfcb02f9445f6e02fd5c839e`. Originalets monterade profil och register har inte ändrats.

## Riktad verifiering och återanvändning

**18 motorprov PASS:** de 12 berörda bindnings-/API-proven uppdaterades för det nya beslutet och kördes tillsammans med sex nya beslutstester. De bevisar partitionen 500/176/775, måltid/beredning, oförändrade originalintervall, skydd mot ändrat/borttaget beslut, fortsatt spärr för låsta tider, tillåten syntetisk flytt inom intervallet och avslag utanför det.

**Två riktade frontendkontroller PASS på 95b9c43:** oförändrad rå motorexport av en syntetisk tillåten placering kl. 09:10–09:20 inom 09:00–09:20 går genom verklig parser och arbetskopiefunktion i minnet. En ändring till 09:11–09:21 avvisas. Ingen persistens eller ny browserrunda.

De tio centrala gateway-/parser-/arbetskopiefilerna är byteidentiska mellan c6d2c810 och 95b9c43. Det redan genomförda isolerade webbläsarprovet, bygg-/typkontrollen och 42 tester på 95b9c43 återanvänds enligt den senaste frontendleveransen; de har inte körts om här. Äldre giltiga kontroller för oförändrade delar återanvänds också.

Oförändrat `bb-need-window/1.0` omfattar 1 451 unika behov. `source_basis` och samtliga 292 originalsegment är exakt oförändrade, kanonisk SHA `01649303aed407c00f9d6cd66db36de3567fe5815a725cef9e717012359cd789`. Originalindata och båda källreferensernas proveniens bevaras. Noll solveranrop, riktiga jobb, registreringar och databasanslutningar. Aktivitetspatchen ingår inte.

## Nästa steg och körgräns

**Nästa minsta steg är att koppla in ett befintligt källstyrkt tidsunderlag för de fyra kvarstående kategorierna**, med gemensamma mallar där dessa är tillämpliga. Samtidigt kan separat beredningsduration/-fönster preciseras om möjligheten till tidigare beredning ska utnyttjas. De 500 redan godkända flyttbara raderna behöver inte granskas om.

När dessa konkreta luckor är slutna: bind uppgifterna versionsbundet, kör bara berörda prov och redovisa exakt installationscommit. Därefter krävs separat mandat för push/installation och en isolerad verklig körning. Rapporterad live-/rollbackbas är `d60b518922040771016a6335f8d1310a6fbe249a`; den har inte ändrats eller verifierats på nytt här. Den lokala föregående granskningsbasen är e92b1b0.

Ett senare verkligt resultat ska redovisa olösta behov och styrkta förändringar mot originalet samt kräva VC:s godkännande innan det ersätter gällande schema. Vi har nu verifierad kodkoppling, inte verifierad optimering, förbättring eller ett genomförbart Flora-schema.

## Fortsatt källsökning och installationsgrind – 2026-10-29

Fortsättningen utgick från ren arbetskopia på `ef72ae85c8accf4c9fbedac241097953f7e77c49`. Motorändringen och dess 18 motorprov/två parserkontroller var redan klara. Ingen ny kodavvikelse har hittats som kan ersätta de saknade tidsuppgifterna. Denna komplettering ändrar därför endast rapporten; körbar motorkod är fortsatt ef72ae85.

### Nytt kontrollerat underlag

Sex unika lokala versioner av Flora-arbetsboken granskades för de återstående 775 behoven. Alla sex innehåller samma 775 källrader, utan en enda ändrad cell i dessa rader jämfört med den bundna källan. Ingen ny +4-granskning eller klassificering av de färdiga 676 behoven gjordes.

`06_VC_ORIGINAL` och `07_KALLOR_OCH_FALT` överensstämmer i alla sex versioner. Två äldre versioner av `08_BESLUT_FLORA` saknar de senare FL-B28–34 och har en äldre introduktion; de innehåller inga ytterligare äldre tidsbeslut. De fyra övriga beslutsbladen överensstämmer. Bladförteckningar, definierade namn, filhashar och jämförelser finns i källinventeringen. Inget separat ordinations- eller tidsmallblad identifierades.

De tillgängliga Flora P2-arkiven inventerades också. Cursor-paketets `RULE_CONTRACT.md` anger uttryckligen att de 286 breda intervallen saknar verksamhetsbekräftelse och att kopplingar mellan kundnärvaro, förberedelse och måltid saknas. Dess äldre fullanalys skiljer påminnelsens 18:50–19-intervall från duschhändelsen kl. 19. Dessa äldre analyser ger ingen ny låst start, ordination eller bekräftad flytträtt. Deras tidigare solverresultat används inte som aktuellt bevis.

Detta avser **de tillgängliga lokala källorna**, inte ett påstående om att verksamheten saknar tidsmallar eller läkemedelslistor i andra system. Registreringstid i historiken är fortfarande inte styrkt insatsstart eller händelsetid.

### Färdigställt beslutsunderlag utan nya verksamhetsbeslut

Ny lokal leverans: `/workspace/deliveries/BB_FLORA_REMAINING_TIMING_20261029/`.

| Fil | Innehåll |
|---|---|
| `source-inventory.json` | De sex källversionerna, SHA, källjämförelse, blad och arkivmedlemmar |
| `source-conclusions.json` | Exakt skillnad i äldre beslutsblad samt källhänvisade utdrag ur tidigare analys |
| `private/questions-by-group.csv` | En rad per kvarvarande granskningsgrupp: kategori, kundkod, aktivitet, dagklass, originalintervall, duration, antal, saknad uppgift, källbrist och rekommendation |
| `private/questions-by-group.json` | Samma 91 grupper med samtliga 775 medlems-ID:n, datum, individuella villkor och oförändrade befintliga referens-/proveniensobjekt |
| `private/full-coverage-review.json` | Alla 1 451 behov, var och en markerad som tidsmässigt klar eller blockerad; inga schemaplaceringar |
| `review-checks.json` | Nya täckningskontroller samt hashreferenser till återanvända testbevis |
| `SHA256SUMS` | Kontrollsummor för den nya leveransen |

Gruppunderlaget är **obesvarat granskningsunderlag**, inte ett godkänt beslut. Gruppens tidigare ID och signatur bevaras. Samma tidsmall kan omfatta flera grupper endast om kundvillkor, datum, duration, originalintervall och ordination faktiskt omfattas. De 19 familjerna är inte automatiskt 19 beslut.

Nya kontroller: **PASS** för 1 451 unika behov, exakt partition 500/176/775, exakt 775 medlemmar en gång vardera i 91 grupper/19 familjer och bevarande av varje befintligt källreferensobjekt. Ingen motorkod importerades eller kördes för att skapa dessa granskningsfiler. De tidigare 18+2 kontrollerna återanvänds; ingen ny browserrunda eller bred testsvit behövdes. Tidigare leveranser lämnas oförändrade.

### Avgränsat delprov

Ett **läsande granskningsunderlag** för de 676 tidsmässigt färdiga behoven är nu förberett med alla 775 blockerade synliga i samma fullständiga mängd. Filen är märkt `NOT_A_JOB_REQUEST`, `submission_allowed=false`; den är varken resultat, arbetskopia eller schema och har inte skickats till appen.

Ett verkligt reducerat solverjobb är inte förberett eller godkänt. Att ta bort de 775 skulle ändra källidentiteten och bryta den exakta bindningen av hela behovsmängden. Att låta dem passera som lösa eller godtyckligt låsta behov skulle kringgå tidsbeslutet. Originalprofilens stopp behålls. Ett nytt syntetiskt frontendprov ger inget nytt bevis: kopplingen är redan kontrollerad på aktuell frontend. Kortaste vägen till ett sammanhängande Flora-prov är därför att komplettera tidskällan, inte att bygga en ny testprofil.

### Endast kvarvarande frågor till Patricia/verksamheten

1. **Måltider, 92 förekomster/12 grupper:** Vilken gällande tidsmall anger de bestämda tiderna för respektive insats? Rekommendation: använd en kund-/tillfällesmall med datumundantag och ange om klockslaget gäller insatsstart, måltid eller annat ankare. Bevara transport, tillsyn och förberedelse i den befintliga omfattningen; välj inte automatiskt intervallets början.
2. **Ordinationsbundna insatser, 516/56:** Vilket gällande ordinationsunderlag anger tid, tillåtet fönster och eventuell händelsekoppling? Rekommendation: låt behörig verksamhetsfunktion tillhandahålla exakt tillämplig tidsuppgift och giltighet, inklusive Duraphat och läggdagsvillkor. Skapa ingen medicinsk testregel och skicka inte journalinnehåll i chatten.
3. **Påminnelser, 63/16:** Finns en bestämd egen start, eller omfattas påminnelserna av ett gemensamt beslut om placering inom originalintervallet? Rekommendation: besvara grupper med samma villkor gemensamt; använd aldrig den senare aktivitetens klockslag som påminnelsestart.
4. **Händelsebundna insatser, 104/7:** Vilket underlag kopplar 84 vätskeinsatser till rökning och 20 tillsyner till avfärd? Rekommendation: återanvänd en styrkt händelse-/dagsplan om den finns. Om händelsen inte kan tidssättas behöver verksamheten precisera hur insatsen ska representeras i ett prov; motorn väljer inte klockslag själv.

Tidigare kvällsberedning behöver ingen ny principiell tillåtelse. Rekommendationen för första provet är att behålla befintliga sammansatta insatser intakta. En ny uppdelning över dygnsgränsen kräver separat styrkt beredningsduration och fönster, men är inte ett krav för att använda nuvarande originalrader.

### Förberett installations- och körningssteg – får inte utföras i detta uppdrag

1. Koppla in svarens verifierade källa, giltighet och exakt omfattade medlems-ID:n i befintlig versionsbunden tidsbindning. Bevara alla 1 451 behov, originalintervall, durationer, personalantal och de 292 källsegmenten. De 286 utvidgningarna och åtta K3-undantagen förblir inaktiva. Kör enbart prov som påverkas av den nya bindningen; frys därefter slutcommit och effektiv profilhash. **Full körning är blockerad tills detta är klart.**
2. Vid senare installationsmandat: verifiera aktuell motorhost/deployment, live-SHA och servervald profil utan att exponera secrets. Rapporterad originalhost är `https://bemanningsbalans-motor.onrender.com`; rapporterad rollback är `d60b518922040771016a6335f8d1310a6fbe249a`. Dessa har inte kontrollerats live i denna fortsättning och ska inte ersättas med identiteten för den separata historiska testtjänsten. Frys det godkända isolerade körmålet och bevara befintligt register, jobbdatabas och autentisering.
3. Pusha/installera endast senare uttryckligen godkänd slutcommit. Kontrollera livecommit, runtimeprofil och källbindning. Ta läsande operativ baseline före/efter förkontroller. Negativa requestprov ska stoppas före jobbhanteraren; inget verkligt jobb ska användas som installationskontroll.
4. Med separat körmandat: fastställ exakt request, idempotensnyckel, isolering och kostnads-/tidsgräns innan en enda Flora-körning tillåts. Gatewayn ska använda rätt organisation, `development`, `FLORA-RADATA`, P2, fil-SHA och serverprofil. En accepterad förkontroll är inte ett bevis på att ett genomförbart schema finns.
5. Efter den senare körningen: verifiera samtliga 1 451 kontraktsrader, full duration/personalantal, styrkta fasta tider och alla individuella krav; redovisa placerade och olösta behov utan bortfall. Kontrollera oförändrat `source_basis`/292 segment och att aktuell frontend visar samma förslag i kund- och medarbetarschema. Förändringar ska ange från/till och stöd i beslutet. VC-granskning ska föregå godkännande; gällande schema får inte ersättas automatiskt.
6. Stopp/rollback: avbryt före jobbskapande vid fel SHA, profil, ofullständig tidsbindning eller ändrat källbevis. Vid installationsfel återställ den då verifierade föregående motorversionen och dess profilkonfiguration enligt ett separat installationsmandat. Radera inga jobb, resultat, registreringar eller källfiler. En kodrollback är inte en databasåterställning.

**Slutsats:** körbar ändring och frontendkoppling är redan riktat kontrollerade. Nya källkontroller och gruppunderlag är färdiga. Fullständigt Flora-prov behöver fortfarande de fyra specificerade tidsunderlagen ovan; ytterligare kod kan inte legitimt uppfinna dem. Ingen verifierad optimering eller förbättring har producerats i denna fortsättning.


## Slutförd kontroll av originalplacering och samlad komplettering

Fortsättningen utgår från rapportcommit `bd89329daccc97749d096562d93f5743d07b7d32`. Ingen ny sökning i de sex arbetsböckerna och ingen upprepning av motor-, parser- eller webbläsarprov gjordes.

Det möjliga tekniska hindret kontrollerades direkt i befintlig exakt motorindata, profil och importkod: motorns `original` sätts till `a`, där `a` kommer från `window_start` (`motor/bb/flora_import.py`). Fältet är därför ett härlett intervallankare, inte en separat verifierad originalplacering. Samtliga 775 återstående rader har `fixed_or_flexible=null`; profilens `retain_original_start` är false för samtliga och dess `expected`-fält innehåller ingen separat låst start. Originalets 292 personalschemasegment saknar behovs-ID-koppling. Befintlig textgranskning visar aktivitets-/händelseankare men inte någon ytterligare styrkt egen insatsstart att binda. Historiska registreringar kan inte uppgraderas till sådan källa.

**Resultat:** noll ytterligare verifierade originalplaceringar kunde kopplas in ur det befintliga granskade underlaget. 676 är fortsatt tidsmässigt färdiga och 775 saknar tidsunderlag. Detta är inte ett påstående att tider saknas i verksamhetens andra system. Ingen kodändring eller ny verksamhetsregel kan ersätta den saknade källan.

Den nuvarande versionsbundna policyn innehåller inte heller en separat policy för verifierad låst start inuti ett bredare intervall. När en sådan originalkälla tillförs ska dess bindning implementeras och riktat testas före installation; ingen förhandsaktivering eller gissad singleton-domän införs här.

Den enda samlade beställningen finns i `docs/flora-timing-completion-request-20261029.md`. Lokal leverans: `/workspace/deliveries/BB_FLORA_TIMING_COMPLETION_REQUEST_20261029/`. Den innehåller fyra konkreta exempel med fönsterstart, fönsterslut, duration och förklaring samt en förifylld privat CSV med exakt 91 grupper och medlemsbilaga för 775 behov. Källreferenser och proveniens kopieras oförändrade. Svars-/tidsfält är tomma; samma befintliga tidsmall kan refereras av flera tillämpliga grupper.

**Nya kontroller PASS:** statisk spårning av `original`-tilldelningen, fältinventering av kvarvarande input/profilbindning, CSV-återläsning med 91 unika grupper och exakt 775 unika medlemmar, oförvalda tider/beslut och oförändrade hashreferenser till tidigare testbevis. Inga motorfunktioner importerades eller kördes. **Återanvänt:** 18 motorprov och två parserkontroller mot frontend 95b9c43 samt tidigare giltigt webbläsarprov. Körbar motorkod är fortfarande ef72ae85; source_basis och 292 segment ändras inte av denna dokumentationsleverans.

Installationsplanen ovan kompletteras med beställningens godkännandekriterier: styrkt källa → exakt medlems-/datumbindning → laglig låst tid/behörig flytt inom originalfönstret → riktade regressions- och parserprov → ny fryst commit/profilhash → separat installations- och körmandat. Inget sådant mandat har utnyttjats här. Ingen optimering eller genomförbarhet har verifierats.
