# Ombyggnad till React-komponenter (shadcn/ui + Tailwind)

Regel för hela arbetet: ingen beräkning, formel eller regel ändras. Endast
presentationslagret flyttas från innerHTML till React-komponenter. Nyckeltal
kontrolleras efter varje steg (Kundbehov 1 142,1 h · Personalbehov 1 330,4 h ·
Dimensionerande 1 438,1 h · Planerad schematid 1 972,0 h · Kundnära 47,4 %).

- [x] Steg 0: bro mellan logik och React (`src/lib/bb/skal.ts`) – logiken
      publicerar skal-tillstånd i stället för att skriva HTML för menyn.
- [x] Steg 1: layoutskal i React – vänstermeny (ikon + namn + undertext,
      fällbar Avancerat, mobilmeny), topprad (rubrik, export, Skapa
      bemanningsbalans / Börja om), klickbar stegrad 1–5, demo-knapp.
- [x] Steg 2: Översikt i React (`src/components/bb/Oversikt.tsx`), data via
      `src/lib/bb/vy.ts`. Nyckeltal kontrollerade: 1 142,1 / 1 330,4 / 1 972,0
      i nuläget, 88,0 % och 1 392,5 h efter optimering.
- [x] Steg 3: Kundbehov i React (`src/components/bb/Kundbehov.tsx`) – shadcn
      Table/Card/Input/Checkbox/Tooltip, redigering av kund, typ, tider,
      minuter, dubbel, veckodagar, ny kund/insats/genomförandeplan, Återställ.
      Kontrollerat: 1 142,1 → 1 144,0 vid ändring, tillbaka till 1 142,1 efter
      Återställ.
- [x] Steg 4: Resursbehov (`src/components/bb/Resursbehov.tsx`) – nyckeltalskort,
      dagväljare, 30-min-staplar med tooltip, personal-linje, förklaringar.
      Kontrollerat: dagens topp 6,8 · periodens topp 7,7 · 1 438,1 h.
- [x] Steg 5: Bemanning (`src/components/bb/Bemanning.tsx`) – sex nyckeltal,
      utfällbara medarbetarkort med namn/status/SSG, ta bort, samt formulär för
      ny medarbetare. Tomt läge när bladet Medarbetare saknas (som förut).
- [x] Steg 6: Schema (`src/components/bb/Schema.tsx`) – bräde medarbetare ×
      dagar, dra-och-släpp via delad `flyttaPass()` i app.ts, regelvarningar och
      indikationer i tooltip, filter per medarbetare, Återställ.
- [x] Steg 7: Uppföljning (`src/components/bb/Uppfoljning.tsx`) – sex utfallskort
      plan mot faktiskt, samma värden som förut.
- [x] Steg 8: Ekonomi (`src/components/bb/Ekonomi.tsx`) – fyra nyckeltal + två
      tabellkort (budget/reserver, timmar), samma tal ur Beräkningar-bladet.
- [x] Per kund (`PerKund.tsx`), Åtgärder (`Atgarder.tsx`), Datakontroller
      (`Datakontroller.tsx`) – React, samma värden.
- [x] Steg 9: Sprid behov (`SpridBehov.tsx`), Intäkter (`Intakter.tsx`), Vad
      händer om (`Simulering.tsx`), Styrande villkor (`Villkor.tsx`),
      Inställningar (`Installningar.tsx`) – React, samma värden.

- [x] Steg 10: verksamhetsväxlare (`Verksamheter.tsx`) + importgranskning som
      Dialog (`ImportGranskning.tsx`)
- [x] Steg 11: "Fråga appen" som React-panel (`FragaAppen.tsx`) + demorutan i
      skalet
- [x] Steg 12: `bb-base.css` och `bb-bold.css` borttagna, ingen innerHTML ritar
      längre någon vy.

Avgränsning: ingen automatisk schemaoptimering eller ny regelmotor byggs här.

## Etapp 3 – Användbarhet (klar)

- [x] Återanvändbart tomt läge (`Tomt.tsx`) i Kundbehov, Bemanning, Schema,
      Uppföljning – ikon, förklaring och vägar vidare.
- [x] Bekräftelse före borttagning (`Bekrafta.tsx`) för insats, medarbetare och
      verksamhet + "Börja om" med Avbryt / Exportera först / Börja om.
- [x] Notiser (`Notiser.tsx`, `notis.ts`) för import, export, borttagning med
      Ångra i tio sekunder, och fel som stannar tills de stängs.
- [x] Laddningsläge: "Läser in…" vid filinläsning, "Optimerar…" på Skapa
      bemanningsbalans.
- [x] Inline-validering: ny kund (tomt/dubblett), ny medarbetare (namn, SSG).
- [x] Tangentbord och skärmläsare: fokusring, aria-label på ikonknappar och
      veckodagar, status alltid ikon + färg + text.
- [x] Hjälptexter (`Hjalp.tsx`) vid genomförandeplan och SSG.
- [x] Import som ersätter data varnar och erbjuder "Exportera först".

## Etapp 5 – Ny modell: före & efter (klar)

- [x] Personalschemat (Medvind-export) läses in: `src/lib/bb/medvind.ts` läser
      namn, sysselsättningsgrad, vakanta rader, arbetstid och sovande jour, och
      lägger schemarullen på riktiga datum.
- [x] `src/lib/bb/modell.ts`: FÖRE = inläst schema mot ursprungligt kundbehov,
      enkel omfördelning av flyttbara insatser inom deras fönster (fasta ligger
      kvar, personalens tillgänglighet väger tyngst), EFTER = samma schema mot
      omfördelat behov, plus jämförelse i klartext.
