import { useSyncExternalStore, useState, useEffect, type ReactNode } from "react";
import { Menu, RotateCcw, Download, Loader2 } from "lucide-react";
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
import { ProcessFlode } from "./ProcessFlode";
import { korBemanningsbalans, atterupptaMotorJobb } from "@/lib/bb/korBemanningsbalans";
import { kopplaAtterupptning } from "@/lib/bb/motorJobb";
import { readinessFranApi } from "@/lib/bb/vcFlode";
import { hamtaStartlage, lyssnaStartlage, sattStartlage } from "@/lib/bb/startlage";
import { oversigtProcessLagen, oversigtProcessTab } from "@/lib/bb/oversiktProcess";

/** Kort förklarande undertext per sida – gör menyn självinstruerande. */
const UNDERTEXT: Record<string, string> = {
  hem: "Översikt och återuppta",
  oversikt: "Samma översikt som Hem",
  verksamhet: "Vilken enhet",
  kundgrupp: "Kundernas behov (Sekoia)",
  schemafil: "Nuvarande personalschema",
  medarbetare: "Villkor och kompetenser",
  underlag: "Filerna appen räknar på",
  uppladdning: "Kundbehov och schema",
  planering: "Planeringsaktiviteter",
  forutsattningar: "Förutsättningar innan balans",
  foreefter: "Före mot planerad balans",
  schemaforslag: "Passlista",
  kundbehov: "Insatser och tider per kund",
  resurskurva: "Behov över dygnet",
  personal: "Medarbetare och kapacitet",
  schema: "Pass per medarbetare",
  nyckeltal: "Så blev schemaperioden",
  ekonomi: "Rätt resurs i rätt tid",
  resultat: "Så planerar vi schemaperioden",
  omplanering: "Förändring under perioden",
  motor: "Skapa bemanningsbalans",
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
    <nav className="flex flex-col gap-0.5 px-3 pb-3">
      {s.grupper.map((grupp: string) => {
        const iGruppen = s.tabs.filter((t) => t.grupp === grupp);
        if (!iGruppen.length) return null;
        const oppen = oppna[grupp] ?? grupp === "Start";
        return (
          <div key={grupp} className="flex flex-col gap-0.5">
            <button
              type="button"
              aria-expanded={oppen}
              onClick={() => setOppna((nu) => ({ ...nu, [grupp]: !oppen }))}
              className="mt-5 flex items-center justify-between rounded-lg px-3 py-1.5 text-[12px] font-semibold tracking-[0.14em] text-muted-foreground uppercase first:mt-1 hover:text-deep"
            >
              {grupp}<span className="opacity-50">{oppen ? "▾" : "▸"}</span>
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
                      sattStartlage("app");
                      bbSkal.actions.setTab(t.id);
                      onNavigate?.();
                    }}
                    className={cn(
                      "group flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition-colors duration-200",
                      aktiv ? "bg-deep text-white shadow-lift" : "text-deep hover:bg-primary-soft/50",
                      last && "cursor-not-allowed opacity-40 hover:bg-transparent",
                    )}
                  >
                    <span
                      className={cn(
                        "grid size-8 shrink-0 place-items-center rounded-xl text-[13px] font-bold",
                        aktiv ? "bg-white/15 text-white" : t.klar ? "bg-primary-soft text-deep" : "bg-muted text-muted-foreground",
                      )}
                      aria-hidden="true"
                    >
                      {t.klar ? "✓" : t.ic}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={cn("block truncate text-[15px]", aktiv ? "font-bold" : "font-medium")}>
                        {t.label}
                      </span>
                      {aktiv ? (
                        <span className="block truncate text-[13px] text-white/70">
                          {t.sub || UNDERTEXT[t.id]}
                        </span>
                      ) : null}
                    </span>

                    {last ? (
                      <span className="shrink-0 text-[12px] opacity-70" aria-hidden="true">
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
    <div className="flex items-center gap-3 px-5 py-5">
      <div className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-deep to-[#163a73] text-sm font-extrabold text-white shadow-lift">
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
  const v = useSyncExternalStore(
    (f) => bbVy.subscribe(f),
    () => bbVy.get(),
    () => bbVy.get(),
  );
  if (!v.api) return null;
  const steg = oversigtProcessLagen({
    aktivTab: s.tab,
    readiness: readinessFranApi(v.api),
    harBalans: v.api.harBalans(),
    harUtfall: false,
    pagaende: Boolean(v.api.motorJobb?.()?.id && v.api.motorJobb?.()?.phase !== "completed"),
  });
  return (
    <div className="px-5 pb-4 pt-2 sm:px-8">
      <div className="rounded-[28px] bg-white/75 px-3 py-3 shadow-lift sm:px-5">
        <ProcessFlode
          steg={steg}
          onValj={(id) => {
            sattStartlage("app");
            if (id === "skapa") {
              if (s.tab === "forutsattningar" && v.api && s.skapaAktiv !== false) {
                void korBemanningsbalans({ api: v.api, state: v.state });
                return;
              }
              bbSkal.actions.setTab("forutsattningar");
              return;
            }
            bbSkal.actions.setTab(oversigtProcessTab(id));
          }}
        />
      </div>
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
  const startlage = useSyncExternalStore(lyssnaStartlage, hamtaStartlage, hamtaStartlage);
  const lugnStart = startlage !== "app";

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

  useEffect(() => {
    return kopplaAtterupptning(
      () => bbVy.get(),
      (f) => bbVy.subscribe(f),
      (api, state) => atterupptaMotorJobb(api, state as Parameters<typeof atterupptaMotorJobb>[1]),
    );
  }, []);

  return (
    <TooltipProvider delayDuration={200}>
    <div className={cn("flex min-h-screen bg-background", lugnStart && "flex-col")}>
      {lugnStart ? null : (
      <aside className="sticky top-0 flex h-screen w-[17.5rem] shrink-0 flex-col overflow-y-auto border-r border-border/70 bg-white max-lg:hidden">
        <Varumarke />
        <NavInnehall />
        <Sidfot />
      </aside>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        {lugnStart ? (
          <header className="flex items-center gap-3 px-6 py-6">
            <Varumarke />
          </header>
        ) : (
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
            <div className="text-[14px] font-semibold tracking-[0.14em] text-primary uppercase">{s.eyebrow}</div>
            <h1 className="truncate text-[36px] font-extrabold tracking-tight text-deep">{s.titel}</h1>
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
            ) : null}
          </div>
        </header>
        )}

        {lugnStart ? null : <Stegrad />}
        <div className={cn("px-5 pb-[6rem] sm:px-8", lugnStart && "px-4 sm:px-6")}>{children}</div>

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
