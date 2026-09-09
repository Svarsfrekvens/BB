import { useSyncExternalStore, useState, useEffect, type ReactNode } from "react";
import { Menu, Plus, RotateCcw, Check, Download, Loader2 } from "lucide-react";
import { bbSkal } from "@/lib/bb/skal";
import { bbVy, APP_VERSION } from "@/lib/bb/vy";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { FragaAppen } from "./FragaAppen";
import { Notiser } from "./Notiser";
import { BekraftaDialog } from "./Bekrafta";
import { Progress } from "@/components/ui/progress";

/** Kort förklarande undertext per sida – gör menyn självinstruerande. */
const UNDERTEXT: Record<string, string> = {
  hem: "Översikt och flöde",
  verksamhet: "Vilken enhet",
  kundgrupp: "Kundernas behov (Sekoia)",
  schemafil: "Nuvarande personalschema",
  medarbetare: "Uppgifter och villkor",
  underlag: "Filerna appen räknar på",
  foreefter: "Vad som förändrats",
  schemaforslag: "Pass och justeringar",
  oversikt: "Resultat efter bemanningsbalans",
  kundbehov: "Insatser och tider per kund",
  resurskurva: "Behov över dygnet",
  personal: "Medarbetare och kapacitet",
  schema: "Pass per medarbetare",
  nyckeltal: "Kundnära tid och mål",
  ekonomi: "Intäkter mot kostnader",
  kunder: "Timmar per kund",
  sprid: "Flytta rörliga insatser",
  intakter: "Ersättning och underlag",
  atgarder: "Vad du bör göra nu",
  simulering: "Prova antaganden",
  villkor: "Regler som styr schemat",
  kontroller: "Hittade fel i datan",
  installningar: "Grunduppgifter",
};

function useSkal() {
  return useSyncExternalStore(
    (f) => bbSkal.subscribe(f),
    () => bbSkal.get(),
    () => bbSkal.get(),
  );
}

function NavInnehall({ onNavigate }: { onNavigate?: () => void }) {
  const s = useSkal();
  const [oppna, setOppna] = useState<Record<string, boolean>>({ Start: true });
  useEffect(() => {
    const aktivGrupp = s.tabs.find((t) => t.id === s.tab)?.grupp;
    if (aktivGrupp) setOppna((nu) => ({ ...nu, [aktivGrupp]: true }));
  }, [s.tab, s.tabs]);
  return (
    <nav className="flex flex-col gap-1 p-3">
      {s.grupper.map((grupp: string) => {
        const iGruppen = s.tabs.filter((t) => t.grupp === grupp);
        if (!iGruppen.length) return null;
        const oppen = oppna[grupp] ?? grupp === "Start";
        return (
          <div key={grupp} className="flex flex-col gap-1">
            <button
              type="button"
              aria-expanded={oppen}
              onClick={() => setOppna((nu) => ({ ...nu, [grupp]: !oppen }))}
              className="mt-4 flex items-center justify-between rounded-lg px-3 py-2 text-[11px] font-bold tracking-widest text-muted-foreground uppercase transition-colors hover:bg-muted hover:text-foreground"
            >
              {grupp}<span className="opacity-60">{oppen ? "▾" : "▸"}</span>
            </button>
            {oppen &&
              iGruppen.map((t) => {
                const aktiv = t.id === s.tab;
                const last = !!t.last;
                return (
                  <button
                    key={t.id}
                    type="button"
                    disabled={last}
                    title={last ? "Låst tills föregående steg är klart" : undefined}
                    onClick={() => {
                      if (last) return;
                      bbSkal.actions.setTab(t.id);
                      onNavigate?.();
                    }}
                    className={cn(
                      "group flex w-full items-start gap-3 rounded-xl border-l-4 px-3 py-2 text-left transition-colors duration-200",
                      aktiv
                        ? "border-primary bg-primary-soft/40 text-deep"
                        : "border-transparent text-deep hover:bg-muted",
                      last && "cursor-not-allowed opacity-45 hover:bg-transparent",
                    )}
                  >
                    <span
                      className={cn(
                        "mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg text-[13px] font-bold",
                        aktiv ? "bg-primary-soft text-primary" : t.klar ? "bg-success-soft text-success" : "bg-muted text-deep-soft",
                      )}
                      aria-hidden="true"
                    >
                      {t.klar ? "✓" : t.ic}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={cn("block truncate text-sm", aktiv ? "font-bold" : "font-normal")}>
                        {t.label}
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {t.sub || UNDERTEXT[t.id]}
                      </span>
                    </span>

                    {last ? (
                      <span className="mt-1 shrink-0 text-[11px] opacity-70" aria-hidden="true">
                        🔒
                      </span>
                    ) : null}
                  </button>
                );
              })}
          </div>
        );
      })}
    </nav>
  );
}

