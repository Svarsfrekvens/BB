import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { FileText, RotateCcw, SlidersHorizontal } from "lucide-react";
import type { VyProps } from "@/lib/bb/vy";

function Eyebrow({ children, ljus }: { children: React.ReactNode; ljus?: boolean }) {
  return (
    <div className={`text-[11px] font-bold tracking-widest uppercase ${ljus ? "text-white/70" : "text-primary"}`}>
      {children}
    </div>
  );
}

export function Simulering({ d, api }: VyProps) {
  if (!d) {
    return (
      <Card className="rounded-2xl p-8 text-center shadow-lift">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary text-xs font-extrabold text-deep">
          XLS
        </div>
        <h2 className="mt-4 text-xl font-extrabold text-deep">Inget att räkna på ännu</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
          Läs in en fil så kan du prova antaganden här.
        </p>
        <Button className="mt-5" onClick={() => api.valjFil()}>
          <FileText /> Välj Excel-fil
        </Button>
      </Card>
    );
  }

  const base = api.simBase();
  const r = api.simResultat();
  const varden: Record<string, number> = api.simVarden();
  const dirty = Object.keys(varden).length > 0;
  const h1 = api.h1;
  const kr0 = (x: number) => Math.round(x).toLocaleString("sv-SE") + " kr";
  const pct = (x: number) => x.toLocaleString("sv-SE", { maximumFractionDigits: 1 }) + " %";
  const hh = (x: number) => h1(x) + " h";
  const g = (k: string, dflt: number) => (varden[k] != null ? varden[k] : dflt);

  const Reglage = ({
    id,
    label,
    min,
    max,
    step,
    baseVal,
    fmt,
    help,
  }: {
    id: string;
    label: string;
    min: number;
    max: number;
    step: number;
    baseVal: number;
    fmt: (x: number) => string;
    help?: string;
  }) => {
    const cur = g(id, baseVal);
    const changed = varden[id] != null && Math.abs(varden[id] - baseVal) > 1e-9;
    return (
      <div className={`rounded-xl border p-4 transition-colors ${changed ? "border-primary/60 bg-primary/5" : "border-border/70 bg-card"}`}>
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-sm font-semibold text-deep">{label}</span>
          <strong className="text-base font-extrabold text-deep tabular-nums">{fmt(cur)}</strong>
        </div>
        <Slider
          className="mt-3"
          min={min}
          max={max}
          step={step}
          value={[cur]}
          onValueChange={(v) => api.simSet(id, v[0] ?? cur)}
          aria-label={label}
        />
        <div className="mt-2 flex flex-wrap justify-between gap-2 text-[11px] text-muted-foreground/80">
          <span>Filens värde: {fmt(baseVal)}</span>
          {help ? <span>{help}</span> : null}
        </div>
      </div>
    );
  };

  const SrKort = ({ lab, val, note, tone }: { lab: string; val: string; note: string; tone?: "pos" | "neg" }) => (
    <div className="rounded-2xl bg-white/10 p-4 ring-1 ring-white/15">
      <div className="text-[11px] font-bold tracking-widest text-white/70 uppercase">{lab}</div>
      <div
        className="mt-1.5 text-2xl font-extrabold tracking-tight tabular-nums"
        style={{ color: tone === "neg" ? "var(--sim-minus)" : tone === "pos" ? "var(--sim-plus)" : "var(--primary-foreground)" }}
      >
        {val}
      </div>
      <div className="mt-1 text-[11px] leading-snug text-white/70">{note}</div>
    </div>
  );

  const vakMax = base.vak.length;
  const forstaKund = Object.keys(base.kundRate)[0] ?? "";
  const breakEven =
    r.planeradeTimmar > 0
      ? Math.round(
          (base.budget - (base.budget * g("reservPct", base.reservPct)) / 100) /
            (r.schematid * (1 + g("korttidPct", base.korttidPct) / 100)),
        ) + " kr/h"
      : "–";

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl border-0 p-6 shadow-lift-lg md:p-8" style={{ background: "var(--djup)" }}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Eyebrow ljus>Vad händer om</Eyebrow>
            <h1 className="mt-1 flex items-center gap-2 text-2xl font-extrabold tracking-tight text-white md:text-3xl">
              <SlidersHorizontal className="size-6" /> Effekt av dina antaganden
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-white/75">
              Dra reglagen och se direkt vad det gör med ekonomin. Allt räknas på en kopia – filen och övriga flikar rörs
              aldrig.
            </p>
          </div>
          <Button
            variant="secondary"
            disabled={!dirty}
            onClick={() => api.simReset()}
            className="bg-white/15 text-white hover:bg-white/25"
          >
            <RotateCcw /> Återställ till filens värden
          </Button>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <SrKort
            lab="Disponibelt efter reserv"
            val={kr0(r.disponibelt)}
            note="Budget − prognos − reserv"
            tone={r.disponibelt >= 0 ? "pos" : "neg"}
          />
          <SrKort lab="Månadsintäkt" val={kr0(r.intakt)} note="Ersättning per kund och dygn" />
          <SrKort lab="Total kostnadsprognos" val={kr0(r.totalPrognos)} note="Schemakostnad + korttidsfrånvaro" />
          <SrKort lab="Dimensionerande behov" val={hh(r.dimBehov)} note="Inkl. vaken natt som golv" />
          <SrKort
            lab="Bemanningsgap i kronor"
            val={kr0(r.gapKr)}
            note={`${hh(r.gapH)} × ${Math.round(r.timkostnad)} kr`}
            tone={r.gapH >= 0 ? "pos" : "neg"}
          />
        </div>
      </Card>

      <div className="grid items-start gap-4 xl:grid-cols-3">
        <Card className="gap-3 rounded-2xl p-6 shadow-lift">
          <Eyebrow>Ekonomi och personal</Eyebrow>
          <Reglage
            id="timkostnad"
            label="1 · Timkostnad"
            min={200}
            max={400}
            step={5}
            baseVal={base.timkostnad}
            fmt={(x) => Math.round(x) + " kr/h"}
          />
          {vakMax ? (
            <Reglage
              id="tillsattVak"
              label="2 · Tillsätt vakanser"
              min={0}
              max={vakMax}
              step={1}
              baseVal={0}
              fmt={(x) => `${x} av ${vakMax}`}
              help={`+${h1(r.extraTimmar)} h schematid`}
            />
          ) : (
            <p className="text-xs text-muted-foreground">Inga vakanta positioner i filen.</p>
          )}
          <Reglage
            id="korttidPct"
            label="3 · Korttidsfrånvaro"
            min={0}
            max={15}
            step={0.5}
            baseVal={base.korttidPct}
            fmt={pct}
          />
          <Reglage
            id="reservPct"
            label="4 · Ekonomisk reserv"
            min={0}
            max={15}
            step={0.5}
            baseVal={base.reservPct}
            fmt={pct}
          />
          <Reglage
            id="buffertPct"
            label="5 · Bemanningsbuffert"
            min={0}
            max={15}
            step={0.5}
            baseVal={base.buffertPct}
            fmt={pct}
          />
          <Reglage
            id="budget"
            label="6 · Personalbudget"
            min={Math.round((base.budget * 0.7) / 1000) * 1000}
            max={Math.round((base.budget * 1.3) / 1000) * 1000}
            step={5000}
            baseVal={base.budget}
            fmt={kr0}
          />
        </Card>

        <Card className="gap-3 rounded-2xl p-6 shadow-lift">
          <Eyebrow>Intäkt</Eyebrow>
          <Reglage
            id="kundRatePct"
            label="7 · Grundersättning per kund"
            min={50}
            max={150}
            step={1}
            baseVal={100}
            fmt={(x) => x + " % av original"}
            help={`≈ ${Math.round(((base.kundRate[forstaKund] ?? 0) * g("kundRatePct", 100)) / 100 || 0)} kr/dygn`}
          />
          <Reglage
            id="kunddagarPct"
            label="8 · Aktiva kunddagar"
            min={50}
            max={120}
            step={1}
            baseVal={100}
            fmt={(x) => x + " % av original"}
            help="kund till/från"
          />
          <div className="pt-2">
            <Eyebrow>Behov och dimensionering</Eyebrow>
          </div>
          <Reglage
            id="nattgolv"
            label="9 · Nattgolv (vaken natt)"
            min={0}
            max={3}
            step={1}
            baseVal={base.nattgolv}
            fmt={(x) => x + " medarb."}
          />
          <Reglage
            id="planeradeTimmar"
            label="10 · Planerade timmar"
            min={Math.round(base.planeradeTimmar * 0.7)}
            max={Math.round(base.planeradeTimmar * 1.3)}
            step={10}
            baseVal={base.planeradeTimmar}
            fmt={hh}
          />
          <Reglage
            id="malPct"
            label="11 · Målnivå (påverkar ej beräkning)"
            min={50}
            max={100}
            step={1}
            baseVal={base.malPct}
            fmt={pct}
          />
        </Card>

        <Card className="gap-0 rounded-2xl p-6 shadow-lift">
          <Eyebrow>Sammansatt</Eyebrow>
          <div className="mt-4 space-y-5">
            <div>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-semibold text-deep">12 · Bemanningsgap i kronor</span>
                <strong
                  className="text-lg font-extrabold tabular-nums"
                  style={{ color: r.gapH >= 0 ? undefined : "var(--korall)" }}
                >
                  {kr0(r.gapKr)}
                </strong>
              </div>
              <p className="mt-1 text-[11px] leading-snug text-muted-foreground/80">
                {r.gapH >= 0 ? "Överkapacitet" : "Underskott"}: {hh(Math.abs(r.gapH))} vid {Math.round(r.timkostnad)}{" "}
                kr/h. Planerade timmar ({hh(r.planeradeTimmar)}) mot dimensionerande behov ({hh(r.dimBehov)}).
              </p>
            </div>
            <div>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-semibold text-deep">13 · Break-even timkostnad</span>
                <strong className="text-lg font-extrabold text-deep tabular-nums">{breakEven}</strong>
              </div>
              <p className="mt-1 text-[11px] leading-snug text-muted-foreground/80">
                Den timkostnad där prognosen (inkl. korttidsfrånvaro) precis möter budgeten efter reserv, vid nuvarande
                schematid.
              </p>
            </div>
            <div>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-semibold text-deep">Resultat (intäkt − kostnad)</span>
                <strong
                  className="text-lg font-extrabold tabular-nums"
                  style={{ color: r.resultat >= 0 ? undefined : "var(--korall)" }}
                >
                  {kr0(r.resultat)}
                </strong>
              </div>
              <p className="mt-1 text-[11px] leading-snug text-muted-foreground/80">
                Månadsintäkt minus total kostnadsprognos med dina antaganden.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <p className="text-[11px] leading-snug text-muted-foreground/80">
        Alla värden räknas på en kopia av filens siffror. Reglagen ändrar aldrig den importerade datan eller övriga
        flikar. Effekterna är aritmetiska – de lägger inte om schemat eller kontrollerar arbetstidsregler.
      </p>
    </div>
  );
}
