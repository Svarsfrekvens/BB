# Plan: Skapa en design-prompt baserad på Patricia's åtta designböcker

## Vad jag ska skapa

En sammanhängande **design-prompt** — ett direktiv till mig själv — som jag ska följa när jag designar och förfinar Bemanningsbalans. Den destillerar de konkreta, tillämpbara principerna från Patricia's böcker till en lista med regler, inte teori.

Jag har läst på om alla åtta böcker (webbsökningar + artikelhämtningar) och sammanställt deras nyckelprinciper. Prompten ska:
- Var tillämpbar på Bemanningsbalans specifikt (korall-röd accent, off-white bakgrund, stora tal, KPI-kort, stegrad 1–5) men generell nog att gälla framtida förfining
- Formulerad som **regler jag följer som standard**, inte abstrakt teori
- Spara som projektminne (mem://design/design-prompt) så den appliceras automatiskt i varje session, och visas även för Patricia som text

## Böckerna och vad jag tar från varje

- **About Face (Alan Cooper)** — Målstyrd design: designa för användarens mål, inte funktioner. Softwaren får inte vara oförskämd (skylla användaren, förhöra med "är du säker?"), göra ogrundade antaganden eller vara obskyr (jargon, dolda funktioner). Designa innan kod. Eliminera onödig "excise" (onödiga dialoger/steg).
- **Refactoring UI (Wathan & Schoger)** — Börja med en funktion inte en layout. Designa i gråskala först (hierarki via avstånd/kontrast/storlek, inte färg). Bygg palett i förväg: grå (8–10 nyanser), primär (5–10), accent (success/warning/error/info). Använd inte grå text på färgad bakgrund — använd transparent version av bakgrundsfärgen. Avståndsskala (4/8pt-grid), aldrig godtyckliga värden, större element behöver mer luft, avstånd visar relationer. Typskala; kombinera storlek+vikt+färg, inte bara storlek. Systematisera allt i förväg (färger, avstånd, typ, skuggor, radier). Skuggor = djup/hierarki.
- **Practical UI (Adham Dannaway)** — Logikstyrda regler: avstånd baserat på hur nära relaterat, 3:1 kontrast för gränssnittselement, en primärknapp per vy (primär/sekundär/tertiär), knappar ≥48×48 px, viktigt innehåll synligt, minskad teckenavstånd för stor text, förlita dig inte på färg ensam, undvik flera justeringar, 4,5:1 textkontrast, överväg att ta bort containers, bara regular/bold vikter, var konsekvent, förväxla inte minimalism med enkelhet, balansera ikon+text.
- **Design Manual (Adrian Kuleszo)** — Mobil-first, design-tokens, skuggor/blur för djup, iOS-/Material-konventioner, vanliga appflöden (onboarding, betalning, 13+ flöden), globala stilar och designsystem-basics.
- **Emotional Design (Don Norman)** — Tre nivåer: viscerala (utseende, direkt känsla, varumärke), behaviorella (användbarhet, effektivitet, fel), reflekterande (medveten tanke, självbild, mening över tid). Vackra saker fungerar bättre — affekt påverkar kognition. Designa för alla tre.
- **100 Things Every Designer Needs to Know (Weinschenk)** — Perifert seende + mönsterigenkänning; bitvis info fastnar bättre (4-elementarschunkar, progressiv avslöjande); berättelser; empati/spegelneuroner; minimera distraktioner för flow; dopamin via feedback; lagom med val (inte för mycket); glömska — designa för att folk glömmer.
- **Information Architecture (Rosenfeld & Morville, isbjörnen)** — Fyra system: organisation (scheman: ämne/uppgift/målgrupp/tid; strukturer: hierarki/matris/linjär/webb), etikettering (kontrollerad vokabulär, användarens språk inte intern jargon), navigation (beständig synlig > dold på desktop; ytan av IA, inte en ersättning), sök (mycket sökande = navigationsfel). IA före navigation-UI. Reflektera användarens mentala modell, inte organisationens.
- **Vitaly Friedman / Smashing** — Designprinciper är standarder teamet följer som default, inte smak. Förklarar vad man INTE gör lika mycket som vad man gör. Dieter Rams 10 principer (innovativt, nyttigt, estetiskt, begripligt, obtrusivt, ärligt, långsiktigt, grundligt, så lite som möjligt). Smarta gränssnittsmönster.

## Struktur på prompten

Sektioner:
1. **Kärnprinciper** — övergripande regler (målstyrd, systematiskt, tre nivåer)
2. **Hierarki & visuell struktur** — gråskala-först, storlek+vikt+färg, ett blickfång per vy
3. **Avstånd & layout** — 8pt-grid, avstånd visar relation, mindre rektanglar i större
4. **Färg & kontrast** — palett i förväg, WCAG AA (3:1 UI, 4,5:1 text), inte färg ensam
5. **Typografi** — typskala, regular/bold, teckenavstånd, max 60–80 tecken/rad
6. **Komponenter** — en primärknapp, ≥48px mål, ikon+text, ta bort onödiga containers
7. **Navigation & information** — beständig synlig nav, användarens språk, IA före UI
8. **Kognition & psykologi** — chunkar om 4, progressiv avslöjande, feedback/dopamin, lagom val, designa för glömska
9. **Interaktion & tillstånd** — inte oförskämd (skyll ej användaren), tydliga tomma lägen, fokusmarkering, rörelse dämpad
10. **Tillämpning på Bemanningsbalans** — specifika regler mot befintlig design (korall-röd, off-white, KPI-kort, stegrad 1–5, 15 flikar)

## Leverans

1. Skriv prompten som en markdown-fil och spara som projektminne `mem://design/design-prompt` + uppdatera `mem://index.md`
2. Visa hela prompten för Patricia i chatten som text så hon kan läsa och godkänna/justera

## Vad som inte ändras

Ingen kod, inga filer i src/. Endast minne + text till Patricia. Rör inga beräkningar eller befintlig funktionalitet.
