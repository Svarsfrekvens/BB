> **ÅTERKALLAD SOM AKTUELL BESTÄLLNING.** Patricias uttryckliga intervallbeslut ersätter kravet på separat exakt start för de 775 förekomsterna. Bevara detta dokument som historik; skicka eller besvara inte den tidigare beställningen. Se gällande status i `flora-patricia-timing-decision-20261029.md`. Endast 132 uttryckliga händelsevillkor kvarstår, inte 775 krav på starttider.

# Flora – en samlad beställning av befintliga tidsuppgifter

**Syfte:** komplettera tidskopplingen för ett framtida, isolerat Flora-prov. Detta är en beställning av befintligt källunderlag, inte ett nytt generellt flyttbeslut. Ingen körning beställs här.

**Omfattning:** FLORA-RADATA, P2, 2026-05-11–2026-06-07 inklusive slutdatum, Europe/Stockholm. Endast 775 kvarvarande förekomster i 91 befintliga granskningsgrupper. De 676 färdigbehandlade behoven ska inte besvaras igen.

Använd `private/KOMPLETTERING_91_GRUPPER.csv`. Grupp-ID, kundkod, aktivitet, dagklass, intervall, duration, antal och gruppsignatur är redan ifyllda. `private/group-members.json` anger exakta medlems-ID:n, datum och båda tidigare verifierade källreferenserna med proveniens. Ändra inte dessa förifyllda uppgifter.

## Lämna en samlad komplettering

För varje berörd grupp, eller gemensam dokumenterad mall som tydligt täcker flera grupper, lämna:

1. **Källa:** dokument/systemreferens, version eller datum och exakt rad/avsnitt. Bifoga endast nödvändiga tidsuppgifter via skyddad överlämning; inga journaler, tokens eller onödiga personuppgifter i chatten.
2. **Vilken tid uppgiften avser:** insatsens egen planerade start, måltidsankare, ordination, påminnelse eller utlösande händelse. En klocktid utan denna betydelse räcker inte.
3. **Den befintliga tidsuppgiften:** egen styrkt start, eller styrkt händelseankare och eventuell dokumenterad offset. Om en tillämplig befintlig tids-/flyttregel redan finns, ange dess referens och exakta omfattning; beställningen kräver inte ett nytt beslut för samma regel.
4. **Giltighet:** berörda grupp-ID:n, datumintervall och eventuella datum-/kundundantag. Ange vilken verksamhetsfunktion som kontrollerat att källan gäller.

En styrkt insatsstart och den redan bundna durationen räcker för att beräkna slut; separat slut behöver bara anges om den finns i källan. Den måste då överensstämma med omfattningen. Obligatoriska är källa, betydelse, tillämplig tidsuppgift och giltighet – inte samtliga valfria CSV-kolumner.

En mall lämnas en gång med ett `shared_template_id`; referera samma mall på de grupper den omfattar. Kundvillkor, ordination, dagklass och datumundantag får inte försvinna genom gruppering. Använd `missing_or_not_available` om uppgiften faktiskt saknas; fyll inte i intervallstart som nödlösning. Alla svar står från början som `UNANSWERED` och innebär ingen automatisk godkännandemarkering.

| Typ | Grupper / förekomster | Minsta komplettering | Rekommendation |
|---|---:|---|---|
| Måltider | 12 / 92 | Befintlig bestämd insatsstart, alternativt måltidsankare med styrkt relation till hela insatsen | Återanvänd kundens måltidsmall; bevara transport, tillsyn och förberedelse. |
| Medicin/ordination | 56 / 516 | Behörigt styrkt ordinationstid/tidsregel och nödvändigt händelsevillkor | Hämta redan gällande uppgifter från ansvarig funktion. Varken VC eller kod ska uppfinna medicinska testtider. |
| Påminnelser | 16 / 63 | Egen bestämd start eller redan gällande beslut om placering inom originalintervallet | Återanvänd en gemensam tillämplig regel, men skilj påminnelsen från aktiviteten. |
| Händelsebundna | 7 / 104 | Styrkt koppling och tidinformation för rök-/avfärdshändelse | Använd befintlig dags-/händelseplan. Om händelsen inte kan tidssättas, markera detta uttryckligen för avgränsat ställningstagande. |

