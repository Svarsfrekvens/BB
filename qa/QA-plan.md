# Kvalitetssäkring av Bemanningsbalans – förslag

Lärdomen från de senaste rundorna: `tsc` och `vite build` var gröna medan appen inte ens startade, och Före & efter visade 92,3 % kundnära med en formel ingen hade bestämt. Statiska kontroller räcker inte. Kvalitet ska mätas på **tre nivåer** och köras **automatiskt vid varje ändring**, så att varken Lovable eller vi behöver upptäcka fel i skärmbilder.

## Princip: Galaxen som facit

De två Galaxen-filerna är det enda underlaget. Talen nedan är verifierade för hand och blir **facit** som varje ändring måste klara. Ändras något av dem har koden brutit – aldrig tvärtom.

| Mått | Facit | Källa |
|---|---|---|
| Insatser | 2 541 | Sekoia Rapport |
| Period | 2026-08-03 – 2026-08-30 (28 dagar) | Sekoia (D/M-datum) |
| Kundbehov | 578,8 h | Σ Förväntad genomförandetid |
| Kunder | 11 (10 i intäkt, Gemensam Norrskenet exkl.) | Boende |
| Status | 2 324 utförd / 164 inställd / 50 flyttad / 3 ej utförd | Status |
| Medarbetare | 11 = 5 ordinarie + 6 vikarierader | Medvind |
| Pass / vakanta | 143 / 40 | Medvind |
| Schematid FÖRE (exkl. jour) | 832,0 h | Medvind Ar-pass |
| Sovande jour | 210,0 h | Medvind Jo-pass |
| Dimensionerande | 793,8 h | resurskurva inkl. nattgolv |
| Kundnära FÖRE | 69,6 % | 578,8 ÷ 832,0 |
| Intäkt | 700 000 kr | 10 × 2 500 × 28 |

## Nivå 1 – Enhetstester på beräkningskärnan (vitest)

**Vad:** `core.ts`, `medvind.ts`, Sekoia-parsern, `modell.ts`, `motorPayload.ts`, `motorResultat.ts`. Rena funktioner, inga React-komponenter.

**Startpaket:** `qa/tests/galaxen.core.test.ts` (bifogad) – 8 tester mot facit-tabellen. Förutsätter att `parseSekoiaRapport` exporteras ur `app.ts` (den ligger i dag inlåst i modulen – be Lovable exportera den, eller flytta den till `sekoia.ts`).

**Lägg till efterhand:**
- Datumtolkning: "3/8/26", "13-08-2026", "2026-08-13" → alla ska bli 2026-08-xx (buggen som gav "8:e i varje månad").
- Medvind-cell med tre pass separerade av radbrytning → tre pass, jour flaggad.
- `procentsatser` med `planeradeTimmar = 0` → `null`, inte division med noll.
- `byggMotorPayload`: koder matchar motorns regex, vikarier blir `active`, `rules` läses ur STYRANDE_VILLKOR, >1 600 insatser ger `overTak`.
- `tolkaMotorSchema`: UTC-minuter → rätt lokal tid över sommartidsomställning.

**Regel:** varje bugg vi hittar får först ett test som faller, sedan fixen.

## Nivå 2 – Röktest i riktig webbläsare (Playwright)

**Vad:** appen startar, filerna läses in, balansen skapas, samma tal syns i alla vyer. Det är exakt den kedjan som gick sönder utan att någon statisk kontroll märkte det.

**Startpaket:** `qa/e2e/galaxen.smoke.spec.ts` + `qa/playwright.config.ts` (bifogade). Testet:
1. kräver att menyn syns inom 15 s (fångar `initBB`-buggen),
2. kräver att "Vintergatan" aldrig förekommer,
3. läser in båda filerna och kontrollerar 2541 / 578,8 / 832,
4. skapar balans och kräver `Kundnära tid 69,6 % → 72,7 %`,
5. läser schematid EFTER i Före & efter och kräver **samma** tal i Bemanning och Ekonomi (fångar 3-timmarsdiffen),
6. kräver noll `pageerror`.

**Lägg till:** Börja om → tom app; ladda om sidan med sparat tillstånd → samma tal (inte äldre version); mobilviewport 390 px → bottenmeny synlig; motorläge mot en lokal motor i CI (`OPTIMIZER_URL`) med ett 7-dagarsfönster.

## Nivå 3 – Motorn (finns redan, behåll)

`motor/tests/` med 23 unittest är bra. Lägg till: ett test som kör `motor/bb/solver.py` på en 7-dagars-payload byggd ur Galaxen och kräver `OPTIMAL|FEASIBLE` + `validation.valid`. Då märks det om frontendens payload och motorns `check_input` glider isär.

## Invarianter som ska gälla överallt (skriv som tester, inte som instruktioner)

1. Kundbehov är oförändrat FÖRE → EFTER, alltid.
2. `kundnära = kundbehov ÷ schematid` – samma formel i Översikt, Före & efter, Ekonomi, Fråga appen.
3. Schematid EFTER är **ett** tal, beräknat av **en** funktion, visat identiskt i alla vyer.
4. Schematid härleds aldrig ur Sekoia när Medvind finns.
5. Ingen vy visar en grön bock utan en beräkning bakom (`ok: true` hårdkodat är förbjudet).
6. Inga hårdkodade utfall, procent eller belopp i vyer (grep i CI: `fakt: "` med siffra → fel).
7. `grep -rni vintergatan src public` = 0.
8. Sparat tillstånd med äldre `STATE_VERSION` kastas.

## CI – kör allt automatiskt

`qa/ci.yml` (bifogad) för GitHub Actions: tsc → eslint → vitest → Playwright → build → Vintergatan-grep, plus motorns unittest i Python. Röd pipeline = ingen publicering. Koppla Lovables GitHub-synk så att varje Lovable-ändring går genom samma kontroll.

## Arbetssätt med Lovable

- **Varje prompt slutar med "Klart när"-kriterier som är körbara tester**, inte beskrivningar. "Kundnära FÖRE = 69,6 %" i stället för "rätt formel".
- Be Lovable **rapportera testutfall**, inte skärmbilder: "vitest 14/14, playwright 1/1, unittest 24/24".
- **Publicera aldrig** utan grön pipeline. De två senaste felen (appen startar inte, gammal formel på publicerad sajt) hade båda stoppats av röktestet.
- Ny bugg → nytt test först (nivå 1 om det är en beräkning, nivå 2 om det är ett flöde).
- Facit-tabellen ovan ändras bara när underlaget ändras, och då i en egen commit med motivering.

## Första steget (till Lovable)

> Lägg in mappen `qa/` som bifogas. Exportera `parseSekoiaRapport` ur `app.ts` (eller flytta den till `src/lib/bb/sekoia.ts`). Installera `vitest`, `@playwright/test`. Lägg `"test": "vitest run"` och `"e2e": "playwright test"` i package.json. Kör båda och rapportera utfallet rad för rad. Om något test faller: ändra koden, inte testet – facit-talen är verifierade mot Galaxen-filerna. Lägg sedan `qa/ci.yml` som `.github/workflows/ci.yml`.