- [x] `byggNaivtNulage()` borttagen – nuläget är alltid verklig inläst data.
      Originalfilerna sparas orörda och "Tillbaka till originaldata" finns.
- [x] Nya sidor: Underlag, Före & efter, Schemaförslag. Huvudmenyn är fyra steg;
      alla tidigare vyer ligger under Avancerat.
- [x] Sekoias datum (dag-månad-år) tolkas rätt – tidigare hamnade en tredjedel
      av insatserna på fel månad.

Avgränsning: appen räknar, jämför och föreslår justeringar. Den lägger inte ett
färdigt lagligt schema automatiskt.

## Etapp 6 – Nytt flöde enligt mockup (klar)

- [x] Meny i mockupens ordning: Hem, Kundgrupp, Schema, Medarbetare,
      Dashboard, Jämför före och efter. Tekniska vyer ligger under Avancerat
      med Inställningar där.
- [x] Nya React-vyer: `Hem.tsx`, `Kundgrupp.tsx`, `SchemaFil.tsx`,
      `Medarbetare.tsx` samt delad dra-och-släpp-yta `Slappyta.tsx`.
- [x] Redigerbara medarbetaruppgifter: namn, sysselsättningsgrad, samordnare,
      delegering, sovande jour, lägg till medarbetare.
- [x] Flödet leder vidare av sig själv: Sekoia-import → Kundgrupp,
      schemaimport → Medarbetare, Skapa bemanningsbalans → Dashboard.
- [x] Typkontroll utan fel och webbläsartest utan konsolfel.

## Etapp 7 – ny modell/design (klar)
- Palett enligt mockup: papper #F7F9F8, djup #1F4A40, teal #2E9E8F, lila #7C5CD6.
- Meny: aktiv flik i djup grön med vit text, undertexter, gradient-logotyp.
- Hem byggd om: hero + citat, sjustegsflöde, verksamhetsval, statuschips, värdegrundsrad.
- Beräkningar orörda.

## Etapp 8 – meny och flöde enligt v3.0-koden (klar)
- Flöde: Underlag (ladda upp + skapa) och Resultat (före & efter)
- Arbeta vidare: Schema, Kundbehov, Ekonomi, Uppföljning
- Mer: övriga vyer, fällbar; låsta flikar med hänglås tills steget innan är klart

## Etapp 9 – schemaoptimering och styrande villkor (klar)
- [x] Koppla in steg B för personalschemat och spara passändringar/varningar.
- [x] Visa optimerat schema, resultat och åtgärder samt räkna om efter manuella flyttar.
- [x] Visa hela katalogen med styrande villkor grupperad och typmärkt.
- [x] Verifiera typkontroll och flödet i förhandsvisningen.

## Etapp 10 – Sekoia-läckage stängt (klar)
- [x] `schemaPerSlot()` bygger bemanningskurvan ur Medvind-pass (ej jour), inte Sekoia.
- [x] `viewOversikt()` daggraf använder Medvind-pass för schematid per dag.
- [x] `harleddModell()` personal härleds ur Medvind-pass (SSG, profil, nattbehörighet,
      vikarie) med Sekoia som märkt reserv ("uppskattad") utan schema.
- [x] Sprid behov visar ingen bemanningslinje när schema saknas, med ledtråd.
- [x] Verifierat mot Galaxen-data: 143 pass (115 ej jour + 28 jour), 799 h schematid,
      578,8 h kundbehov, 0 konsolfel. core.ts orörd.

## Etapp 11 – inbyggd optimeringsmotor (klar)
- [x] Motor-vyn kopplad till appens egen TypeScript-optimering (ingen extern tjänst).
- [x] `Motor.tsx` kör `api.skapa()` direkt, visar pass/insatser/ändringar, före-efter-tabell,
      regelvarningar och vikariebeslut. Befintligt schema ändras aldrig automatiskt.
- [x] Extern `motor.functions.ts`/`motorPayload.ts` ersatt av inbyggd motor; `core.ts` orörd.
- [x] Typkontroll ren, sidan renderar utan konsolfel.

## Etapp 12 – stabil extern optimeringsmotor (klar)
- [x] Ge motorn en giltig startlösning så stora underlag inte avslutas med `UNKNOWN` utan förslag.
- [x] Dela Galaxens period i högst tre dagar och 320 insatser per körning för att hålla varje anrop inom tidsgränsen.
- [x] Behåll alla hårda regler och redovisa behov som ännu inte kunnat bemannas öppet.
- [x] Kör hela motorns regel- och lösartestsvit.

## Etapp 13 – automatisk kvalitetssäkring mot Galaxen (klar)
- [x] `qa/`-paketet på plats: facit-fixturer, Vitest-tester, Playwright-röktest och CI-fil (`.github/workflows/ci.yml`).
- [x] Sekoia-läsaren flyttad till `src/lib/bb/sekoia.ts` så den kan testas isolerat; `core.ts` orörd.
- [x] `medvind.ts` läser XLSX även utanför webbläsaren och räknar med vakanta schemarader utan utlagda pass (11 rader, 6 vikarier).
- [x] 8/8 enhetstester gröna (2 541 insatser, 578,8 h, 832,0 h, 210,0 h jour, 793,8 h dimensionerande, 69,6 % kundnära, 700 000 kr).
- [x] Röktest grönt: uppladdning → balans → samma efter-schematid i Före & efter och Bemanning, inga konsolfel.
