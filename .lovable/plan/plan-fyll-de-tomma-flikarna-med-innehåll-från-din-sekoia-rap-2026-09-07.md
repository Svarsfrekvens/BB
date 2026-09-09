# Plan: Fyll de tomma flikarna med innehåll från din Sekoia-Rapport

## Bakgrund och orsak

Din uppladdade Sekoia-fil innehåller bara bladet **Rapport** (3 379 insatser). Flikarna Ekonomi, Åtgärder, Intäkter och Bemanning kräver fyra modellblad som inte finns i filen:

| Flik | Kräver | Visar idag |
|------|--------|-----------|
| Ekonomi | `Beräkningar` (nyckelvärden) | tomt läge |
| Åtgärder | `Kontroller` (kontrollrader) | tomt läge |
| Intäkter | `Intäkter` (ersättning per kund/dygn) | tomt läge |
| Bemanning | `Personal` (medarbetare + budget) | tomt läge |

Appen härleder redan **Individschema** från Rapporten (därför fungerar Schema). Datakontroller-fliken räknar själv från datan och fungerar redan.

Eftersom du valde att härleda allt från Rapporten med branschtypiska startvärden, bygger vi en härledning som skapar dessa fyra modell-objekt från din Rapport + det redan härledda Individschemat + startvärdena i Inställningar. Då fylls flikarna med riktigt innehåll från din egen verksamhet.

## Vad som byggs

En ny funktion `harleddModell(rows, individschema, antaganden)` som körs vid import när filen saknar modellblad (bara Rapport). Den returnerar fyra objekt i exakt samma form som view-funktionerna redan förväntar sig, så **inga befintliga vyer eller beräkningar ändras** — core.ts rör vi inte alls.

### 1. Beräkningar (→ Ekonomi-fliken)
Nyckelvärden byggda från core.ts + Individschema + Inställningar:
- Antal dagar i period, Summerade kundinsatser (`nyckeltal.kundbehovH`), Samtidighetsbaserat resursbehov (`resurskurva.dimensionerandeH`)
- Planerad schematid = summa `Betald tid h` ur Individschema
- Planerad bruttotid, Budgeterad personaltid = budget ÷ timkostnad, Tillgänglig personaltid, Vakanta timmar, Övrig planerad tid
- Planerad kundnära andel = kundbehov ÷ schematid, Mål kundnära tid = 75 %
- Månadsintäkt (från Intäkter-härledningen), Ren schemakostnad = schematid × timkostnad
- Prognos korttidsfrånvaro, Total kostnadsprognos, Budgetavvikelse, Ekonomisk reserv, Disponibelt
- Beslutad bemanningsbuffert, Aktuell personalbudget, Dimensionerande direkt resursbehov

Ekonomi-fliken visar sedan KPI-kort + detaljtabeller precis som för en X2-import.

### 2. Kontroller (→ Åtgärder-fliken)
Rader byggda från `importkontroll()`-resultatet:
- Antal Sekoia-rader, Godkända rader, Avvisade rader, Antal kunder/gemensamma/fasta/flyttbara/dubbelbemannade
- Varje varning blir en rad med status ÅTGÄRD
- Modellstatus = "PASS" om inga varningar, annars "KRÄVER ÅTGÄRD"
- Kolumner: Kontroll | Utfall | Förväntat | Status | Åtgärd — exakt som viewAtgarder ritar

### 3. Personal (→ Bemanning-fliken)
En rad per medarbetare från Individschema:
- Medarbetare, Status = "Anställd", Budget h/mån = summa `Betald tid h`, Planerade h, Timkostnad = 270, Budgetkostnad/mån = budget × timkostnad, Passprofil från passens Slot (Natt/Dag/Kväll)
- Bemanning-fliken visar medarbetarkorten med redigering (SSG-reglage, byt namn, lägg till/ta bort) — allt finns redan

### 4. Intäkter (→ Intäkter-fliken)
En rad per kund per dag i perioden:
- Kunder från `perKund()` (exklusive `Gemensam`), Grund kr/dygn = 3 500 (branschtypiskt, redigerbart), Aktiv kund = 1, Intäktsfaktor = 1, Beräknad intäkt = 3 500
- Intäkter-fliken visar KPI-kort + tabell med redigerbar grundersättning och aktiv/inaktiv per kund — finns redan

## Startvärden (branschtypiska, justeras i Inställningar)

| Antagande | Startvärde | Var |
|-----------|-----------|-----|
| Timkostnad | 270 kr/h | redan default i `DEFAULT_VERKS` |
| Personalbudget | 460 000 kr | redan default |
| Korttidsfrånvaro | 4 % | redan default |
| Ekonomisk reserv | 6 % | redan default |
| Bemanningsbuffert | 4 % | ny default |
| Grundersättning | 3 500 kr/dygn | ny default |
| Mål kundnära tid | 75 % | ny default |

Alla är redan eller blir redigerbara i Inställningar. Användaren ändrar dem och flikarna räknas om.

## Hookpunkt

I `approveImport()` (rad 433–438): när `pendingMeta.berakningar/kontroller/personal/intakter` är null men Rapport + Individschema finns, anropas `harleddModell(...)` och resultaten stoppas in i `pendingMeta` innan de tilldelas `state`. Ingen annan del av importflödet ändras.

## Begränsningar (kravspec)

- **core.ts rörs inte** — beräkningarna är oförändrade; vi återanvänder `nyckeltal`, `resurskurva`, `ekonomi`, `procentsatser`, `importkontroll`, `perKund` som de är.
- **Befintliga view-funktioner rörs inte** — de ritar redan rätt när state är ifyllt.
- **Endast utseende/struktur-regeln** gäller inte här: användaren bad uttryckligen om innehåll i tomma flikar, vilket kräver att vi bygger datalagret som vyerna redan förväntar sig. Inga befintliga beräkningar ändras.
- UI-text på svenska.

## Verifiering

1. Importera Sekoia-filen → Översikt visar dina rader (3 379, Axelsberg)
2. Ekonomi: KPI-kort (Månadsintäkt, Ren schemakostnad, Total kostnadsprognos, Disponibelt) + detaljtabeller — inte tomt
3. Åtgärder: kontrolltabell med PASS/ÅTGÄRD-rader + modellstatus-pill — inte tomt
4. Intäkter: KPI-kort + redigerbar kundtabell med månadsintäkt — inte tomt
5. Bemanning: medarbetarkort med SSG-reglage — inte tomt
6. Ändra timkostnad i Inställningar → Ekonomi/Intäkter räknas om
7. Playwright-skärmdump av alla fyra flikar i desktop + mobilbredd
