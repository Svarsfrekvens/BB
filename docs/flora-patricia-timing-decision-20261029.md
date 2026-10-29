# Flora – gemensamt tidsbeslut, 2026-10-29

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
