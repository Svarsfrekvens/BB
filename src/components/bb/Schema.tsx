import { useState } from "react";
import { AlertTriangle, CalendarDays, Check, Info, Moon, RotateCcw, Upload } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { Pass } from "@/lib/bb/typer";
import type { VyProps } from "@/lib/bb/vy";
import { TomtLage } from "./Tomt";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

function Val({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-10 rounded-lg border border-input bg-card px-3 text-sm font-semibold text-deep transition-colors outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40"
    >
      {children}
    </select>
  );
}

const VECKODAG = ["mån", "tis", "ons", "tor", "fre", "lör", "sön"];

/** Färgton per passtyp – samma indelning som tidigare. */
function passTon(typ: string) {
  if (/natt/i.test(typ)) return "bg-[var(--pass-natt)] text-deep";
  if (/kväll/i.test(typ)) return "bg-[var(--pass-kvall)] text-deep";
  if (/resurs|ssg/i.test(typ)) return "bg-[var(--pass-resurs)] text-deep";
  return "bg-[var(--pass-dag)] text-deep";
}

function Forklaring({ farg, text }: { farg: string; text: string }) {
  return (
    <span className="flex items-center gap-2 text-xs text-muted-foreground">
      <i className="inline-block size-3 rounded-[3px]" style={{ background: farg }} />
      {text}
    </span>
  );
}

