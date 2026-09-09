import { useState } from "react";
import { Plus, RotateCcw, X, ArrowLeftRight, Lock, Users, FileText, Upload, ClipboardList, ChevronLeft, ChevronRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { VyApi, VyProps } from "@/lib/bb/vy";
import type { Insats } from "@/lib/bb/typer";
import { TomtLage } from "./Tomt";
import { BekraftaDialog } from "./Bekrafta";
import { Hjalp } from "./Hjalp";
import { notera } from "@/lib/bb/notis";

const DAGAR = ["M", "T", "O", "T", "F", "L", "S"];
const DAGNAMN = ["måndagar", "tisdagar", "onsdagar", "torsdagar", "fredagar", "lördagar", "söndagar"];
const PER_SIDA = 100;

/** Ny kund med validering medan man skriver. */
function NyKundDialog({
  open,
  onOpenChange,
  befintliga,
  onSpara,
  rubrik,
  knapp,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  befintliga: string[];
  onSpara: (namn: string) => void;
  rubrik: string;
  knapp: string;
}) {
  const [namn, setNamn] = useState("");
  const rent = namn.trim();
  const fel = !rent
    ? "Skriv ett namn på kunden, t.ex. Kund 7."
    : befintliga.some((k) => k.toLowerCase() === rent.toLowerCase())
      ? "Det finns redan en kund med det namnet."
      : "";
  const spara = () => {
    if (fel) return;
    onSpara(rent);
    setNamn("");
    onOpenChange(false);
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) setNamn("");
        onOpenChange(o);
      }}
    >
      <DialogContent className="max-w-md rounded-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-extrabold tracking-tight text-deep">{rubrik}</DialogTitle>
          <DialogDescription className="text-sm">
            Kunden får en första insats som utkast, som du sedan justerar i tabellen.
          </DialogDescription>
        </DialogHeader>
        <label className="grid gap-1.5 text-xs font-bold tracking-widest text-muted-foreground uppercase">
          Kundens namn
          <Input
            autoFocus
            value={namn}
            placeholder="t.ex. Kund 7"
            aria-invalid={!!fel && !!namn}
            onChange={(e) => setNamn(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") spara();
            }}
          />
          {fel && namn ? <span className="text-xs font-semibold text-primary normal-case">{fel}</span> : null}
        </label>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Avbryt
          </Button>
          <Button disabled={!!fel} onClick={spara}>
            <Plus /> {knapp}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Tar bort en rad och lägger en notis med Ångra i tio sekunder. */
function taBortMedAngra(api: VyApi, namn: string, gor: () => void) {
  const snap = api.ogonblicksbild();
  gor();
  notera(`${namn} borttagen`, "ok", {
    detalj: "Du kan ångra i tio sekunder.",
    angra: () => api.aterstallOgonblicksbild(snap),
  });
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{children}</div>;
}

/** Ett litet fält som ser ut som resten av systemet, för val i tabellen. */
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

function Kpi({ etikett, tal, not, i }: { etikett: string; tal: string; not: string; i: number }) {
  return (
    <Card
      className="bb-rise gap-0 rounded-2xl p-6 shadow-lift transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift-lg"
      style={{ animationDelay: `${i * 70}ms` }}
    >
      <div className="text-[11px] font-bold tracking-widest text-muted-foreground uppercase">{etikett}</div>
      <div className="mt-2 text-4xl font-extrabold tracking-tight text-deep tabular-nums">{tal}</div>
      <div className="mt-2 text-sm text-muted-foreground">{not}</div>
    </Card>
  );
}

