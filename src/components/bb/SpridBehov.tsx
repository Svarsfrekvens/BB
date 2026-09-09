import { useRef } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, RotateCcw, ArrowLeftRight, ChevronLeft, ChevronRight, CalendarPlus } from "lucide-react";
import type { VyProps } from "@/lib/bb/vy";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

const VD = ["mån", "tis", "ons", "tor", "fre", "lör", "sön"];
const VD_LANG = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"];

export function SpridBehov({ d, state, api }: VyProps) {
  const dragData = useRef<{ typ: "ins" | "mote"; id: string } | null>(null);

  if (!d) {
    return (
      <Card className="rounded-2xl p-8 text-center shadow-lift">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary text-xs font-extrabold text-deep">
          XLS
        </div>
        <h2 className="mt-4 text-xl font-extrabold text-deep">Behovet kan inte visas ännu</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
          Läs in en fil med kundernas insatser så kan du sprida behovet här.
        </p>
        <Button className="mt-5" onClick={() => api.valjFil()}>
          <FileText /> Välj Excel-fil
        </Button>
      </Card>
    );
  }

  const h1 = api.h1;
  const minClock = api.minClock;
  const zoom: string = api.spridZoom();
  const safeDag: number = api.spridDagIdx();
  const dagar: string[] = [];
  for (let i = 0; i < state.analysisDays; i++) dagar.push(api.addDays(state.period?.from ?? "", i));
  const lek = api.kundLek();
  const antalFlyttar = Object.keys(lek.moves || {}).length;
  const antalMoten = (lek.moten || []).length;

  const dagTopp = dagar.map((iso) => {
    const ins = api.kundDagModell(iso);
    const moten = (lek.moten || []).filter((m) => m.datum === iso);
    const kurva = api.kundDagKurva(ins, moten);
    return {
      iso,
      peak: kurva.peak,
      peakSlot: kurva.peakSlot,
      behovH: ins.reduce((s: number, p) => s + p.dur * p.staff, 0) / 60,
      antal: ins.length,
      flyttbara: ins.filter((p) => p.flyttbar).length,
    };
  });
  const maxPeak = Math.max(1, ...dagTopp.map((x) => x.peak));

  const Huvud = (
    <Card className="gap-0 rounded-2xl p-6 shadow-lift md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Eyebrow>Sprid kundbehov</Eyebrow>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-extrabold tracking-tight text-deep md:text-3xl">
            <ArrowLeftRight className="size-6 text-primary" /> Jämna ut topparna inom insatsernas fönster
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Välj <strong>Månad</strong> eller <strong>Vecka</strong> för att se vilka dagar som har högst samtidighet, och
            klicka på en dag för att öppna <strong>Dag</strong>-läget där du drar de gula insatserna inom deras fönster.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-xl border border-border bg-muted/40 p-1">
            {[
              ["manad", "Månad"],
              ["vecka", "Vecka"],
              ["dag", "Dag"],
            ].map(([id = "", lab]) => (
              <button
                key={id}
                type="button"
                onClick={() => api.setSpridZoom(id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-colors ${
                  zoom === id ? "bg-card text-primary shadow-sm" : "text-muted-foreground hover:text-deep"
                }`}
              >
                {lab}
              </button>
            ))}
          </div>
          <Button variant="outline" disabled={!antalFlyttar && !antalMoten} onClick={() => api.aterstallSprid()}>
            <RotateCcw /> Återställ
          </Button>
        </div>
      </div>
    </Card>
  );

  if (zoom !== "dag") {
    const set = zoom === "manad" ? dagTopp : dagTopp.slice(Math.max(0, safeDag - 3), Math.max(0, safeDag - 3) + 7);
    const summa = set.reduce((s, x) => s + x.behovH, 0);
    return (
      <div className="space-y-4">
        {Huvud}
        <Card className="gap-0 rounded-2xl p-6 shadow-lift md:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Eyebrow>{zoom === "manad" ? "Månadsöversikt – hela perioden" : "Veckoöversikt"}</Eyebrow>
            <Badge variant="secondary" className="rounded-full font-bold tabular-nums">
              Summa kundbehov: {h1(summa)} h
            </Badge>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-7">
            {set.map((x) => {
              const di = dagar.indexOf(x.iso);
              const dd = new Date(x.iso + "T12:00:00Z");
              const wd = VD[(dd.getUTCDay() + 6) % 7];
              const helg = wd === "lör" || wd === "sön";
              const farg = x.peak > 8 ? "var(--korall)" : x.peak > 6 ? "var(--varn)" : "var(--ok)";
              return (
                <button
                  key={x.iso}
                  type="button"
                  onClick={() => {
                    api.setSpridDag(di);
                    api.setSpridZoom("dag");
                  }}
                  className={`rounded-2xl border p-4 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift ${
                    helg ? "border-border/70 bg-muted/40" : "border-border/70 bg-card"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs font-bold text-deep">
                    <span>
                      {wd} {x.iso.slice(8)}
                    </span>
                    {x.flyttbara ? (
                      <span className="text-[11px] font-bold" style={{ color: "var(--varn)" }}>
                        ⇄ {x.flyttbara}
                      </span>
                    ) : null}
                  </div>
                  <div
                    className="mt-2 inline-block rounded-full px-2 py-0.5 text-[11px] font-bold tabular-nums"
                    style={{ background: farg + "1A", color: farg }}
                  >
                    Topp {x.peak} kl. {minClock(x.peakSlot * 15)}
                  </div>
                  <div className="mt-3 flex h-16 items-end">
                    <i
                      className="block w-full rounded-t"
                      style={{ height: `${(x.peak / maxPeak) * 100}%`, background: farg, opacity: 0.85 }}
                    />
                  </div>
                  <div className="mt-2 text-[11px] text-muted-foreground tabular-nums">
                    {h1(x.behovH)} h · {x.antal} insatser
                  </div>
                </button>
              );
            })}
          </div>
          <p className="mt-4 text-[11px] text-muted-foreground/80">
            Klicka på en dag för att öppna dagvyn och dra insatser. Rött = hög samtidighet (fler än 8), gult = 7–8, grönt =
            lugnare.
          </p>
        </Card>
      </div>
    );
  }

  const iso = dagar[safeDag]!;
  const insatser = api.kundDagModell(iso);
  const moten = (lek.moten || []).filter((m) => m.datum === iso);
  const kurva = api.kundDagKurva(insatser, moten);
  const rorliga = insatser.filter((p) => p.flyttbar).length;
  const bemSlots: number[] | null = api.schemaPerSlot ? api.schemaPerSlot(iso) : null;
  const bemMax = bemSlots ? Math.max(...bemSlots) : 0;
  const yMax = Math.max(1, kurva.peak, bemMax);
  const ySteg = yMax <= 5 ? 1 : yMax <= 10 ? 2 : yMax <= 20 ? 5 : 10;
  const yLbls: number[] = [];
  for (let v = 0; v <= yMax; v += ySteg) yLbls.push(v);
  const dd = new Date(iso + "T12:00:00Z");
  const wdName = VD_LANG[(dd.getUTCDay() + 6) % 7];

  const kunder = [...new Set(insatser.map((p) => p.kund))].sort((a, b) =>
    a === "Gemensamt" ? 1 : b === "Gemensamt" ? -1 : String(a).localeCompare(String(b), "sv"),
  ) as string[];

  const slapp = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const mins = Math.round(((frac * 1440) / 15)) * 15;
    const dd2 = dragData.current;
    if (!dd2) return;
    if (dd2.typ === "ins") api.flyttaInsats(dd2.id, iso, mins);
    else api.flyttaMote(Number(dd2.id), mins);
    dragData.current = null;
  };

  return (
    <div className="space-y-4">
      {Huvud}
      <Card className="gap-0 rounded-2xl p-6 shadow-lift md:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" aria-label="Föregående dag" onClick={() => api.setSpridDag(safeDag - 1)}>
              <ChevronLeft />
            </Button>
            <strong className="text-sm font-extrabold text-deep">
              {wdName} {iso}
            </strong>
            <Button variant="outline" size="icon" aria-label="Nästa dag" onClick={() => api.setSpridDag(safeDag + 1)}>
              <ChevronRight />
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <span
              className="rounded-full px-3 py-1 text-xs font-bold tabular-nums"
              style={
                kurva.peak > 6 ? { background: "var(--varn-mjuk)", color: "var(--varn)" } : { background: "var(--ok-mjuk)", color: "var(--ok)" }
              }
            >
              Högsta samtidighet: {kurva.peak} kl. {minClock(kurva.peakSlot * 15)}
            </span>
            <Badge variant="secondary" className="rounded-full font-bold tabular-nums">
              {rorliga} flyttbara insatser
            </Badge>
            {antalFlyttar ? (
              <Badge variant="secondary" className="rounded-full font-bold tabular-nums">
                {antalFlyttar} flyttade
              </Badge>
            ) : null}
          </div>
        </div>

        {/* Behovskurva per 15 min */}
        <div className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-bold text-muted-foreground">
            <span>Behov (samtidiga insatser){bemSlots ? " mot schemalagda medarbetare" : ""}</span>
            <span className="flex items-center gap-3">
              <span className="flex items-center gap-1.5">
                <i className="inline-block h-2.5 w-3 rounded-sm" style={{ background: "var(--djup)" }} /> Behov
              </span>
              {bemSlots ? (
                <span className="flex items-center gap-1.5">
                  <i className="inline-block h-0.5 w-4" style={{ background: "var(--korall)" }} /> Schemalagda medarbetare
                </span>
              ) : null}
            </span>
          </div>
          <div className="relative mt-2 h-32 rounded-xl border border-border/70 bg-muted/25 pl-7">
            <div className="pointer-events-none absolute inset-y-0 left-0 w-7">
              {yLbls.map((v) => (
                <span
                  key={v}
                  className="absolute right-1 -translate-y-1/2 text-[10px] text-muted-foreground tabular-nums"
                  style={{ bottom: `${(v / yMax) * 100}%` }}
                >
                  {v}
                </span>
              ))}
            </div>
            <div className="flex h-full items-end gap-px pr-1">
              {kurva.slots.map((v: number, i: number) => {
                const hh = Math.floor((i * 15) / 60);
                const natt = hh >= 22 || hh < 6;
                return (
                  <i
                    key={i}
                    title={`${minClock(i * 15)}: behov ${v} samtidiga insatser${bemSlots ? `, schemalagt ${bemSlots[i]}` : ""}`}
                    className="block flex-1 rounded-t"
                    style={{
                      height: `${(v / yMax) * 100}%`,
                      background: natt ? "var(--djup-ljus)" : "var(--djup)",
                      minHeight: v ? 2 : 0,
                    }}
                  />
                );
              })}
            </div>
            {bemSlots && bemMax > 0 ? (
              <svg className="pointer-events-none absolute inset-y-0 right-1 left-7" viewBox="0 0 100 100" preserveAspectRatio="none">
                <polyline
                  fill="none"
                  stroke="var(--korall)"
                  strokeWidth="1.5"
                  vectorEffect="non-scaling-stroke"
                  points={bemSlots
                    .map((v, i) => `${((i / 95) * 100).toFixed(2)},${(100 - (v / yMax) * 100).toFixed(2)}`)
                    .join(" ")}
                />
              </svg>
            ) : null}
          </div>
        </div>

        {/* Timstreck */}
        <div className="relative mt-4 ml-[132px] h-4">
          {Array.from({ length: 13 }, (_, i) => (
            <span
              key={i}
              className="absolute -translate-x-1/2 text-[10px] text-muted-foreground tabular-nums"
              style={{ left: `${((i * 2) / 24) * 100}%` }}
            >
              {String(i * 2).padStart(2, "0")}
            </span>
          ))}
        </div>

        {/* Tidslinje per kund */}
        <div className="space-y-1.5">
          {kunder.map((kund) => (
            <div key={kund} className="flex items-center gap-3">
              <div className="w-[120px] shrink-0 truncate text-xs font-bold text-deep">{kund}</div>
              <div
                className="relative h-9 flex-1 rounded-lg border border-border/60 bg-muted/25"
                onDragOver={(e) => e.preventDefault()}
                onDrop={slapp}
              >
                {insatser
                  .filter((p) => p.kund === kund)
                  .map((p) => {
                    const left = (p.start / 1440) * 100;
                    const width = Math.max(1.2, (p.dur / 1440) * 100);
                    const fStart = p.fonsterStart ?? p.start;
                    const fLeft = (fStart / 1440) * 100;
                    const fWidth = (((p.fonsterEnd ?? p.end) - fStart) / 1440) * 100;
                    return (
                      <div key={p.id}>
                        {p.flyttbar ? (
                          <div
                            className="pointer-events-none absolute inset-y-1 rounded-md border border-dashed border-muted-foreground/50 bg-muted/40"
                            style={{ left: `${fLeft}%`, width: `${fWidth}%` }}
                            title={`Tillåtet fönster ${minClock(fStart)}–${minClock(p.fonsterEnd ?? p.end)}`}
                          />
                        ) : null}
                        <div
                          draggable={p.flyttbar}
                          onDragStart={() => {
                            dragData.current = { typ: "ins", id: p.id };
                          }}
                          title={`${p.insats} ${minClock(p.start)}–${minClock(p.end)}${
                            p.flyttbar
                              ? ` · dra inom ${minClock(fStart)}–${minClock(p.fonsterEnd ?? p.end)}`
                              : " · fast tid"
                          }`}
                          className={`absolute inset-y-1 flex items-center overflow-hidden rounded-md px-1.5 text-[10px] font-bold whitespace-nowrap ${
                            p.flyttbar ? "cursor-grab active:cursor-grabbing" : ""
                          } ${p.moved ? "ring-2 ring-offset-1" : ""}`}
                          style={{
                            left: `${left}%`,
                            width: `${width}%`,
                            background: p.flyttbar ? "var(--ins-flyttbar)" : "var(--ins-fast)",
                            color: "var(--djup-natt)",
                            outline: p.flyttbar ? "1px solid var(--varn)" : "none",
                            boxShadow: p.staff > 1 ? "inset 0 -3px 0 0 var(--korall)" : undefined,
                          }}
                        >
                          {p.flyttbar ? <span className="mr-1">⇄</span> : null}
                          <span className="truncate">{p.insats}</span>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          ))}
          <div className="flex items-center gap-3">
            <div className="w-[120px] shrink-0 truncate text-xs font-bold text-deep">Möte / utbildning</div>
            <div
              className="relative h-9 flex-1 rounded-lg border border-dashed border-border bg-muted/15"
              onDragOver={(e) => e.preventDefault()}
              onDrop={slapp}
            >
              {moten.map((m, i: number) => (
                <div
                  key={i}
                  draggable
                  onDragStart={() => {
                    dragData.current = { typ: "mote", id: String((lek.moten || []).indexOf(m)) };
                  }}
                  title={`${m.titel} ${minClock(m.start)}–${minClock(m.start + m.dur)}`}
                  className="absolute inset-y-1 flex cursor-grab items-center overflow-hidden rounded-md px-1.5 text-[10px] font-bold text-white active:cursor-grabbing"
                  style={{
                    left: `${(m.start / 1440) * 100}%`,
                    width: `${Math.max(1.5, (m.dur / 1440) * 100)}%`,
                    background: "var(--graf-linje)",
                  }}
                >
                  <span className="truncate">{m.titel}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button onClick={() => api.laggMote(iso)}>
            <CalendarPlus /> Lägg möte där behovet är lägst
          </Button>
          <span className="text-[11px] text-muted-foreground">
            Appen placerar mötet i största lediga luckan 08–17. Dra det sedan dit du vill.
          </span>
        </div>

        <div className="mt-4 flex flex-wrap gap-4 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <i className="inline-block size-3 rounded" style={{ background: "var(--ins-fast)" }} /> Fast insats (kan inte flyttas)
          </span>
          <span className="flex items-center gap-1.5">
            <i className="inline-block size-3 rounded" style={{ background: "var(--ins-flyttbar)", outline: "1px solid var(--varn)" }} /> ⇄
            Flyttbar insats – dra och släpp
          </span>
          <span className="flex items-center gap-1.5">
            <i
              className="inline-block size-3 rounded"
              style={{ background: "var(--graf-neutral)", outline: "1px dashed var(--graf-axel)" }}
            />{" "}
            Tillåtet fönster
          </span>
          <span className="flex items-center gap-1.5">
            <i className="inline-block size-3 rounded" style={{ background: "var(--graf-linje)" }} /> Möte/utbildning
          </span>
        </div>
      </Card>
    </div>
  );
}
