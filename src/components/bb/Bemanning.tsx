import { useRef, useState } from "react";
import { ChevronDown, ChevronUp, Moon, Plus, RotateCcw, Trash2, Upload, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { VyProps } from "@/lib/bb/vy";
import type { BladRad } from "@/lib/bb/typer";
import { TomtLage } from "./Tomt";
import { BekraftaDialog } from "./Bekrafta";
import { Hjalp } from "./Hjalp";
import { notera } from "@/lib/bb/notis";

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

function Val({
  value,
  onChange,
  children,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "h-9 rounded-lg border border-input bg-card px-2 text-sm font-semibold text-deep",
        "transition-colors outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40",
        className,
      )}
    >
      {children}
    </select>
  );
}

function Chip({ etikett, tal, not, i }: { etikett: string; tal: string; not: string; i: number }) {
  return (
    <Card
      className="bb-rise gap-0 rounded-2xl p-5 shadow-lift transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift-lg"
      style={{ animationDelay: `${i * 60}ms` }}
    >
      <div className="text-2xl font-extrabold tracking-tight text-deep tabular-nums">{tal}</div>
      <div className="mt-1 text-[11px] font-bold tracking-widest text-muted-foreground uppercase">{etikett}</div>
      <div className="mt-1 text-xs text-muted-foreground/80">{not}</div>
    </Card>
  );
}

function Ruta({ etikett, children }: { etikett: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl bg-muted/50 px-4 py-3">
      <div className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">{etikett}</div>
      <div className="mt-1 flex items-center gap-1 text-sm font-semibold text-deep tabular-nums">{children}</div>
    </div>
  );
}

const num = (r: BladRad, c: string) => (typeof r[c] === "number" ? r[c] : 0);

