# Vintergatan: avstämning av Medvind före optimering

Status enligt Bemanningsbibeln v16.32, avsnitt 8d: **källrader avstämda,
fullständig Medvind-total ännu inte styrkt, jämförbart före inte låst**. Detta är inte
en sparad arbetskopia eller ett nytt schema.

Det verifierade Medvind-originalet `vinterg ssg mm.xlsx` har SHA-256
`9c7f372e04b75ae3361915d35997389a388a2a40f4e798dd74b18bb0e9809deb`.
Samtliga **145** rader i `Medvind!A2:J146` motsvarar varsin rad i
`SCHEMA_DEC!A2:N146` i den verifierade decemberarbetsboken med SHA-256
`d7952d4d7038a276bbf5413dff18dc29fe03f07103223988d62a56cd14fb874c`.
Alla 145 värden i Medvinds `Summa` stämmer exakt mot arbetsbokens
`netto_timmar`. Inga rader saknas, är dubblerade eller har okänd personaltyp.

| Storhet | Källa | Timmar | Status |
|---|---|---:|---|
| Tillsvidare, rapporterad radsumma | 145 tidsatta Medvind-pass, 9 personer | 1 178,94 | Exakt summa av rapporterade decimalvärden |
| Tillsvidare, klippt till 2–29 december | 144 helt inre pass + 155 minuter av ett gränspass | 1 171,693333… | Periodklippt enligt Medvinds **rapporterade** netto; decimalvärdena är avrundade i källan |
| Vikarier, tidsatta i detta utdrag | Inga rader | 0 | Endast i detta utdrag |
| Faktisk vikarietid i hela Medvind | Separat totalrapport ännu inte funnen | **Okänd** | Får inte fyllas med utdragets noll |
| Vakanser, beräkningsantagande | 65,37 % × 148 h + 6,5 h | 103,2476 | **Otidsatt komplettering**, inte Medvind-bokning eller kundbehov |

Periodgränspasset har inget nettotidsavdrag i Medvind; dess 155 minuter inom
perioden har därför behållits som **rapporterad nettotid enligt Medvind**.
**27 pass över fem timmar saknar ett redovisat avdrag om minst 30 minuter**
(inklusive avrundningsskillnader på 0,2 minut). Detta är en käll-/rastfråga.
Användaren har beslutat att originalets rapporterade netto ska behållas utan
ytterligare 30-minutersschablon. Rastläget är inte verifierat; kalla därför
inte denna tid verifierad betald tid. I det nya förslaget ska beslutad rast
däremot placeras och täckas.

Användaren bekräftar **inte** att de 145 passen är hela Medvind. Genomsökning
av det verifierade decemberkällpaketet och BB:s privata artefaktlista fann
ingen separat decemberrapport med TV-, vikarie- och totalsummor. De två
`axmedvind`-filerna avser veckorna 44–47, och den andra filen med Medvind i
namnet är ett externt arbetsschema; de är inte en total för denna verksamhet.
Decemberarbetsbokens `SCHEMA_DEC` är en bearbetning av det nämnda utdraget,
och `VAKANSER!A2:G4` är VC-underlagets antagande, inte tidsatta Medvindpass.
Ingen tillgänglig fil/blad/cell med separat faktisk TV/vik/total har därmed
kunnat anges. Detta är en konkret saknad källa, inte bevis för att den inte
existerar. Full Medvind-vikarietid är okänd tills källan hittas.

Den nuvarande leveransgrinden `scripts/vg_delivery_gate.py` kräver dessutom
minutexakta betalda intervall för sin Medvind-ledger. De 145 källraderna ger
avrundade decimalvärden för rapporterad nettotid och styrker inte var varje
historisk rast låg eller att tiden var betald. Grinden ska därför fortsätta
blockera leverans. När en fullständig Medvindtotal finns måste dess exakta
källceller bindas och grinden kunna bevara rapporterat decimalnetto utan att
konstruera betalda intervall eller dolda 30-minutersavdrag.

Vakansantagandet 103,2476 h redovisas separat. Det får inte bli faktiskt
Medvindutfall eller adderas igen om det finns i en senare fullständig total.
SSG-/avtalstimmar och ramen 1 230,24/103,2476/1 333,4876 h hålls separat
från Medvindutfallet. Optimeringsscenarier får fortsätta mot beslutade behov
och villkor, men ingen verifierad Medvindbesparing får påstås.

`scripts/vg_medvind_baseline_audit.py` reproducerar kontrollen med endast
aggregat i utdata. Privat person-/kundinnehåll finns enbart i skyddade
källfiler; inga sådana rader hör hemma i GitHub.

## Kontroll av kompletterande privat källarkiv 4 november

Användarens `VINTERGATAN_KALLUNDERLAG_20261104 (1).tar.xz` har SHA-256
`1f954cd8a3bc5abf8ef862f7fcfc6537e172a2b99dbcb5c085c087717592c1a6`.
Arkivet innehåller 50 manifestförda filer; alla storlekar och SHA-256 i
`FILFORTECKNING.txt` stämmer. Den ingående decemberarbetsboken och
`vinterg ssg mm.xlsx` har samma SHA-256 som ovan och ger inga nya faktiska
Medvindtotaler. De ytterligare Medvindutdragen avser maj–juli, juli–september,
veckor 44–47 samt externt arbete över oktober–december. Ingen av dessa är en
separat faktisk TV-, vikarie- och totalrapport för Vintergatan 2–29 december.
Kopplingsnycklar och VC-underlag ger planeringsramar, inte bokad Medvindtid.
Faktisk fullständig Före-total och vikarietid är därför fortsatt okända.
Privatarkivets innehåll och personrader publiceras inte i GitHub.

Ett separat inklistrat mejlutdrag anger 667 vikarieh för 27 juli–23 augusti
och 448 vikarieh för 24 augusti–20 september; frågan om decemberschema säger
uttryckligen att vikarier kan vara ännu inte inbokade. Utdraget ger alltså
inte faktisk vikarie-Före 2–29 december. Senare svar i samma tråd preciserar
30 administrationstimmar **per fyra veckor** (redan i Medvindpassen) och att
`0,0439` avser ett pass på 6,5 timmar. Dessa planeringsuppgifter får inte
adderas som en ny faktisk Medvindtotal.
