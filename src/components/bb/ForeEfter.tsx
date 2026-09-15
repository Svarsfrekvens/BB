import { ArrowDown, ArrowUp, Minus, Sparkles, Upload } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { VyProps } from "@/lib/bb/vy";
import type { Lage } from "@/lib/bb/modell";
import { TomtLage } from "./Tomt";
import { filtreraJamforRader, jamforTon, lasMotorSummary, berakningsKallaText, visningEffekt } from "@/lib/bb/vcFlode";
import { lasJourDiagnos, harMjukKundbrist } from "@/lib/bb/jourDiagnos";
import { ResursbristPanel, resursbristProps } from "./ResursbristPanel";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

/** Dygnskurva: behov mot bemanning, som medelvärde per timme över perioden. */
function Kurva({ lage, rubrik, text }: { lage: Lage; rubrik: string; text: string }) {
  const max = Math.max(1, ...lage.perTimme.map((t) => Math.max(t.behov, t.bemanning)));
  return (
    <Card className="gap-0 rounded-2xl p-7 shadow-lift">
      <Eyebrow>{rubrik}</Eyebrow>
      <h3 className="mt-1 text-lg font-extrabold text-deep">Behov mot bemanning över dygnet</h3>
      <p className="mt-1 text-sm text-muted-foreground">{text}</p>
      <div className="mt-5 flex h-44 items-end gap-[3px]">
        {lage.perTimme.map((t) => (
          <div key={t.timme} className="flex flex-1 flex-col justify-end gap-[2px]" title={`kl. ${String(t.timme).padStart(2, "0")}`}>
            <div className="relative flex h-40 items-end gap-[2px]">
              <div className="flex-1 rounded-t bg-primary/80" style={{ height: `${(t.behov / max) * 100}%` }} />
              <div className="flex-1 rounded-t bg-deep/25" style={{ height: `${(t.bemanning / max) * 100}%` }} />
            </div>
            <span className="text-center text-[9px] tabular-nums text-muted-foreground">
              {t.timme % 3 === 0 ? String(t.timme).padStart(2, "0") : ""}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-2">
          <i className="inline-block size-3 rounded-[3px] bg-primary/80" /> Kundernas behov
        </span>
        <span className="flex items-center gap-2">
          <i className="inline-block size-3 rounded-[3px] bg-deep/25" /> Personal på plats
        </span>
      </div>
    </Card>
  );
}

export function ForeEfter({ api }: VyProps) {
  const m = api.foreEfter();

  if (!m) {
    return (
      <TomtLage
        ikon={Upload}
        rubrik="Jämförelsen behöver båda filerna"
        text="Ladda upp personalschemat och kundfilen under Underlag. Då visas dagens läge jämfört med ett förslag som följer kundernas behov."
        atgarder={[{ text: "Gå till Underlag", onClick: () => api.setTab("uppladdning"), ikon: Upload }]}
      />
    );
  }

  const { fore, efter, tabell, punkter, flyttade, vikarie, varningar, obemannade, ofullstandig } = m;
  const summary = lasMotorSummary(api.motorResultat());
  const jour = lasJourDiagnos((api.motorResultat() as { resourceDiagnostics?: unknown } | null)?.resourceDiagnostics);
  const tackningSank = !!(efter && efter.tackningPct + 0.05 < fore.tackningPct);
  const visade = efter ? filtreraJamforRader(tabell) : [];
  const extra = efter
    ? [
        vikarie
          ? {
              namn: "Vikariebehov",
              fore: "–",
              efter: `${vikarie.antalBehalls} pass`,
              forandring: `${vikarie.antalBehalls}`,
              riktning: "lika" as const,
            }
          : null,
        {
          namn: "Hårda regelbrott",
          fore: "–",
          efter: String(summary?.hardViolations.length ?? api.regelbrott()),
          forandring: String(summary?.hardViolations.length ?? api.regelbrott()),
          riktning: (summary?.hardViolations.length || api.regelbrott() ? "ner" : "lika") as "ner" | "lika",
        },
        {
          namn: "Arbetsmiljövarningar",
          fore: "–",
          efter: String(summary?.warnings.length ?? varningar.length),
          forandring: String(summary?.warnings.length ?? varningar.length),
          riktning: ((summary?.warnings.length || varningar.length) ? "ner" : "lika") as "ner" | "lika",
        },
      ].filter(Boolean)
    : [];

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <Eyebrow>Före → Balans</Eyebrow>
            <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">
              Inläst nuläge jämfört med planerad balans
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Före är det inlästa underlaget. Balans är hur vi planerar schemaperioden. Pilarna följer om värdet ökar
              eller minskar.
            </p>
            {efter || ofullstandig ? (
              <p className="mt-2 text-xs font-semibold text-muted-foreground">{berakningsKallaText(api.berakningsKalla())}</p>
            ) : null}
          </div>
          {efter || ofullstandig ? (
            <Button variant="outline" onClick={() => api.aterstallBalans()}>
              Tillbaka till originaldata
            </Button>
          ) : (
            <Button onClick={() => api.skapaBalans()}>
              <Sparkles /> Skapa balans
            </Button>
          )}
        </div>
      </Card>

      <ResursbristPanel
        diagnos={jour}
        visaKundbrist={harMjukKundbrist({
          tacktBehovPct: efter?.tackningPct,
          obemannadeAntal: obemannade.length,
          ofullstandigUtanSchema: Boolean(ofullstandig),
        })}
        {...resursbristProps(api)}
      />

      {efter ? (
        <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-0 text-sm">
              <thead>
                <tr className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                  <th className="px-6 py-3 text-left">Mått</th>
                  <th className="px-6 py-3 text-right">Före</th>
                  <th className="px-6 py-3 text-right">Balans</th>
                  <th className="px-6 py-3 text-right">Förändring</th>
                </tr>
              </thead>
              <tbody>
                {visade.concat(extra as typeof visade).map((r) => {
                  const ton = jamforTon({ namn: r.namn, riktning: r.riktning, tackningSank });
                  const effekt = visningEffekt(r.forandring);
                  const pil = "pil" in r && r.pil ? r.pil : effekt.pil;
                  return (
                  <tr key={r.namn} className="border-t border-border">
                    <th className={cn("border-t border-border px-6 py-3 text-left text-sm font-bold text-deep", "underMatchning" in r && r.underMatchning && "pl-10 font-semibold text-muted-foreground")}>
                      {"underMatchning" in r && r.underMatchning ? `↳ ${r.namn}` : r.namn}
                    </th>
                    <td className="border-t border-border px-6 py-3 text-right tabular-nums text-muted-foreground">{r.fore}</td>
                    <td className="border-t border-border px-6 py-3 text-right font-bold tabular-nums text-deep">{r.efter}</td>
                    <td className="border-t border-border px-6 py-3 text-right">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold tabular-nums",
                          ton === "bra"
                            ? "bg-success-soft text-success"
                            : ton === "varn"
                              ? "bg-warning-soft text-warning"
                              : "bg-muted text-muted-foreground",
                        )}
                      >
                        {pil === "upp" ? <ArrowUp className="size-3" /> : pil === "ner" ? <ArrowDown className="size-3" /> : <Minus className="size-3" />}
                        {effekt.text}
                      </span>
                    </td>
                  </tr>
                );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {obemannade.length ? (
        <Card className="gap-0 rounded-2xl border-destructive/40 bg-destructive/5 p-6 shadow-lift">
          <Eyebrow>Otäckt kundbehov</Eyebrow>
          <h3 className="mt-1 text-lg font-extrabold text-destructive">
            Vissa kundinsatser är ännu inte bemannade
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {obemannade.reduce((s, u) => s + (u.antal || 1), 0)} insatser saknar bemanning i förslaget. Detta är inte
            samma sak som att obligatorisk jour saknar resurs. Hårda regler har inte lättats.
          </p>
          <ul className="mt-4 space-y-2">
            {obemannade.map((u, i) => (
              <li key={`${u.datum}-${u.insats}-${i}`} className="flex gap-3 text-sm leading-relaxed text-deep">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-destructive" />
                <span>
                  <span className="font-semibold">{u.insats}</span>
                  {" · "}
                  {u.datum}
                  {" · "}
                  {u.minuter} minuter
                  {u.antal > 1 ? ` · ${u.antal} tillfällen` : ""}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {vikarie ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Card className="gap-1 rounded-2xl p-6 shadow-lift">
            <span className="text-[13px] font-semibold text-muted-foreground">Vikariepass som behöver tillsättas</span>
            <strong className="text-3xl font-extrabold tabular-nums text-deep">{vikarie.antalBehalls}</strong>
            <span className="text-[13px] text-muted-foreground">De fyller ett verkligt gap i kundernas behov.</span>
          </Card>
          <Card className="gap-1 rounded-2xl p-6 shadow-lift">
            <span className="text-[13px] font-semibold text-muted-foreground">Vikariepass som kunde tas bort</span>
            <strong className="text-3xl font-extrabold tabular-nums text-deep">{vikarie.antalBorttagna}</strong>
            <span className="text-[13px] text-muted-foreground">Behovet täcks av ordinarie personal på de tiderna.</span>
          </Card>
        </div>
      ) : null}

      {varningar.length ? (
        <Card className="gap-0 rounded-2xl border-warning/40 bg-warning-soft/60 p-6 shadow-lift">
          <Eyebrow>Att se över</Eyebrow>
          <ul className="mt-3 space-y-2">
            {varningar.slice(0, 12).map((w) => (
              <li key={w} className="flex gap-3 text-sm leading-relaxed text-deep-soft">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-warning" />
                {w}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card className="gap-0 rounded-2xl p-7 shadow-lift">
        <Eyebrow>Vad som ändrats och varför</Eyebrow>
        <h3 className="mt-1 text-lg font-extrabold text-deep">Förklaring i klartext</h3>
        <ul className="mt-4 space-y-2">
          {(punkter.length ? punkter : ["Skapa bemanningsbalans för att se vad som kan förbättras."]).map((p) => (
            <li key={p} className="flex gap-3 text-sm leading-relaxed text-deep-soft">
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />
              {p}
            </li>
          ))}
        </ul>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Kurva lage={fore} rubrik="Före" text="Inläst schema mot ursprungligt kundbehov." />
        {efter ? <Kurva lage={efter} rubrik="Balans" text="Så planerar vi schemaperioden." /> : null}
      </div>

      {flyttade.length ? (
        <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
          <div className="px-7 pt-7">
            <Eyebrow>Flyttade insatser</Eyebrow>
            <h3 className="mt-1 text-lg font-extrabold text-deep">{flyttade.length} insatser fick ny tid</h3>
            <p className="mt-1 text-sm text-muted-foreground">Varje insats ligger kvar inom sitt tillåtna fönster.</p>
          </div>
          <div className="mt-5 max-h-96 overflow-auto">
            <table className="w-full border-separate border-spacing-0 text-sm">
              <thead className="sticky top-0 bg-card">
                <tr className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                  <th className="px-6 py-3 text-left">Kund</th>
                  <th className="px-6 py-3 text-left">Insats</th>
                  <th className="px-6 py-3 text-left">Datum</th>
                  <th className="px-6 py-3 text-right">Från</th>
                  <th className="px-6 py-3 text-right">Till</th>
                </tr>
              </thead>
              <tbody>
                {flyttade.slice(0, 200).map((f) => (
                  <tr key={f.id + f.datum} className="border-t border-border">
                    <td className="border-t border-border px-6 py-2.5 font-semibold text-deep">{f.kund}</td>
                    <td className="border-t border-border px-6 py-2.5 text-muted-foreground">{f.insats}</td>
                    <td className="border-t border-border px-6 py-2.5 tabular-nums text-muted-foreground">{f.datum}</td>
                    <td className="border-t border-border px-6 py-2.5 text-right tabular-nums text-muted-foreground">{f.fran}</td>
                    <td className="border-t border-border px-6 py-2.5 text-right font-bold tabular-nums text-deep">{f.till}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {flyttade.length > 200 ? (
            <div className="px-7 py-4 text-xs text-muted-foreground">Visar de 200 första av {flyttade.length}.</div>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