export function Bemanning({ d, state, api }: VyProps) {
  const h1 = api.h1;
  const kr = api.kr;
  const [oppen, setOppen] = useState<string | null>(null);
  const [taBort, setTaBort] = useState<null | { id: string; namn: string }>(null);
  const formRef = useRef<HTMLDivElement | null>(null);
  const namnRef = useRef<HTMLInputElement | null>(null);
  const [ny, setNy] = useState({
    namn: "",
    status: "Anställd",
    ssg: "100",
    heltid: "40",
    passprofil: "Dag/kväll",
    timkostnad: "270",
    helg: "Varannan helg",
    natt: false,
  });

  if (!d || !api.harPersonal()) {
    return (
      <TomtLage
        ikon={Users}
        rubrik="Bemanningen kan inte visas ännu"
        text="Listan över medarbetare saknas i den inlästa filen. Läs in en fil med medarbetare, så visas namn, sysselsättningsgrad och kapacitet här."
        atgarder={[{ text: "Välj Excel-fil", onClick: () => api.valjFil(), ikon: Upload }]}
      />
    );
  }

  const rader = api.personalRader();
  const redigerad: boolean = api.personalEditAktiv();
  const idAv = (r: BladRad, i: number) => (r["_pid"] != null ? String(r["_pid"]) : "p" + i);

  // Validering av formuläret för ny medarbetare (bara utseende och vägledning).
  const nyttNamn = ny.namn.trim();
  const namnFel = !nyttNamn
    ? "Skriv medarbetarens namn."
    : rader.some((r) => String(r["Medarbetare"] ?? "").trim().toLowerCase() === nyttNamn.toLowerCase())
      ? "Det finns redan en medarbetare med det namnet."
      : "";
  const ssgTal = Number(ny.ssg);
  const ssgFel = !Number.isFinite(ssgTal) || ssgTal < 0 || ssgTal > 150 ? "Ange mellan 0 och 150." : "";
  const kanLagga = !namnFel && !ssgFel;


  const aktiva = rader.filter((r) => String(r["Status"]).toLowerCase() === "anställd");
  const vakanta = rader.filter((r) => String(r["Status"]).toLowerCase() === "vakant");
  const budgetKostnad = rader.reduce((s, r) => s + num(r, "Budgetkostnad/mån"), 0);
  const budgetH = rader.reduce((s, r) => s + num(r, "Budget h/mån"), 0);
  const fte = rader.reduce((s, r) => s + num(r, "Grund-SSG"), 0);
  const vakantFte = vakanta.reduce((s, r) => s + num(r, "Grund-SSG"), 0);
  const nattbeh = rader.filter(
    (r) => String(r["Nattbehörig"] ?? "") === "Ja" || /natt/i.test(String(r["Passprofil"] ?? "")),
  ).length;

  const chips: [string, string, string][] = [
    ["Aktiva", String(aktiva.length), "anställda"],
    ["Kapacitet", fte.toFixed(2) + " FTE", "summa SSG"],
    ["Vakant", vakantFte.toFixed(2) + " FTE", vakanta.length + " positioner"],
    ["Nattbehöriga", String(nattbeh), "kan nattpass"],
    ["Budgettid", h1(budgetH) + " h", "per månad"],
    ["Personalkostnad", kr(budgetKostnad), "per månad"],
  ];

  // Dölj tomma platshållare, precis som förut.
  const synliga = rader.filter((r) => {
    const namn = String(r["Medarbetare"] || "").trim();
    const status = String(r["Status"] || "").toLowerCase();
    const budget = num(r, "Budget h/mån");
    const tom = /^ny medarbetare/i.test(namn) && budget === 0 && status !== "anställd" && status !== "vakant";
    return !tom;
  });

  return (
    <div className="space-y-4">
      <Card className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Eyebrow>Medarbetare och villkor {redigerad ? "· ändrat" : ""}</Eyebrow>
            <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">Medarbetare och kapacitet</h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
              Uppgifterna styr vilka pass varje person kan få. Klicka på en medarbetare för att se och justera
              detaljer.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              onClick={() => {
                formRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                setTimeout(() => namnRef.current?.focus(), 300);
              }}
            >
              <Plus /> Lägg till
            </Button>
            <Button variant="outline" disabled={!redigerad} onClick={() => api.aterstallPersonalEdit()}>
              <RotateCcw /> Återställ
            </Button>
          </div>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {chips.map(([l, v, n], i) => (
            <Chip key={l} etikett={l} tal={v} not={n} i={i} />
          ))}
        </div>
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        {synliga.map((r, i) => {
          const id = idAv(r, i);
          const namn = String(r["Medarbetare"] ?? "");
          const init =
            namn
              .split(/\s+/)
              .map((w) => w[0])
              .join("")
              .slice(0, 2)
              .toUpperCase() || "–";
          const status = String(r["Status"] ?? "");
          const ssg = num(r, "Grund-SSG");
          const profil = String(r["Passprofil"] ?? "–");
          const budget = num(r, "Budget h/mån");
          const tillg = num(r, "Tillgängligt h/mån");
          const timkost = num(r, "Timkostnad");
          const kostnad = num(r, "Budgetkostnad/mån");
          const helg = String(r["Helgmodell"] ?? "–");
          const rapport = String(r["Rapportindikation"] ?? "");
          const natt = String(r["Nattbehörig"] ?? "") === "Ja" || /natt/i.test(profil);
          const diff = tillg - budget;
          const utfalld = oppen === id;

          return (
            <Card
              key={id}
              className={cn(
                "gap-0 overflow-hidden rounded-2xl p-0 shadow-lift transition-all duration-200",
                utfalld ? "shadow-lift-lg" : "hover:-translate-y-0.5 hover:shadow-lift-lg",
              )}
            >
              <button
                type="button"
                onClick={() => setOppen(utfalld ? null : id)}
                className="flex w-full items-center gap-3 px-6 py-5 text-left"
              >
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-secondary text-sm font-extrabold text-deep">
                  {init}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-base font-extrabold text-deep">{namn}</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground tabular-nums">
                    Tillgänglig <strong className="text-deep">{h1(tillg)}</strong> av {h1(budget)} h{" "}
                    <span className={diff < 0 ? "font-bold text-primary" : "font-bold text-[var(--ok)]"}>
                      {diff >= 0 ? "+" : ""}
                      {h1(diff)} h
                    </span>
                  </span>
                </span>
                <Badge
                  variant="secondary"
                  className={cn(
                    "rounded-full px-3 py-1 text-[11px] font-bold",
                    status.toLowerCase() === "vakant" && "bg-[var(--varn-mjuk)] text-[var(--varn)]",
                    status.toLowerCase() === "anställd" && "bg-[var(--ok-mjuk)] text-[var(--ok)]",
                  )}
                >
                  {status}
                </Badge>
                {utfalld ? (
                  <ChevronUp className="size-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="size-4 text-muted-foreground" />
                )}
              </button>

              <div className="flex flex-wrap gap-2 px-6 pb-5">
                {profil && profil !== "–" ? (
                  <Badge variant="outline" className="rounded-full px-3 py-1 text-[11px] font-semibold">
                    {profil}
                  </Badge>
                ) : null}
                {natt ? (
                  <Badge variant="outline" className="rounded-full px-3 py-1 text-[11px] font-semibold">
                    <Moon className="size-3" /> Nattbehörig
                  </Badge>
                ) : null}
                {helg && helg !== "–" ? (
                  <Badge variant="outline" className="rounded-full px-3 py-1 text-[11px] font-semibold">
                    {helg}
                  </Badge>
                ) : null}
                <Badge variant="outline" className="rounded-full px-3 py-1 text-[11px] font-semibold">
                  Undersköterska
                </Badge>
                <Badge variant="outline" className="rounded-full px-3 py-1 text-[11px] font-semibold">
                  Läkemedelsdeleg.
                </Badge>
              </div>

              {utfalld ? (
                <div className="border-t border-border bg-muted/20 px-6 py-6">
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    <Ruta etikett="Namn">
                      <Input
                        className="h-9 w-[150px]"
                        defaultValue={namn}
                        onBlur={(e) => api.personalSet(id, "namn", e.target.value)}
                      />
                    </Ruta>
                    <Ruta etikett="Status">
                      <Val value={status} onChange={(v) => api.personalSet(id, "status", v)}>
                        <option>Anställd</option>
                        <option>Vakant</option>
                        <option>Tjänstledig</option>
                      </Val>
                    </Ruta>
                    <Ruta etikett="SSG">
                      <Input
                        className="h-9 w-[74px]"
                        type="number"
                        min={0}
                        max={150}
                        step={5}
                        defaultValue={Math.round(ssg * 100)}
                        onBlur={(e) => api.personalSet(id, "ssg", e.target.value)}
                      />{" "}
                      %
                    </Ruta>
                    <Ruta etikett="Passprofil">
                      <Val value={profil} onChange={(v) => api.personalSet(id, "passprofil", v)}>
                        <option>Dag</option>
                        <option>Dag/kväll</option>
                        <option>Kväll</option>
                        <option>Natt</option>
                        <option>Blandat</option>
                      </Val>
                    </Ruta>
                    <Ruta etikett="Heltidsmått">
                      <Input
                        className="h-9 w-[84px]"
                        type="number"
                        min={0}
                        max={60}
                        step={0.5}
                        defaultValue={num(r, "Heltid h/vecka")}
                        onBlur={(e) => api.personalSet(id, "heltid", e.target.value)}
                      />{" "}
                      h/v
                    </Ruta>
                    <Ruta etikett="Timkostnad">
                      <Input
                        className="h-9 w-[84px]"
                        type="number"
                        min={0}
                        step={10}
                        defaultValue={Math.round(timkost)}
                        onBlur={(e) => api.personalSet(id, "timkostnad", e.target.value)}
                      />{" "}
                      kr
                    </Ruta>
                    <Ruta etikett="Budgettid">
                      <Input
                        className="h-9 w-[84px]"
                        type="number"
                        min={0}
                        step={1}
                        defaultValue={Math.round(budget * 10) / 10}
                        onBlur={(e) => api.personalSet(id, "budget", e.target.value)}
                      />{" "}
                      h/mån
                    </Ruta>
                    <Ruta etikett="Kostnad">{kr(kostnad)}/mån</Ruta>
                    <Ruta etikett="Helgmodell">
                      <Val value={helg} onChange={(v) => api.personalSet(id, "helg", v)}>
                        <option>Varannan helg</option>
                        <option>Var tredje helg</option>
                        <option>Varje helg</option>
                        <option>Inga helger</option>
                      </Val>
                    </Ruta>
                    <Ruta etikett="Nattbehörig">
                      <Val value={natt ? "Ja" : "Nej"} onChange={(v) => api.personalSet(id, "natt", v === "Ja")}>
                        <option>Ja</option>
                        <option>Nej</option>
                      </Val>
                    </Ruta>

                  </div>
                  {rapport ? (
                    <p className="mt-4 rounded-xl bg-[var(--varn-mjuk)] px-4 py-3 text-sm text-[var(--varn)]">
                      <strong>Rapportindikation:</strong> {rapport}
                    </p>
                  ) : null}
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button variant="outline" className="mt-5" onClick={() => setTaBort({ id, namn })}>
                        <Trash2 /> Ta bort medarbetare
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Tas bort ur arbetskopian – filen ändras inte</TooltipContent>
                  </Tooltip>
                </div>
              ) : null}
            </Card>
          );
        })}
      </div>

      <Card ref={formRef} className="gap-0 rounded-2xl p-7 shadow-lift sm:p-8">
        <Eyebrow>Ny medarbetare</Eyebrow>
        <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">Lägg till medarbetare</h2>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Fyll i uppgifterna och klicka på Lägg till. Namn, SSG, heltidsmått, timkostnad och passprofil påverkar budget
          och kapacitet direkt.
        </p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="grid gap-1.5 text-xs font-bold tracking-widest text-muted-foreground uppercase">
            Namn
            <Input
              ref={namnRef}
              placeholder="t.ex. Kepler"
              value={ny.namn}
              aria-invalid={!!namnFel && !!ny.namn}
              onChange={(e) => setNy({ ...ny, namn: e.target.value })}
            />
            {namnFel && ny.namn ? (
              <span className="text-xs font-semibold text-primary normal-case">{namnFel}</span>
            ) : null}
          </label>
          <label className="grid gap-1.5 text-xs font-bold tracking-widest text-muted-foreground uppercase">
            Status
            <Val value={ny.status} onChange={(v) => setNy({ ...ny, status: v })}>
              <option>Anställd</option>
              <option>Vakant</option>
              <option>Tjänstledig</option>
            </Val>
          </label>
          <label className="grid gap-1.5 text-xs font-bold tracking-widest text-muted-foreground uppercase">
            <span className="flex items-center gap-1">
              SSG %
              <Hjalp etikett="Om SSG" text="Sysselsättningsgrad i procent av heltid. 100 betyder heltid." />
            </span>
            <Input
              type="number"
              min={0}
              max={150}
              step={5}
              value={ny.ssg}
              aria-invalid={!!ssgFel}
              onChange={(e) => setNy({ ...ny, ssg: e.target.value })}
            />
            {ssgFel ? <span className="text-xs font-semibold text-primary normal-case">{ssgFel}</span> : null}
          </label>
          <label className="grid gap-1.5 text-xs font-bold tracking-widest text-muted-foreground uppercase">
            Heltid h/v
            <Input
              type="number"
              min={0}
              max={40}
              step={0.5}
              value={ny.heltid}
              onChange={(e) => setNy({ ...ny, heltid: e.target.value })}
            />
          </label>
          <label className="grid gap-1.5 text-xs font-bold tracking-widest text-muted-foreground uppercase">
            Passprofil
            <Val value={ny.passprofil} onChange={(v) => setNy({ ...ny, passprofil: v })}>
              <option>Dag/kväll</option>
              <option>Natt</option>
              <option>Flexibel</option>
            </Val>
          </label>
          <label className="grid gap-1.5 text-xs font-bold tracking-widest text-muted-foreground uppercase">
            Timkostnad kr
            <Input
              type="number"
              min={0}
              step={10}
              value={ny.timkostnad}
              onChange={(e) => setNy({ ...ny, timkostnad: e.target.value })}
            />
          </label>
          <label className="grid gap-1.5 text-xs font-bold tracking-widest text-muted-foreground uppercase">
            Helgmodell
            <Val value={ny.helg} onChange={(v) => setNy({ ...ny, helg: v })}>
              <option>Varannan helg</option>
              <option>Varje helg</option>
              <option>Var tredje helg</option>
            </Val>
          </label>
          <label className="flex items-center gap-2 self-end pb-2 text-sm font-semibold text-deep">
            <Checkbox checked={ny.natt} onCheckedChange={(v) => setNy({ ...ny, natt: v === true })} />
            Nattbehörig
          </label>
        </div>
        <Button
          className="mt-6 w-fit"
          disabled={!kanLagga}
          onClick={() => {
            api.personalLaggTillFran(ny);
            notera(`${nyttNamn} tillagd`, "ok", { detalj: "Budget och kapacitet är uppdaterade." });
            setNy({ ...ny, namn: "" });
          }}
        >
          <Plus /> Lägg till medarbetare
        </Button>
      </Card>

      <BekraftaDialog
        open={!!taBort}
        onOpenChange={(o) => { if (!o) setTaBort(null); }}
        rubrik={`Ta bort ${taBort?.namn ?? "medarbetaren"}?`}
        text="Medarbetaren tas bort ur arbetskopian. Det går att ångra i tio sekunder."
        onBekrafta={() => {
          if (!taBort) return;
          const snap = api.ogonblicksbild();
          api.personalTaBort(taBort.id);
          notera(`${taBort.namn} borttagen`, "ok", {
            detalj: "Du kan ångra i tio sekunder.",
            angra: () => api.aterstallOgonblicksbild(snap),
          });
          setTaBort(null);
        }}
      />
    </div>
  );
}
