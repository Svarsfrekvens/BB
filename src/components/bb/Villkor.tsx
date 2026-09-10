import { ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { VyProps } from "@/lib/bb/vy";

const typTon: Record<string, string> = {
  krav: "bg-danger-soft text-destructive",
  mål: "bg-blue-soft text-blue",
  gul: "bg-warning-soft text-warning",
  individ: "bg-primary-soft text-primary",
  uppfyllt: "bg-success-soft text-success",
  info: "bg-muted text-muted-foreground",
  ram: "bg-muted text-deep",
};

export function Villkor({ api }: VyProps) {
  const modell = api.villkor();
  const grupper = (modell?.["grupper"] ?? []) as { grupp: string; villkor: [string, string, string, string, string][] }[];
  const antal = grupper.reduce((sum, grupp) => sum + grupp.villkor.length, 0);

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <div className="flex items-start gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-primary-soft text-primary"><ShieldCheck className="size-5" /></span>
          <div>
            <div className="text-[11px] font-bold tracking-widest text-primary uppercase">Styrande villkor</div>
            <h1 className="mt-1 text-2xl font-extrabold text-deep">Regelverket bakom schemat</h1>
            <p className="mt-2 text-sm text-muted-foreground">{antal} villkor i {grupper.length} grupper styr kontroller och schemaförslag.</p>
          </div>
        </div>
      </Card>

      {grupper.map((grupp) => (
        <Card key={grupp.grupp} className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
          <div className="flex items-center justify-between px-6 py-5">
            <h2 className="text-lg font-extrabold text-deep">{grupp.grupp}</h2>
            <Badge variant="secondary">{grupp.villkor.length} villkor</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead><tr className="border-y border-border bg-muted/40 text-left text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                {['Villkor', 'Värde', 'Enhet', 'Kommentar', 'Typ'].map((h) => <th key={h} className="px-6 py-3">{h}</th>)}
              </tr></thead>
              <tbody>{grupp.villkor.map(([namn, varde, enhet, kommentar, typ]) => (
                <tr key={namn} className="border-b border-border/60">
                  <td className="px-6 py-3 font-semibold text-deep">{namn}</td>
                  <td className="px-6 py-3 font-bold tabular-nums text-deep">{varde}</td>
                  <td className="px-6 py-3 text-muted-foreground">{enhet}</td>
                  <td className="px-6 py-3 text-muted-foreground">{kommentar}</td>
                  <td className="px-6 py-3"><Badge className={cn("rounded-full", typTon[typ] ?? typTon["info"])}>{typ}</Badge></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
      ))}
    </div>
  );
}