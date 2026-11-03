# Vintergatan: avstämning av Medvind före optimering

Status enligt Bemanningsbibeln v16.32, avsnitt 8d: **källrader avstämda,
jämförbart före ännu inte låst**. Detta är inte
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
| Vikarier, tidsatta i detta utdrag | Inga rader | 0 | Endast i detta utdrag; separat fullständig vikariesumma saknas |
| Vakanser, beräkningsantagande | 65,37 % × 148 h + 6,5 h | 103,2476 | **Otidsatt komplettering**, inte Medvind-bokning eller kundbehov |

Periodgränspasset har inget nettotidsavdrag i Medvind; dess 155 minuter inom
perioden har därför räknats som rapporterad betald tid. **27 pass över fem
timmar saknar ett redovisat avdrag om minst 30 minuter** (inklusive
avrundningsskillnader på 0,2 minut). Detta är en käll-/rastfråga. Vi har inte
lagt in ett påhittat rastläge, och samma regeldefinition kan därför ännu inte
certifieras mellan Medvind och det nya förslaget.

Innan före får låsas krävs bekräftelse på att detta är hela Medvinds
TV/vik-tidsutdrag för perioden, hur de 27 rapporterade långa passen ska
behandlas, och om de tre vakansposterna ska läggas till som uttrycklig
komplettering utanför Medvind. Kompletteringen får inte räknas igen om den
redan ingår i en senare fullständig Medvindtotal. SSG-/avtalstimmar och
ramen 1 230,24/103,2476/1 333,4876 h hålls separat från Medvindutfallet.

`scripts/vg_medvind_baseline_audit.py` reproducerar kontrollen med endast
aggregat i utdata. Privat person-/kundinnehåll finns enbart i skyddade
källfiler; inga sådana rader hör hemma i GitHub.