export function Schema({ d, state, api }: VyProps) {
  const h1 = api.h1;
  const [filter, setFilter] = useState("alla");
  const [drag, setDrag] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);

  const modell = d ? api.schemaModell() : null;

  if (!d || !modell) {
    return (
      <TomtLage
        ikon={CalendarDays}
        rubrik="Schemat kan inte visas ännu"
        text="Medarbetarnas pass saknas i den inlästa filen. Läs in en fil med schemat, så visas passen per medarbetare och dag här."
        atgarder={[{ text: "Välj Excel-fil", onClick: () => api.valjFil(), ikon: Upload }]}
      />
    );
  }

  const { model, effektiva, varningar, medInfo, moves, notis } = modell;
  const antalFlyttar = Object.keys(moves).length;
  const alla = Object.values(varningar);
  const totalVarn = alla.reduce((s, w) => s + w.filter((x) => !x.indikation).length, 0);
  const totalInd = alla.reduce((s, w) => s + w.filter((x) => x.indikation).length, 0);

  const visaMed: string[] = filter === "alla" ? model.medarbetare : [filter];
  const perCell: Record<string, Pass[]> = {};
  for (const p of effektiva) (perCell[`${p.namn}|${p.datum}`] ||= []).push(p);

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Eyebrow>Schemabräde</Eyebrow>
            <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">
              Dra ett pass till en annan medarbetare
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Flytta pass genom att dra och släppa. Systemet varnar direkt vid dygnsvila under 11 h, för många pass i
              följd, natt utan behörighet och stora SSG-avvikelser. Övertid och veckovila visas som indikationer som
              bör kontrolleras mot avtalet. Ändringarna rör aldrig den importerade filen.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Val value={filter} onChange={setFilter}>
              <option value="alla">Alla medarbetare</option>
              {model.medarbetare.map((m: string) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Val>
            <Button variant="outline" disabled={!antalFlyttar} onClick={() => api.aterstallSchema()}>
              <RotateCcw /> Återställ ({antalFlyttar})
            </Button>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <Badge
            className={cn(
              "rounded-full px-3 py-1 text-xs font-bold",
              totalVarn ? "bg-[var(--fara-mjuk)] text-[var(--fara)]" : "bg-[var(--ok-mjuk)] text-[var(--ok)]",
            )}
          >
            {totalVarn ? (
              <>
                <AlertTriangle className="size-3" /> {totalVarn} regelvarningar
              </>
            ) : (
              <>
                <Check className="size-3" /> Inga regelbrott
              </>
            )}
          </Badge>
          {totalInd ? (
            <Badge className="rounded-full bg-[var(--varn-mjuk)] px-3 py-1 text-xs font-bold text-[var(--varn)]">
              <Info className="size-3" /> {totalInd} indikationer (övertid/veckovila)
            </Badge>
          ) : null}
          {antalFlyttar ? (
            <Badge variant="secondary" className="rounded-full px-3 py-1 text-xs font-bold">
              {antalFlyttar} flyttade pass
            </Badge>
          ) : null}
        </div>

        {notis ? (
          <div
            className={cn(
              "mt-5 rounded-xl px-5 py-4 text-sm",
              notis.ton === "warn" ? "bg-[var(--fara-mjuk)] text-[var(--fara)]" : "bg-[var(--ok-mjuk)] text-[var(--ok)]",
            )}
          >
            <strong className="flex items-center gap-2 font-extrabold">
              {notis.ton === "warn" ? <AlertTriangle className="size-4" /> : <Check className="size-4" />}
              {notis.ton === "warn" ? "Villkor bryts" : "Passet är flyttat"}
            </strong>
            <div className="mt-1">
              {notis.namn}: {notis.text}
            </div>
          </div>
        ) : null}
      </Card>

      <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-card px-5 py-3 text-left text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                  Medarbetare
                </th>
                {model.dagar.map((iso: string) => {
                  const dd = new Date(iso + "T12:00:00Z");
                  const wd = VECKODAG[(dd.getUTCDay() + 6) % 7];
                  const helg = wd === "lör" || wd === "sön";
                  return (
                    <th
                      key={iso}
                      className={cn(
                        "min-w-[74px] px-2 py-3 text-center text-[11px] font-bold text-muted-foreground tabular-nums",
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
              {visaMed.map((namn: string) => {
                const info = medInfo[namn] || { diff: 0, nattbehorig: false };
                const prof = model.prof[namn] || {};
                const ton =
                  Math.abs(info.diff) <= 8
                    ? "bg-[var(--ok-mjuk)] text-[var(--ok)]"
                    : Math.abs(info.diff) <= 20
                      ? "bg-[var(--varn-mjuk)] text-[var(--varn)]"
                      : "bg-[var(--fara-mjuk)] text-[var(--fara)]";
                return (
                  <tr key={namn} className="border-t border-border">
                    <th className="sticky left-0 z-10 border-t border-border bg-card px-5 py-3 text-left align-top">
                      <strong className="block text-sm font-extrabold text-deep normal-case">{namn}</strong>
                      <span className="mt-1 flex flex-wrap items-center gap-1">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-bold tabular-nums normal-case", ton)}>
                              {info.diff >= 0 ? "+" : ""}
                              {h1(info.diff)} h mot mål
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>Planerad tid mot budget och mål</TooltipContent>
                        </Tooltip>
                        {prof.nattbehorig ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="text-muted-foreground">
                                <Moon className="size-3" />
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>Nattbehörig</TooltipContent>
                          </Tooltip>
                        ) : null}
                      </span>
                    </th>
                    {model.dagar.map((iso: string) => {
                      const nyckel = `${namn}|${iso}`;
                      const list = perCell[nyckel] || [];
                      return (
                        <td
                          key={iso}
                          onDragOver={(e) => {
                            e.preventDefault();
                            setOver(nyckel);
                          }}
                          onDragLeave={() => setOver((o) => (o === nyckel ? null : o))}
                          onDrop={(e) => {
                            e.preventDefault();
                            setOver(null);
                            if (drag) api.flyttaPass(drag, namn);
                            setDrag(null);
                          }}
                          className={cn(
                            "border-t border-border px-1.5 py-2 align-top transition-colors",
                            over === nyckel && "bg-secondary",
                          )}
                        >
                          <div className="flex flex-col gap-1">
                            {list.map((p) => {
                              const w = varningar[p.id] || [];
                              const hard = w.some((x) => !x.indikation);
                              const ind = w.some((x) => x.indikation);
                              return (
                                <Tooltip key={p.id}>
                                  <TooltipTrigger asChild>
                                    <div
                                      draggable
                                      onDragStart={() => setDrag(p.id)}
                                      onDragEnd={() => setDrag(null)}
                                      className={cn(
                                        "cursor-grab rounded-lg px-2 py-1.5 text-[11px] leading-tight font-semibold transition-all duration-150 hover:-translate-y-0.5 hover:shadow-lift active:cursor-grabbing",
                                        passTon(p.typ),
                                        hard && "ring-2 ring-[var(--fara)]/50",
                                        ind && !hard && "ring-2 ring-[var(--varn)]/40",
                                        drag === p.id && "opacity-50",
                                      )}
                                    >
                                      <span className="block truncate">{p.typ}</span>
                                      <em className="block font-bold not-italic tabular-nums">
                                        {p.start}–{p.slut}
                                      </em>
                                      {hard ? (
                                        <AlertTriangle className="mt-0.5 inline size-3 text-[var(--fara)]" />
                                      ) : ind ? (
                                        <Info className="mt-0.5 inline size-3 text-[var(--varn)]" />
                                      ) : null}
                                    </div>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    {w.length
                                      ? w.map((x) => (x.indikation ? "ⓘ " : "⚠ ") + x.text).join(" • ")
                                      : `${p.typ} ${p.start}–${p.slut}`}
                                  </TooltipContent>
                                </Tooltip>
                              );
                            })}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="flex flex-wrap gap-x-5 gap-y-2 px-1">
        <Forklaring farg="var(--pass-dag)" text="Dag" />
        <Forklaring farg="var(--pass-kvall)" text="Kväll" />
        <Forklaring farg="var(--pass-natt)" text="Natt" />
        <Forklaring farg="var(--pass-resurs)" text="Resurs/SSG" />
        <Forklaring farg="var(--fara-mjuk)" text="Regelbrott" />
        <Forklaring farg="var(--varn-mjuk)" text="Indikation" />
      </div>
    </div>
  );
}
