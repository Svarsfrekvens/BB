# QA-testrapport – Galaxen

Datum: 2026-09-09 23:49 (Stockholm)
Underlag: `qa/fixtures/Galaxen_sekoia.xlsx` (kundernas behov) och `qa/fixtures/Schema_galaxen.xlsx` (personalschemat)
Körning: `npx vitest run` – **8 av 8 kontroller passerar**, 0 misslyckas.

## Sammanfattning

| # | Kontroll | Facit | Resultat |
| - | -------- | ----- | -------- |
| 1 | Alla insatser och rätt period läses in | 2 541 insatser, 2026-08-03 – 2026-08-30, 28 dagar | Passerar |
| 2 | Kundernas behov och antal kunder | 578,8 h, 11 kunder (inkl. Gemensam) | Passerar |
| 3 | Statusfördelning för uppföljningen | 2 324 utförda, 164 inställda, 50 flyttade, 3 ej utförda | Passerar |
| 4 | Medarbetare, vikarier och pass | 11 schemarader varav 6 vikarier, 143 pass, 40 vakanta | Passerar |
| 5 | Schematid och jourtid hålls åtskilda | 832,0 h schematid, 210,0 h sovande jour | Passerar |
| 6 | Sysselsättningsgrad läses ur schemaraden | Topas 70 % | Passerar |
| 7 | Kundnära tid och dimensionerande behov | 69,6 % (578,8 ÷ 832,0), 793,8 h | Passerar |
| 8 | Intäkt räknas utan Gemensam | 10 kunder × 2 500 kr × 28 dagar = 700 000 kr | Passerar |

## Varför de passerar

1. **Insatser och period.** Läsningen av kundfilen tolkar dag/månad rätt, så alla 28 dagar i augusti finns och inget datum hamnar på samma dag i varje månad.
2. **Kundernas behov.** Summan av insatstiderna ger 578,8 timmar och de elva kundrubrikerna hittas, inklusive den gemensamma raden.
3. **Statusfördelning.** Varje insats behåller sin status ur filen, vilket är grunden för uppföljningen mot verkligt utfall.
4. **Medarbetare och pass.** Tidigare räknades bara vakanta rader som redan hade utlagda pass, vilket gav 9 rader och 4 vikarier. Läsningen tar nu med alla vakanta schemarader, eftersom de är kapacitet som kan bemannas av vikarie. Därför blir det 11 rader varav 6 vikarier.
5. **Schematid och jour.** Sovande jour räknas separat och blandas aldrig in i schematiden, så 832,0 timmar arbetstid och 210,0 timmar jour redovisas var för sig.
6. **Sysselsättningsgrad.** Graden hämtas ur schemaradens text, inte ur ett antagande.
7. **Kundnära tid.** Måttet är genomgående kundernas behov delat med planerad schematid. Testet läser numera värdet ur `kundbehovAvPlanerade`, som är kärnans egna namn på just den formeln – formeln och talen är oförändrade.
8. **Intäkt.** Den gemensamma raden räknas inte som intäktsgrundande kund, så tio kunder ger 700 000 kronor för perioden.

## Åtgärder som krävdes för att nå grönt

- Kundfilens läsning flyttades till en egen modul (`src/lib/bb/sekoia.ts`) så den kan kontrolleras isolerat. Beräkningskärnan `core.ts` är orörd.
- Schemaläsningen fungerar nu även utanför webbläsaren, vilket krävdes för att kontrollerna ska kunna köras automatiskt.
- Vakanta schemarader utan utlagda pass räknas med (punkt 4 ovan).

## Utöver sifferkontrollerna

Genomflödet i webbläsaren (`npx playwright test --config qa/playwright.config.ts`) passerar också: appen startar tom, båda filerna läses in, bemanningsbalansen skapas och samma schematid efter balans visas i både Före & efter och Bemanning – utan fel i webbläsaren.