function Varumarke() {
  return (
    <div className="flex items-center gap-3 border-b border-border px-5 py-5">
      <div className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-deep to-teal text-sm font-extrabold text-white shadow-lift">
        BB
      </div>
      <div className="leading-tight">
        <strong className="block text-sm font-extrabold text-deep">Bemanningsbalans</strong>
        <span className="block text-xs text-muted-foreground">Kundens behov först</span>
      </div>
    </div>
  );
}

function Sidfot() {
  const s = useSkal();
  return (
    <div className="mt-auto border-t border-border px-5 py-4 text-xs">
      <span className="text-muted-foreground">Aktuell verksamhet</span>
      <strong className="mt-1 block truncate text-sm font-bold text-deep">{s.org}</strong>
      <span className="mt-0.5 block text-muted-foreground">{s.periodFoot}</span>
      <span className="mt-2 block text-[11px] text-muted-foreground">
        Bemanningsbalans v{s.version || APP_VERSION} · pilot
      </span>
    </div>
  );
}

function Stegrad() {
  const s = useSkal();
  if (s.stegIdx === -1) return null;
  return (
    <div className="px-5 pb-4 sm:px-8">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-primary-soft px-3 py-1 text-xs font-bold text-primary">
          Steg {s.stegIdx + 1} av {s.steg.length}
        </span>
        <div className="flex flex-wrap items-center gap-1.5">
          {s.steg.map((st, i: number) => {
            const aktiv = i === s.stegIdx;
            const klar = i < s.stegIdx;
            return (
              <Tooltip key={st.id}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    aria-label={`Gå till steg ${i + 1}: ${st.label}`}
                    onClick={() => bbSkal.actions.setTab(st.id)}
                    className={cn(
                      "flex items-center gap-2 rounded-full border px-2 py-1.5 text-xs font-semibold transition-all duration-200 md:px-3",
                      aktiv
                        ? "border-primary bg-primary text-primary-foreground shadow-lift"
                        : klar
                          ? "border-transparent bg-primary-soft text-primary"
                          : "border-border bg-card text-muted-foreground hover:text-deep",
                    )}
                  >
                    <span
                      className={cn(
                        "grid size-5 place-items-center rounded-full text-[10px] font-bold",
                        aktiv ? "bg-primary-foreground/20" : "bg-muted",
                      )}
                    >
                      {klar ? <Check className="size-3" /> : i + 1}
                    </span>
                    <span className="hidden md:inline">{st.label}</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent>Klicka för att gå till steget</TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </div>
      {/* På smal skärm visar cirklarna bara siffror – namnet står här. */}
      <div className="mt-1.5 text-xs font-semibold text-deep md:hidden">{s.steg[s.stegIdx]?.label}</div>
    </div>
  );
}

/** Visas medan en Excel-fil läses in. */
function LaserIn() {
  const v = useSyncExternalStore(
    (f) => bbVy.subscribe(f),
    () => bbVy.get(),
    () => bbVy.get(),
  );
  if (!v.laser) return null;
  return (
    <div className="fixed inset-x-0 top-0 z-50 flex justify-center p-3">
      <div className="flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-bold text-deep shadow-lift-lg">
        <Loader2 className="size-4 animate-spin text-primary" /> Läser in…
      </div>
      <Progress value={60} className="sr-only" />
    </div>
  );
}

export function Skal({ children }: { children: ReactNode }) {
  const s = useSkal();
  const [mobilOppen, setMobilOppen] = useState(false);
  const [fragaOm, setFragaOm] = useState(false);
  const [optimerar, setOptimerar] = useState(false);

  // Varna innan fliken stängs om arbetet inte är exporterat.
  useEffect(() => {
    if (!s.osparat) return;
    const varna = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "Du har osparade ändringar. Exportera innan du lämnar?";
      return e.returnValue;
    };
    window.addEventListener("beforeunload", varna);
    return () => window.removeEventListener("beforeunload", varna);
  }, [s.osparat]);


  const skapa = () => {
    setOptimerar(true);
    // Kort laddningsläge så knappen visar att något händer.
    setTimeout(() => {
      try {
        bbSkal.actions.skapa();
      } finally {
        setOptimerar(false);
      }
    }, 60);
  };

  return (
    <TooltipProvider delayDuration={200}>
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 flex h-screen w-72 shrink-0 flex-col overflow-y-auto border-r border-border bg-card max-lg:hidden">
        <Varumarke />
        <NavInnehall />
        <Sidfot />
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex flex-wrap items-center gap-3 border-b border-border bg-background/85 px-5 py-4 backdrop-blur sm:px-8">
          <Sheet open={mobilOppen} onOpenChange={setMobilOppen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" className="lg:hidden" aria-label="Öppna menyn">
                <Menu />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-80 overflow-y-auto p-0">
              <Varumarke />
              <NavInnehall onNavigate={() => setMobilOppen(false)} />
              <Sidfot />
            </SheetContent>
          </Sheet>

          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-bold tracking-widest text-primary uppercase">{s.eyebrow}</div>
            <h1 className="truncate text-2xl font-extrabold tracking-tight text-deep sm:text-3xl">{s.titel}</h1>
          </div>

          <div className="flex items-center gap-2">
            <span className="hidden text-[13px] text-muted-foreground xl:inline">
              {s.osparat ? (
                <span className="font-semibold text-[var(--warning)]">Osparade ändringar</span>
              ) : (
                "Ändringar sparas när du exporterar"
              )}
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="outline" className="relative" onClick={() => bbSkal.actions.exportera?.()}>
                  <Download /> <span className="hidden sm:inline">Exportera till Excel</span>
                  {s.osparat && (
                    <span
                      className="absolute -top-1 -right-1 size-2.5 rounded-full bg-[var(--warning)] ring-2 ring-background"
                      aria-hidden="true"
                    />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {s.osparat ? "Du har ändringar som inte är exporterade" : "Spara ditt arbete som en Excel-fil"}
              </TooltipContent>
            </Tooltip>
            {s.optimerat ? (
              <Button variant="outline" onClick={() => setFragaOm(true)}>
                <RotateCcw /> Börja om
              </Button>
            ) : (
              <Button onClick={skapa} disabled={optimerar}>
                {optimerar ? <Loader2 className="animate-spin" /> : <Plus />}
                {optimerar ? "Optimerar…" : "Skapa bemanningsbalans"}
              </Button>
            )}
          </div>
        </header>

        <Stegrad />
        <div className="px-5 pb-[6rem] sm:px-8">{children}</div>

        <FragaAppen />
        <LaserIn />
        <Notiser />

        <BekraftaDialog
          open={fragaOm}
          onOpenChange={setFragaOm}
          rubrik="Börja om från nuläget?"
          text="Dina ändringar i den här sessionen försvinner. Exportera först om du vill spara dem."
          bekraftaText="Börja om"
          extraText="Exportera först"
          onExtra={() => {
            bbSkal.actions.exportera?.();
            setFragaOm(false);
          }}
          onBekrafta={() => bbSkal.actions.borjaOm()}
        />
      </main>
    </div>
    </TooltipProvider>
  );
}
