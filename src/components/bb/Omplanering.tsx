import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { VyProps } from "@/lib/bb/vy";
import { lasMotorSummary } from "@/lib/bb/vcFlode";

/** Struktur för live-omplanering. Påverkan räknas inte om i UI. */
export function Omplanering({ api }: VyProps) {
  const [person, setPerson] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [visad, setVisad] = useState(false);
  const summary = lasMotorSummary(api.motorResultat());
  const lasta = api.schemaPass().filter((p) => p.last);
  const andrade = api.schemaForandringar();

  return (
    <div className="space-y-4">
      <div>
        <div className="text-[11px] font-bold tracking-widest text-primary uppercase">Förändring under perioden</div>
        <h2 className="mt-1 text-2xl font-extrabold text-deep">Omplanering</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Beskriv vad som hänt, till exempel att en medarbetare är sjuk. Förslaget och konsekvensen kommer från
          beräkningen – inte från sidan.
        </p>
      </div>

      <Card className="rounded-2xl p-6 shadow-lift">
        <h3 className="text-base font-extrabold text-deep">Förändring</h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <label className="text-sm font-semibold text-deep">
            Medarbetare
            <Input className="mt-1" value={person} onChange={(e) => setPerson(e.target.value)} placeholder="Namn" />
          </label>
          <label className="text-sm font-semibold text-deep">
            Från
            <Input className="mt-1" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="text-sm font-semibold text-deep">
            Till
            <Input className="mt-1" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </label>
        </div>
        <Button className="mt-4" type="button" onClick={() => setVisad(true)}>
          Visa påverkan
        </Button>
      </Card>

      {visad ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="rounded-2xl p-6 shadow-lift">
            <h3 className="font-extrabold text-deep">Påverkan</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {person || "Medarbetare"} {from && to ? `${from}–${to}` : ""} påverkar pass som ligger i intervallet.
              Låsta pass räknas men flyttas inte.
            </p>
          </Card>
          <Card className="rounded-2xl p-6 shadow-lift">
            <h3 className="font-extrabold text-deep">Förslag</h3>
            <p className="mt-2 text-sm text-muted-foreground">{andrade.length} pass i senaste förslaget skiljer sig från originalet.</p>
          </Card>
          <Card className="rounded-2xl p-6 shadow-lift">
            <h3 className="font-extrabold text-deep">Konsekvens</h3>
            <ul className="mt-2 space-y-1 text-sm">
              <li>Kundtäckning: {summary?.coveragePercent != null ? `${summary.coveragePercent} %` : "–"}</li>
              <li>Kostnad: {summary ? `${Math.round(summary.cost / 100).toLocaleString("sv-SE")} kr` : "–"}</li>
              <li>Regelpåverkan: {summary?.hardViolations.length ?? api.regelbrott()} hårda avvikelser</li>
              <li>Ändrade pass: {summary?.changedShiftCount ?? andrade.length}</li>
            </ul>
          </Card>
          <Card className="rounded-2xl p-6 shadow-lift">
            <h3 className="font-extrabold text-deep">Beslut</h3>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="button" onClick={() => api.setTab("schemaforslag")}>
                Godkänn ändring
              </Button>
              <Button type="button" variant="outline" onClick={() => setVisad(false)}>
                Avbryt
              </Button>
            </div>
          </Card>
        </div>
      ) : null}

      {lasta.length ? (
        <p className="text-xs text-muted-foreground">{lasta.length} låsta pass ingår i vilovillkor och SSG men visas diskret.</p>
      ) : null}
    </div>
  );
}
