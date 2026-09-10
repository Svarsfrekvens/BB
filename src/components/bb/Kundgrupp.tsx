import { ArrowRight, CheckCircle2, FileSpreadsheet } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fmtH } from "@/lib/bb/vy";
import type { VyProps } from "@/lib/bb/vy";
import { Slappyta } from "./Slappyta";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

function Rad({ etikett, varde }: { etikett: string; varde: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2 last:border-0">
      <span className="text-sm text-muted-foreground">{etikett}</span>
      <strong className="text-sm font-bold tabular-nums text-deep">{varde}</strong>
    </div>
  );
}

/** Steg 2: ladda upp kundgruppen (Sekoia-rapporten). */
export function Kundgrupp({ api }: VyProps) {
  const u = api.underlag();
  const sekoia = u.sekoia;

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <Eyebrow>Steg 2 · Kundgrupp</Eyebrow>
        <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">Ladda upp kundgrupp</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Ladda upp fil från Sekoia. Kundgruppen måste laddas upp först – den visar vad kunderna faktiskt behöver, och
          filen sparas orörd så du alltid kan jämföra mot originalet.
        </p>
      </Card>

      <Card className="gap-0 rounded-2xl p-7 shadow-lift">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Eyebrow>1 · Kundgrupp</Eyebrow>
            <h3 className="mt-1 text-lg font-extrabold text-deep">Fil från Sekoia</h3>
          </div>
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
            <FileSpreadsheet className="size-5" />
          </span>
        </div>

        {sekoia ? (
          <>
            <Badge className="mt-4 w-fit rounded-full bg-success-soft px-3 py-1 text-xs font-bold text-success">
              <CheckCircle2 className="size-3" /> Inläst · {sekoia.kunder} kunder · {sekoia.insatser} insatser ·{" "}
              {fmtH(sekoia.timmar)} behovstid
            </Badge>
            <div className="mt-4">
              <Rad etikett="Insatser" varde={String(sekoia.insatser)} />
              <Rad etikett="Kunder" varde={String(sekoia.kunder)} />
              <Rad etikett="Period i filen" varde={`${sekoia.from} – ${sekoia.to}`} />
              <Rad etikett="Tid hos kund" varde={fmtH(sekoia.timmar)} />
              <Rad etikett="Period som analyseras" varde={`${u.period.from} – ${u.period.to}`} />
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => api.valjFil()}>
                Byt fil
              </Button>
              <Button onClick={() => api.setTab("schemafil")}>
                Nästa: ladda upp schema <ArrowRight />
              </Button>
            </div>
          </>
        ) : (
          <Slappyta
            text="Släpp Sekoia-filen här"
            hjalp="Excel (.xlsx) med bladet Rapport – tider, längd, kund och om insatsen är fast eller flyttbar."
            onFil={(f) => api.hanteraFil(f)}
            onValj={() => api.valjFil()}
          />
        )}
      </Card>
    </div>
  );
}
