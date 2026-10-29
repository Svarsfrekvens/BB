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
