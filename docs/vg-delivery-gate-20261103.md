# Vintergatan: spärr före leverans av ett optimerat förslag

Den tidigare C-filen `VG-20261202-bcd6252a503b` är **BLOCKED** för import som färdigt
schema. Den klarar pass- och behovskontroller men har inget låst fullständigt
Medvind-före, inget gemensamt optimeringsbevis och dess redovisade timmar räknar
hela två pass som går in i 30 december. Filen och manifestet ska bevaras med
ursprungliga kontrollsummor som ett granskningsspår, inte skrivas över.

## Obligatorisk ordning

1. Frys ett komplett Medvind-tidsutdrag för Vintergatan och 2–29 december med
   både tillsvidare och vikarier. Varje rad ska ha unik källreferens, explicit
   personaltyp och betalda intervall. Rastplacering måste vara styrkt för pass
   som korsar periodgränsen. Originalrapportens SHA-256 binds till normaliserad
   ledger. Saknad vikariesumma får inte ersättas med noll.
2. Lås en separat baseline: rapporterad tid, periodklippning, styrkta
   vakanskompletteringar och jämförelsetid per personaltyp. Varje vakans får
   läggas till högst en gång, endast om den inte redan finns i Medvind.
   SSG-/avtalstimmar är kapacitetskontroll, inte före-tid.
3. Beräkna samma beslutade kundbehov med ett gemensamt mål som i första hand
   minimerar vikariernas schemalagda nettotid och därefter total nettotid.
   En stegvis tilldelning av återstående arbete till vikarier räcker inte som
   optimeringsbevis. Spara modellens hash, solverlogg, målvärde, gräns och
   söktid för exakt kandidathash. En genomförbar kandidat får inte kallas
   optimal utan bevisad gräns.
4. Kör oberoende pass-/behovsvalidatorn och `scripts/vg_delivery_gate.py` på
   **exakt de filer som ska överlämnas**. Kontrollera periodklippt betald tid
   från personpass, samma 293 kr per aktiv timme, vaken natt och administration
   en gång. Läs gate-utdata: endast `READY_FOR_REVIEW` tillåter en versionsmärkt
   granskningsleverans; verksamhetsgodkännande och inloggad import är separata.

Gate-anropet kräver `candidate`, `--manifest`, `--source-report`,
`--source-workbook`, `--medvind-ledger`, `--baseline` och
`--optimization-proof`. Saknas någon av de tre sista bevisdelarna stannar
leveransen. Källrapporten måste granskas mot Medvind; hashbindning ensam
bevisar inte att rapporten är fullständig. Inte heller ersätter en solverlogg
oberoende kontroll av modellens omfattning och rätt kundbehov.

För den redan uppladdade C-kandidaten ger spärren `BLOCKED`: `AFTER_NOT_PERIOD_CLIPPED`,
`AFTER_COST_NOT_PERIOD_CLIPPED`, `LOCKED_MEDVIND_BASELINE_MISSING` och
`JOINT_OPTIMIZATION_PROOF_MISSING`. Hela pass ger 1 978 h 05 min, men
**periodklippt eftertid är 1 969 h 40 min** (tillsvidare 1 160 h 30 min,
vikarier 809 h 10 min), modellkostnad 577 112,33 kr. Det är fortfarande
inte en styrkt besparing mot faktiskt Medvind-före. En framtida korrigerad
kandidat måste få nytt ID, nya kontrollsummor och en uttrycklig ersättningsnotis.
