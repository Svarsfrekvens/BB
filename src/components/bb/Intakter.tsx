import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { FileText, RotateCcw, Coins, Pencil } from "lucide-react";
import type { VyProps } from "@/lib/bb/vy";
import type { BladRad } from "@/lib/bb/typer";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

export function Intakter({ d, api }: VyProps) {
  if (!d || !api.harIntakter()) {
    return (
      <Card className="rounded-2xl p-8 text-center shadow-lift">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary text-xs font-extrabold text-deep">
          XLS
        </div>
        <h2 className="mt-4 text-xl font-extrabold text-deep">Intäkterna kan inte visas ännu</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
          Bladet Intäkter saknas i den inlästa filen. Läs in HR-exporten (X2) så visas intäkterna här.
        </p>
        <Button className="mt-5" onClick={() => api.valjFil()}>
          <FileText /> Välj Excel-fil
        </Button>
      </Card>
    );
  }

  const kr = api.kr;
  const rader = api.intaktRader();
  const redigerad: boolean = api.intaktEditAktiv();
  const num = (r: BladRad, c: string) => {
    const v = r[c];
    return typeof v === "number" ? v : Number(v) || 0;
  };
  const total = rader.reduce((s, r) => s + num(r, "Beräknad intäkt"), 0);

  const perKund: Record<string, { kund: string; grund: number; dagar: number; summa: number; aktiv: boolean }> = {};
  for (const r of rader) {
    const k = String(r["Kund"] ?? "").trim();
    if (!k) continue;
    if (!perKund[k])
      perKund[k] = {
        kund: k,
        grund: num(r, "Grund kr/dygn") || num(r, "Ny ersättning"),
        dagar: 0,
        summa: 0,
        aktiv: Number(r["Aktiv kund"]) !== 0,
      };
    perKund[k].dagar++;
    perKund[k].summa += num(r, "Beräknad intäkt");
  }
  const kunder = Object.values(perKund).sort((a, b) => a.kund.localeCompare(b.kund, "sv"));

  const kort = [
    {
      lab: "Månadsintäkt totalt",
      val: kr(total),
      note: redigerad ? "räknas live ur dina ändringar" : "summa datumstyrd ersättning",
      mal: true,
    },
    ...kunder.slice(0, 3).map((k) => ({
      lab: k.kund,
      val: kr(k.summa),
      note: `${k.grund.toLocaleString("sv-SE")} kr/dygn`,
      mal: false,
    })),
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kort.map((k, i) => (
          <div
            key={k.lab}
            className="bb-rise rounded-2xl border border-border/70 bg-card p-5 shadow-lift transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift-lg"
            style={{ animationDelay: `${i * 60}ms`, borderLeftWidth: 4, borderLeftColor: k.mal ? "var(--ok)" : "var(--djup)" }}
          >
            <div className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">{k.lab}</div>
            <div className="mt-2 text-2xl font-extrabold tracking-tight text-deep tabular-nums">{k.val}</div>
            <div className="mt-1 text-xs leading-snug text-muted-foreground/80">{k.note}</div>
          </div>
        ))}
      </div>

      <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
        <div className="flex flex-wrap items-start justify-between gap-4 px-6 pt-6 pb-4 md:px-8">
          <div>
            <div className="flex items-center gap-2">
              <Eyebrow>Datumstyrd intäktsberäkning</Eyebrow>
              {redigerad ? (
                <Badge variant="secondary" className="gap-1 rounded-full text-[11px] font-bold">
                  <Pencil className="size-3" /> ändrat
                </Badge>
              ) : null}
            </div>
            <h1 className="mt-1 flex items-center gap-2 text-2xl font-extrabold tracking-tight text-deep">
              <Coins className="size-6 text-primary" /> Intäkter
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
              Ändra grundersättningen per dygn för en kund – beräknad intäkt och månadsintäkten uppdateras med en gång.
              Bocka ur en kund för att se effekten om ersättningen upphör. Den inlästa filen ändras aldrig.
            </p>
          </div>
          <Button variant="outline" disabled={!redigerad} onClick={() => api.aterstallIntaktEdit()}>
            <RotateCcw /> Återställ
          </Button>
        </div>
        <div className="max-h-[600px] overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 bg-card/95 backdrop-blur">
              <tr className="border-b border-border text-left text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                <th className="px-6 py-3">Kund</th>
                <th className="px-6 py-3">Grundersättning</th>
                <th className="px-6 py-3">Dagar</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Intäkt i perioden</th>
              </tr>
            </thead>
            <tbody>
              {kunder.map((k) => (
                <tr key={k.kund} className="border-t border-border/60 transition-colors hover:bg-muted/40">
                  <td className="px-6 py-3 font-semibold text-deep">{k.kund}</td>
                  <td className="px-6 py-3">
                    <span className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        step={100}
                        defaultValue={Math.round(k.grund)}
                        onChange={(e) => api.intaktSetGrund(k.kund, e.currentTarget.value)}
                        className="h-9 w-24 tabular-nums"
                        aria-label={`Grundersättning för ${k.kund}`}
                      />
                      <span className="text-xs text-muted-foreground">kr/dygn</span>
                    </span>
                  </td>
                  <td className="px-6 py-3 whitespace-nowrap tabular-nums">{k.dagar} dygn</td>
                  <td className="px-6 py-3">
                    <label className="flex items-center gap-2 text-xs font-semibold text-deep">
                      <Checkbox checked={k.aktiv} onCheckedChange={(v) => api.intaktSetAktiv(k.kund, !!v)} />
                      aktiv kund
                    </label>
                  </td>
                  <td className="px-6 py-3 text-right font-bold whitespace-nowrap text-deep tabular-nums">
                    {kr(k.summa)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-border bg-muted/30">
                <td className="px-6 py-4 font-extrabold text-deep" colSpan={4}>
                  Månadsintäkt totalt
                </td>
                <td className="px-6 py-4 text-right text-lg font-extrabold text-deep tabular-nums">{kr(total)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Card>
    </div>
  );
}
