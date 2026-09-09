import { useMemo, useState } from "react";
import { AlertTriangle, Moon, TrendingDown, TrendingUp, Upload } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { fmtH } from "@/lib/bb/vy";
import type { VyProps } from "@/lib/bb/vy";
import { TomtLage } from "./Tomt";

const VECKODAG = ["mån", "tis", "ons", "tor", "fre", "lör", "sön"];

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

function Kort({ etikett, tal, forklaring }: { etikett: string; tal: string; forklaring: string }) {
  return (
    <Card className="gap-0 rounded-2xl p-6 shadow-lift">
      <span className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">{etikett}</span>
      <strong className="mt-2 block text-3xl font-extrabold tabular-nums text-primary">{tal}</strong>
      <span className="mt-2 block text-xs leading-relaxed text-muted-foreground">{forklaring}</span>
    </Card>
  );
}

export function Schemaforslag({ api }: VyProps) {
  const pass = api.schemaPass();
  const m = api.foreEfter();
  const andringar = api.schemaForandringar();
  const andrade = new Set(andringar.map((x) => `${x.namn}|${x.datum}`));
  const [vald, setVald] = useState("alla");

  const { dagar, namn, celler } = useMemo(() => {
    const dagar = Array.from(new Set(pass.map((p) => p.datum))).sort();
    const namn = Array.from(new Set(pass.map((p) => p.namn))).sort();
    const celler = new Map<string, typeof pass>();
    for (const p of pass) {
      const k = `${p.namn}|${p.datum}`;
      const lista = celler.get(k) || [];
      lista.push(p);
      celler.set(k, lista);
    }
    return { dagar, namn, celler };
  }, [pass]);

  if (!pass.length || !m) {
    return (
      <TomtLage
        ikon={Upload}
        rubrik="Schemaförslaget behöver personalschemat"
        text="Ladda upp schemafilen under Underlag. Då visas hur personalen arbetar under perioden och var bemanningen bör justeras."
        atgarder={[{ text: "Gå till Underlag", onClick: () => api.setTab("underlag"), ikon: Upload }]}
      />
    );
  }

  const lage = m.efter ?? m.fore;
  const visa = vald === "alla" ? namn : [vald];

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <Eyebrow>Steg 3 · Schemaförslag</Eyebrow>
            <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">
              Så bör bemanningen justeras
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Nedan syns ert inlästa schema för perioden. Appen jämför det med kundernas behov och pekar ut när det finns
              för mycket och för lite personal. Appen lägger inte ett nytt schema automatiskt – förslagen är beslutsstöd.
            </p>
          </div>
          <select
            value={vald}
            onChange={(e) => setVald(e.target.value)}
            className="h-10 rounded-lg border border-input bg-card px-3 text-sm font-semibold text-deep outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40"
          >
            <option value="alla">Alla medarbetare</option>
            {namn.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kort etikett="Schemalagd tid" tal={fmtH(lage.schematidH)} forklaring="Arbetad tid i perioden, utan sovande jour." />
        <Kort etikett="Sovande jour" tal={fmtH(lage.jourH)} forklaring="Jourtid 23:00–06:30 räknas separat." />
        <Kort etikett="Överkapacitet" tal={fmtH(lage.overkapacitetH)} forklaring="Tid med mer personal än kundbehov." />
        <Kort etikett="Obemannat behov" tal={fmtH(lage.obemannatH)} forklaring="Tid där personalen inte räcker till behovet." />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="gap-0 rounded-2xl p-7 shadow-lift">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-warning-soft text-warning">
              <TrendingDown className="size-4" />
            </span>
            <h3 className="text-lg font-extrabold text-deep">Kan minskas</h3>
          </div>
          {m.minska.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {m.minska.map((t) => (
                <Badge key={t} className="rounded-full bg-warning-soft px-3 py-1 text-xs font-bold tabular-nums text-warning">
                  kl. {t}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">Ingen tid på dygnet har tydlig överbemanning.</p>
          )}
        </Card>
        <Card className="gap-0 rounded-2xl p-7 shadow-lift">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-danger-soft text-danger">
              <TrendingUp className="size-4" />
            </span>
            <h3 className="text-lg font-extrabold text-deep">Behöver förstärkas</h3>
          </div>
          {m.forstark.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {m.forstark.map((t) => (
                <Badge key={t} className="rounded-full bg-danger-soft px-3 py-1 text-xs font-bold tabular-nums text-danger">
                  kl. {t}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">Personalen räcker till under hela dygnet.</p>
          )}
        </Card>
      </div>

      <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
        <div className="px-7 pt-7">
            <Eyebrow>{m.efter ? "Optimerat personalschema" : "Inläst personalschema"}</Eyebrow>
            <h3 className="mt-1 text-lg font-extrabold text-deep">Pass per medarbetare och dag</h3>
            {m.efter ? <p className="mt-1 text-sm text-muted-foreground">{andringar.length} passändringar har föreslagits av optimeringen.</p> : null}
        </div>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-card px-5 py-3 text-left text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                  Medarbetare
                </th>
                {dagar.map((iso) => {
                  const dd = new Date(iso + "T12:00:00Z");
                  const wd = VECKODAG[(dd.getUTCDay() + 6) % 7];
                  const helg = wd === "lör" || wd === "sön";
                  return (
                    <th
                      key={iso}
                      className={cn(
                        "min-w-[78px] px-2 py-3 text-center text-[11px] font-bold tabular-nums text-muted-foreground",
                        helg && "bg-muted/50",
                      )}
                    >
                      <span className="block uppercase">{wd}</span>
                      {iso.slice(8)}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {visa.map((n) => (
                <tr key={n} className="border-t border-border">
                  <th className="sticky left-0 z-10 border-t border-border bg-card px-5 py-3 text-left align-top text-sm font-extrabold text-deep">
                    {n}
                  </th>
                  {dagar.map((iso) => {
                    const lista = celler.get(`${n}|${iso}`) || [];
                    return (
                      <td key={iso} className="border-t border-border px-1.5 py-2 align-top">
                        <div className="flex flex-col gap-1">
                          {lista.map((p) => (
                            <span
                              key={p.id}
                              className={cn(
                                "rounded-lg px-2 py-1.5 text-[11px] leading-tight font-semibold tabular-nums",
                                p.vikarie ? "bg-warning-soft text-warning" : p.jour ? "bg-[var(--pass-natt)] text-deep" : "bg-[var(--pass-dag)] text-deep",
                                andrade.has(`${p.namn}|${p.datum}`) && "ring-2 ring-primary/50",
                              )}
                            >
                              {p.jour ? <Moon className="mb-0.5 inline size-3" /> : null} {p.start}–{p.slut}
                            </span>
                          ))}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center gap-4 px-7 py-5 text-xs text-muted-foreground">
          <span className="flex items-center gap-2">
            <i className="inline-block size-3 rounded-[3px]" style={{ background: "var(--pass-dag)" }} /> Arbetstid
          </span>
          <span className="flex items-center gap-2">
            <i className="inline-block size-3 rounded-[3px]" style={{ background: "var(--pass-natt)" }} /> Sovande jour
          </span>
          <span className="flex items-center gap-2">
            <AlertTriangle className="size-3" /> Vakanta schemarader visas som egna rader.
          </span>
          <span className="flex items-center gap-2">
            <i className="inline-block size-3 rounded-[3px] bg-primary-soft ring-2 ring-primary/50" /> Ändrat pass
          </span>
        </div>
      </Card>
    </div>
  );
}
