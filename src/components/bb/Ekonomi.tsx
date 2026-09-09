import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, Info, Wallet, Clock } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { VyProps } from "@/lib/bb/vy";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

const DETALJ = [
  "Aktuell personalbudget",
  "Budgetavvikelse före reserv",
  "Ekonomisk reserv",
  "Prognos korttidsfrånvaro",
  "Beslutad bemanningsbuffert – värde",
  "Budgeterade personaltimmar",
];

const TIMMAR = [
  "Planerad schematid",
  "Planerad bruttotid",
  "Budgeterad medarbetartid",
  "Tillgänglig medarbetartid",
  "Vakanta timmar",
  "Övrig planerad tid",
];

export function Ekonomi({ d, api }: VyProps) {
  if (!d || !api.hasBer()) {
    return (
      <Card className="rounded-2xl p-8 text-center shadow-lift">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary text-xs font-extrabold text-deep">
          XLS
        </div>
        <h2 className="mt-4 text-xl font-extrabold text-deep">Ekonomin kan inte visas ännu</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
          Bladet Beräkningar saknas i den inlästa filen. Läs in en fil som innehåller modellbladen, så visas
          verksamhetens egna ekonomital här.
        </p>
        <Button className="mt-5" onClick={() => api.valjFil()}>
          <FileText /> Välj Excel-fil
        </Button>
      </Card>
    );
  }

  const kr = api.kr;
  const h1 = api.h1;
  const tal = (namn: string) => {
    const v = api.ber(namn);
    return typeof v === "number" ? v : null;
  };
  const krRad = (namn: string) => {
    const v = tal(namn);
    return v == null ? "–" : kr(v);
  };
  const hRad = (namn: string) => {
    const v = tal(namn);
    return v == null ? "–" : h1(v) + " h";
  };
  const def = (namn: string) => (api.berDef ? String(api.berDef(namn) || "") : "");
  const period = api.ber("Antal dagar i period");

  const kort: [string, string, string, boolean][] = [
    ["Månadsintäkt", krRad("Månadsintäkt"), "Datumstyrd ersättning per kund", true],
    ["Ren schemakostnad", krRad("Ren schemakostnad"), "Planerad schematid × timkostnad", false],
    ["Total kostnadsprognos", krRad("Total kostnadsprognos"), "Schemakostnad + korttidsfrånvaro m.m.", false],
    [
      "Disponibelt efter reserv",
      krRad("Disponibelt utrymme efter ekonomisk reserv"),
      "Budgetavvikelse − ekonomisk reserv",
      false,
    ],
  ];

  const Tabell = ({
    ikon,
    etikett,
    rubrik,
    rader,
    format,
  }: {
    ikon: React.ReactNode;
    etikett: string;
    rubrik: string;
    rader: string[];
    format: (n: string) => string;
  }) => (
    <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
      <div className="flex items-center gap-3 px-6 pt-6 pb-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-secondary text-deep">{ikon}</span>
        <div>
          <Eyebrow>{etikett}</Eyebrow>
          <h2 className="mt-0.5 text-lg font-extrabold text-deep">{rubrik}</h2>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <tbody>
            {rader.map((namn) => (
              <tr key={namn} className="border-t border-border/60 transition-colors hover:bg-muted/40">
                <td className="px-6 py-3 align-top">
                  <div className="font-semibold text-deep">{namn}</div>
                  {def(namn) ? (
                    <div className="mt-0.5 max-w-md text-[11px] leading-snug text-muted-foreground/80">{def(namn)}</div>
                  ) : null}
                </td>
                <td className="px-6 py-3 text-right font-bold whitespace-nowrap text-deep tabular-nums">
                  {format(namn)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-6 shadow-lift md:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Eyebrow>Ekonomi · hela perioden</Eyebrow>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-deep md:text-3xl">
              Intäkter mot kostnader
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
              Talen är verksamhetens egna, hämtade direkt ur modellens Beräkningar-blad för hela perioden
              {period != null ? ` (${period} dagar)` : ""}. De ändras inte av periodväljaren i Översikt.
            </p>
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="secondary" className="gap-1 rounded-full px-3 py-1 text-xs font-bold">
                <Info className="size-3.5" /> Ur filens egna beräkningar
              </Badge>
            </TooltipTrigger>
            <TooltipContent>Inget räknas om här – siffrorna speglar filen.</TooltipContent>
          </Tooltip>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {kort.map(([etikett, varde, not, mal], i) => (
            <div
              key={etikett}
              className="bb-rise rounded-2xl border border-border/70 bg-card p-5 shadow-lift transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift-lg"
              style={{ animationDelay: `${i * 60}ms`, borderLeftWidth: 4, borderLeftColor: mal ? "var(--ok)" : "var(--djup)" }}
            >
              <div className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">{etikett}</div>
              <div className="mt-2 text-2xl font-extrabold tracking-tight text-deep tabular-nums">{varde}</div>
              <div className="mt-1 text-xs leading-snug text-muted-foreground/80">{not}</div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Tabell
          ikon={<Wallet className="size-4" />}
          etikett="Ekonomi i detalj"
          rubrik="Budget och reserver"
          rader={DETALJ}
          format={krRad}
        />
        <Tabell
          ikon={<Clock className="size-4" />}
          etikett="Personaltid"
          rubrik="Timmar i perioden"
          rader={TIMMAR}
          format={hRad}
        />
      </div>
    </div>
  );
}