export function Kundbehov({ d, state, api }: VyProps) {
  const [nyKund, setNyKund] = useState<null | "kund" | "plan">(null);
  const [taBort, setTaBort] = useState<null | { id: string; namn: string }>(null);
  const [sida, setSida] = useState(0);

  if (!d) {
    return (
      <TomtLage
        ikon={ClipboardList}
        rubrik="Ingen data ännu"
        text="Läs in verksamhetens Excel-fil, så visas alla insatser här och kan justeras direkt."
        atgarder={[
          { text: "Välj Excel-fil", onClick: () => api.valjFil(), ikon: Upload },
          { text: "Skapa bemanningsbalans", onClick: () => api.skapa(), ikon: Plus, variant: "outline" },
        ]}
      />
    );
  }

  const kundLista: string[] = ["Gemensamt", ...api.gfpKunder()];
  const forstaDag: string = d.from;

  // Vilka veckodagar varje insats-typ förekommer på – förberett en gång.
  const { alla, vdKarta } = (() => {
    const karta: Record<string, Set<number>> = {};
    for (const r of d.rows) {
      if (!r.datum) continue;
      const k = `${r.kund}|${r.insats}|${r.start}`;
      (karta[k] || (karta[k] = new Set())).add(api.veckodagIdx(r.datum));
    }
    const sorterade = d.rows
      .slice()
      .sort((a, b) => (b.status === "utkast" ? 1 : 0) - (a.status === "utkast" ? 1 : 0));
    return { alla: sorterade, vdKarta: karta };
  })();

  // Sidvisning: 100 rader i taget så även 3 000+ insatser ritas direkt.
  const antalSidor = Math.max(1, Math.ceil(alla.length / PER_SIDA));
  const aktuellSida = Math.min(sida, antalSidor - 1);
  const forsta = aktuellSida * PER_SIDA;
  const rader = alla.slice(forsta, forsta + PER_SIDA);

  const idAv = (r: Insats, i: number) => (r._id != null ? r._id : r.kallrad != null ? String(r.kallrad) : "r" + i);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Kpi etikett="Kundbehov" tal={`${api.h1(d.n.kundbehovH)} h`} not={`${d.n.antalInsatser} insatser`} i={0} />
        <Kpi
          etikett="Personalbehov inkl. dubbel"
          tal={`${api.h1(d.n.personalbehovH)} h`}
          not={`${d.n.dubbelbemannadeRader} rader med två personer`}
          i={1}
        />
        <Kpi
          etikett="Dimensionerande resursbehov"
          tal={`${api.h1(d.resursH)} h`}
          not={d.redigerad ? "räknas live ur dina ändringar" : "ur filens modell"}
          i={2}
        />
      </div>

      <Card className="gap-0 overflow-hidden rounded-2xl p-0 shadow-lift">
        <div className="flex flex-wrap items-start justify-between gap-4 p-6 sm:p-8">
          <div className="min-w-0">
            <Eyebrow>
              Kundens behov{" "}
              {d.redigerad ? <span className="text-success">· ändrat av dig</span> : null}
            </Eyebrow>
            <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-deep">Kundens behov i tid</h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              Fasta insatser ligger kvar på sin tid. Flyttbara och gemensamma kan flyttas inom sitt fönster
              (start–senast klar). Ändra direkt i tabellen – alla tal och kurvor räknas om med en gång.{" "}
              <strong className="font-bold text-deep">{d.n.antalInsatser} insatser</strong> i perioden.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 rounded-xl bg-muted p-2">
              <Val
                value={(state.__gfpKund as string) || kundLista[1] || "Gemensamt"}
                onChange={(v) => {
                  state.__gfpKund = v;
                }}
                className="min-w-32 bg-card"
              >
                {api.gfpKunder().map((k: string) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
                <option value="__ny">+ Ny kund…</option>
              </Val>
              <Button
                onClick={() => {
                  const kund = (state.__gfpKund as string) || api.gfpKunder()[0] || "";
                  if (kund === "__ny") {
                    setNyKund("plan");
                    return;
                  }
                  const n = api.laggTillGenomforandeplan(kund);
                  if (n)
                    notera(`Utkast till genomförandeplan skapat för ${kund}`, "ok", {
                      detalj: "Justera tider och längder direkt i tabellen.",
                    });
                }}
              >
                <FileText /> Genomförandeplan
              </Button>
              <Hjalp
                etikett="Om genomförandeplan"
                text="Skapar ett första utkast med typiska insatser för en kund. Du justerar allt efteråt."
              />
            </div>
            <Button variant="outline" onClick={() => setNyKund("kund")}>
              <Users /> Ny kund
            </Button>
            <Button variant="outline" onClick={() => api.kundEditLaggTill(forstaDag)}>
              <Plus /> Insats
            </Button>
            <Button variant="outline" disabled={!d.redigerad} onClick={() => api.aterstallKundEdit()}>
              <RotateCcw /> Återställ
            </Button>
          </div>
        </div>

        <div className="max-h-[640px] overflow-auto border-t border-border">
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-card">
              <TableRow>
                <TableHead className="sticky left-0 z-20 bg-card">Kund</TableHead>
                <TableHead>Insats</TableHead>
                <TableHead>Typ</TableHead>
                <TableHead>Start</TableHead>
                <TableHead>Senast klar</TableHead>
                <TableHead>Minuter</TableHead>
                <TableHead>Dubbel</TableHead>
                <TableHead>Veckodagar</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rader.map((r, i: number) => {
                const id = idAv(r, i);
                const dagar: Set<number> = vdKarta[`${r.kund}|${r.insats}|${r.start}`] || new Set<number>();
                const utkast = r.status === "utkast";
                return (
                  <TableRow key={String(id)} className={cn(utkast && "bg-warning-soft/60")}>
                    <TableCell className={cn("sticky left-0 z-10", utkast ? "bg-warning-soft" : "bg-card")}>
                      <Val value={String(r.kund ?? "")} onChange={(v) => api.kundEditSet(id, "kund", v)}>
                        {kundLista.map((k) => (
                          <option key={k} value={k}>
                            {k}
                          </option>
                        ))}
                      </Val>
                    </TableCell>
                    <TableCell className="max-w-52">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-bold text-deep">{r.insats || ""}</span>
                        {utkast ? (
                          <Badge className="bg-warning-soft text-warning shadow-none">ny</Badge>
                        ) : null}
                      </div>
                      {r["beskrivning"] ? (
                        <div className="truncate text-xs text-muted-foreground">{String(r["beskrivning"])}</div>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Val
                        value={r.flyttbar ? "Flyttbar" : "Fast"}
                        onChange={(v) => api.kundEditSet(id, "typ", v)}
                        className="min-w-24"
                      >
                        <option value="Fast">Fast</option>
                        <option value="Flyttbar">Flyttbar</option>
                      </Val>
                    </TableCell>
                    <TableCell>
                      <Input
                        type="time"
                        className="h-9 w-[104px] px-2 font-semibold tabular-nums"
                        defaultValue={r.start || ""}
                        onBlur={(e) => api.kundEditSet(id, "start", e.target.value)}
                      />
                    </TableCell>
                    <TableCell>
                      {r.flyttbar ? (
                        <Input
                          type="time"
                          className="h-9 w-[104px] px-2 font-semibold tabular-nums"
                          defaultValue={r.fonsterSlut || r.slut || ""}
                          onBlur={(e) => api.kundEditSet(id, "senast", e.target.value)}
                        />
                      ) : (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                              <Lock className="size-3.5" /> fast tid
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>Senast klar gäller bara flyttbara insatser</TooltipContent>
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={1}
                        step={1}
                        className="h-9 w-16 px-2 font-semibold tabular-nums"
                        defaultValue={Math.round(r.minuter || 0)}
                        onBlur={(e) => api.kundEditSet(id, "minuter", e.target.value)}
                      />
                    </TableCell>
                    <TableCell>
                      <label className="flex cursor-pointer items-center gap-2 text-xs font-semibold text-deep-soft">
                        <Checkbox
                          checked={!!r.tvaPersoner}
                          onCheckedChange={(v) => api.kundEditSet(id, "dubbel", !!v)}
                        />
                        Dubbel
                      </label>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {DAGAR.map((dag, di) => {
                          const pa = dagar.has(di);
                          return (
                            <Tooltip key={di}>
                              <TooltipTrigger asChild>
                                <button
                                  type="button"
                                  aria-pressed={pa}
                                  aria-label={pa ? `Ta bort alla ${DAGNAMN[di]}` : `Lägg till på alla ${DAGNAMN[di]}`}
                                  onClick={() => api.kundToggleVeckodag(id, di)}
                                  className={cn(
                                    "grid size-7 place-items-center rounded-md text-[11px] font-bold transition-colors",
                                    pa
                                      ? "bg-primary text-primary-foreground"
                                      : "bg-muted text-muted-foreground hover:text-deep",
                                  )}
                                >
                                  {dag}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>
                                {pa ? `Ta bort alla ${DAGNAMN[di]}` : `Lägg till på alla ${DAGNAMN[di]}`}
                              </TooltipContent>
                            </Tooltip>
                          );
                        })}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Ta bort insatsen"
                            className="text-muted-foreground hover:bg-danger-soft hover:text-primary"
                            onClick={() => setTaBort({ id, namn: `${r.kund} · ${r.insats}` })}
                          >
                            <X />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Ta bort insatsen</TooltipContent>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>

        <div className="flex flex-wrap items-center gap-4 border-t border-border px-6 py-4 text-xs text-muted-foreground sm:px-8">
          <span className="inline-flex items-center gap-1.5">
            <ArrowLeftRight className="size-3.5 text-primary" /> Flyttbar – kan flyttas inom sitt fönster
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Lock className="size-3.5" /> Fast – ligger kvar på sin tid
          </span>
          <span className="ml-auto flex items-center gap-3">
            <span>
              Visar {alla.length ? forsta + 1 : 0}–{forsta + rader.length} av {alla.length} insatser
            </span>
            {antalSidor > 1 ? (
              <span className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  aria-label="Föregående sida"
                  disabled={aktuellSida === 0}
                  onClick={() => setSida(aktuellSida - 1)}
                >
                  <ChevronLeft /> Föregående
                </Button>
                <span className="font-semibold text-deep tabular-nums">
                  Sida {aktuellSida + 1} av {antalSidor}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  aria-label="Nästa sida"
                  disabled={aktuellSida >= antalSidor - 1}
                  onClick={() => setSida(aktuellSida + 1)}
                >
                  Nästa <ChevronRight />
                </Button>
              </span>
            ) : null}
          </span>
        </div>
      </Card>

      <NyKundDialog
        open={!!nyKund}
        onOpenChange={(o) => { if (!o) setNyKund(null); }}
        befintliga={kundLista}
        rubrik={nyKund === "plan" ? "Ny kund med genomförandeplan" : "Ny kund"}
        knapp={nyKund === "plan" ? "Skapa plan" : "Lägg till kund"}
        onSpara={(namn) => {
          if (nyKund === "plan") {
            const n = api.laggTillGenomforandeplan(namn);
            if (n)
              notera(`Utkast till genomförandeplan skapat för ${namn}`, "ok", {
                detalj: "Justera tider och längder direkt i tabellen.",
              });
          } else {
            api.kundLaggTillNy(namn, forstaDag);
            notera(`${namn} tillagd`, "ok", { detalj: "Lägg till fler insatser i tabellen." });
          }
          setNyKund(null);
        }}
      />

      <BekraftaDialog
        open={!!taBort}
        onOpenChange={(o) => { if (!o) setTaBort(null); }}
        rubrik={`Ta bort ${taBort?.namn ?? "insatsen"}?`}
        text="Det går att ångra i tio sekunder efteråt."
        onBekrafta={() => {
          if (taBort) taBortMedAngra(api, taBort.namn, () => api.kundEditTaBort(taBort.id));
          setTaBort(null);
        }}
      />
    </div>
  );
}
