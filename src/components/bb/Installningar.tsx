import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Building2, Settings2, Trash2, TriangleAlert } from "lucide-react";
import type { VyProps } from "@/lib/bb/vy";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

const FALT: [string, string, string][] = [
  ["Planerade personaltimmar i perioden", "plannedHours", "Summan av personalens tid i perioden"],
  ["Timkostnad (kr/h)", "hourlyCost", "Genomsnittlig kostnad per arbetad timme"],
  ["Bemanningsplanens längd (dagar)", "planDays", "Så många dagar planen omfattar"],
  ["Personalbudget (kr)", "budget", "Budgeten som kostnaderna jämförs mot"],
  ["Korttidsfrånvaro (%)", "absencePct", "Påslag för sjukfrånvaro i prognosen"],
  ["Ekonomisk reserv (%)", "reservePct", "Del av budgeten som hålls i reserv"],
];

export function Installningar({ state, api }: VyProps) {
  return (
    <div className="max-w-3xl space-y-4">
      <Card className="gap-0 rounded-2xl p-6 shadow-lift md:p-8">
        <Eyebrow>Verksamhet</Eyebrow>
        <h1 className="mt-1 flex items-center gap-2 text-2xl font-extrabold tracking-tight text-deep md:text-3xl">
          <Settings2 className="size-6 text-primary" /> Grunduppgifter
        </h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Talen här används i beräkningarna när filen inte innehåller ett eget värde. Ändringar syns direkt i alla flikar.
        </p>
        <div className="mt-6">
          <Label htmlFor="setOrg" className="flex items-center gap-2 text-xs font-bold text-deep">
            <Building2 className="size-3.5" /> Verksamhetens namn
          </Label>
          <Input
            id="setOrg"
            defaultValue={state.org}
            onBlur={(e) => api.setOrg(e.currentTarget.value)}
            className="mt-2 h-11"
          />
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        {FALT.map(([lab, key, hjalp]) => (
          <Card key={key} className="gap-0 rounded-2xl p-5 shadow-lift">
            <Label htmlFor={`set-${key}`} className="text-xs font-bold text-deep">
              {lab}
            </Label>
            <Input
              id={`set-${key}`}
              type="number"
              defaultValue={Number(state[key]) || 0}
              onBlur={(e) => api.setTal(key, e.currentTarget.value)}
              className="mt-2 h-11 font-bold tabular-nums"
            />
            <p className="mt-2 text-[11px] leading-snug text-muted-foreground/80">{hjalp}</p>
          </Card>
        ))}
      </div>

      <Card className="gap-0 rounded-2xl p-6 shadow-lift">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-extrabold text-deep">
              <TriangleAlert className="size-4 text-primary" /> Rensa all data
            </div>
            <p className="mt-1 text-[11px] leading-snug text-muted-foreground/80">
              Tar bort importen ur webbläsaren. Går inte att ångra.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => api.rensaAllt()}
            className="border-primary/60 text-primary hover:bg-primary/5 hover:text-primary"
          >
            <Trash2 /> Rensa
          </Button>
        </div>
      </Card>
    </div>
  );
}