## Fyra konkreta exempel

Start och slut nedan är **källans fönstergränser**, inte verifierade originalplaceringar. Senaste matematiska start säger bara vad som ryms, inte vad som är tillåtet att flytta.

| Typ / grupp | Datum | Befintlig fönsterstart | Befintligt fönsterslut | Varaktighet | Varför det inte räcker |
|---|---|---|---|---:|---|
| Måltid, FL-TID-G056 | 2026-06-04 | 07:00 | 08:00 | 5 min | Insatsen ryms matematiskt vid flera starter mellan 07:00 och 07:55. Ingen av dessa är styrkt som den bestämda tiden. |
| Medicin, FL-TID-G001 | 2026-05-11 | 08:00 | 09:00 | 10 min | 08:00–08:50 är matematiskt möjliga starter, men raden hänvisar till en läkemedelslista. Den ordinerade tiden kan inte väljas ur intervallet. |
| Påminnelse, FL-TID-G049 | 2026-05-15 | 18:50 | 19:00 | 5 min | Egen start kan matematiskt vara 18:50–18:55. Dusch kl. 19 gäller den senare aktiviteten; påminnelse kl. 19 skulle dessutom sluta utanför fönstret. |
| Händelsebunden tillsyn, FL-TID-G139 | 2026-05-11 | 08:45 | 08:55 | 5 min | Matematiska starter 08:45–08:50 visar inte när kunden har lämnat hemmet. Avfärdsvillkoret saknar en styrkt tidskoppling. |

För samtliga fyra exempel saknas verifierad egen originalstart och eget originalslut. Historisk registrering under `Utförd kl.` är inte verifierad planerad start eller händelsetid. Personalens originalpass ger heller ingen behovsspecifik placering.

## Vad som redan är klart

Alla 1 451 behov, originalintervall, durationer, personalantal, individuella krav och 292 originalsegment bevaras. De 500 tillåtna flyttförslagen och 176 entydiga starterna behöver ingen ny granskning. De 286 analysutvidgningarna och åtta K3-undantagen är inaktiva.

Tillstånd att förbereda frukost kvällen innan är redan beslutat. Första provet kan behålla sammansatta originalinsatser intakta. Ny uppdelning över dygnsgräns ingår inte i denna beställning.

## Godkännandekriterier efter komplettering

- Varje tidsuppgift har en spårbar källa och exakt täckning av gruppmedlemmar/datum. Ingen dubbel, motsägande eller saknad koppling döljs.
- Låsta tider binds serverstyrt till rätt källa. `original=window_start` i äldre modellfält får inte användas som oberoende placeringsbevis.
- Tidsuppgiften ryms med full duration i originalets EXECUTION_WINDOW och bevarar personalantal och individuella beroenden. Konflikt redovisas; originalintervallet vidgas inte automatiskt.
- Befintligt serverkontrakt har ännu ingen separat policy för en styrkt låst start inuti ett bredare intervall. När en sådan källa finns behöver dess exakta bindning införas och riktat testas. Enbart ifyllt underlag gör alltså inte motorn körklar.
- Positivt råresultat ska gå genom aktuell frontend `95b9c43ee92751397ddd066b2379e28a54a33df9`. Negativt prov ska avvisa ändrad start/källa, bortfall eller otillåten flytt. Giltiga oförändrade tester återanvänds.
- Alla 1 451 kontraktsrader och `source_basis`/292 segment bevaras. Kvarvarande `REVIEW_REQUIRED` innebär fortsatt stopp för fullständigt Flora-prov.
- Frys ny motorkommit och profilhash först efter godkända kontroller. Verifiera därefter, under separat installationsmandat, aktuell deployment, isolerat mål, rollback och operativ baseline. Körmandat ska ange exakt request och tids-/kostnadsgräns innan ett verkligt jobb tillåts.
- Ett senare resultat redovisar olösta behov och styrkta från-/till-förändringar. VC granskar före godkännande; gällande schema ersätts aldrig automatiskt.

**Rekommenderat nästa steg:** låt verksamheten lämna en enda komplettering med de redan gällande tidsmallarna/ordinationerna och gruppreferenserna ovan. Begär särskilt besked endast där dessa källor verkligen saknas. Inget nytt generellt flyttgodkännande efterfrågas.
