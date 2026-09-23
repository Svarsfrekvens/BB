import { ArrowRight, AlertTriangle, CheckCircle2, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { VyProps } from "@/lib/bb/vy";
import { readinessFranApi } from "@/lib/bb/vcFlode";
import { korBemanningsbalans } from "@/lib/bb/korBemanningsbalans";
import { fmtH } from "@/lib/bb/vy";
import { BalansPagar } from "./BalansPagar";

const DOLDA = new Set(["kontaktpersonstid", "samverkan_kund"]);

export function Forutsattningar({ api, state }: VyProps) {
  const u = api.underlag();
  const r = readinessFranApi(api);
  const koll = api.underlagKoll();
  const aktiviteter = api.planAktiviteter().filter((a) => !DOLDA.has(a.id) && !DOLDA.has(a.aktivitetstyp) && a.aktiv);
  const blocker = r.blockingReasons;
  const jobb = api.motorJobb?.();
  const pagaende = Boolean(jobb?.id && jobb.phase !== "completed" && jobb.phase !== "failed");

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <p className="text-[14px] font-semibold tracking-[0.14em] text-primary uppercase">Granska</p>
        <h2 className="mt-2 text-[32px] font-extrabold tracking-tight text-deep">Förutsättningar för balans</h2>
        <p className="mt-3 text-[16px] leading-relaxed text-muted-foreground">
          Kontrollera underlaget innan du skapar balans. Blockerande brister måste åtgärdas först.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="rounded-[24px] p-6 shadow-lift">
          <h3 className="text-[18px] font-extrabold text-deep">Kundunderlag</h3>
          <p className="mt-2 text-[16px] text-muted-foreground">
            {u.sekoia
              ? `${u.sekoia.insatser} insatser · ${fmtH(u.sekoia.timmar)} · ${u.godkand.kund ? "godkänt" : "ej godkänt"}`
              : "Saknas"}
          </p>
        </Card>
        <Card className="rounded-[24px] p-6 shadow-lift">
          <h3 className="text-[18px] font-extrabold text-deep">Medarbetare</h3>
          <p className="mt-2 text-[16px] text-muted-foreground">
            {u.schema
              ? `${u.schema.medarbetare} medarbetare · ${u.schema.pass} pass`
              : "Saknas"}
          </p>
        </Card>
        <Card className="rounded-[24px] p-6 shadow-lift">
          <h3 className="text-[18px] font-extrabold text-deep">Villkor</h3>
          <p className="mt-2 text-[16px] text-muted-foreground">
            {koll.schemaGodkand ? "Medarbetare & villkor godkända" : "Villkor är inte godkända"} · {koll.villkor} individuella villkor
          </p>
        </Card>
        <Card className="rounded-[24px] p-6 shadow-lift">
          <h3 className="text-[18px] font-extrabold text-deep">Planeringsaktiviteter</h3>
          <p className="mt-2 text-[16px] text-muted-foreground">
            {aktiviteter.length ? aktiviteter.map((a) => a.namn).join(", ") : "Inga tillval aktiva"}
          </p>
        </Card>
      </div>

      {blocker.length ? (
        <Card className="rounded-[24px] border-warning/40 bg-warning-soft p-6">
          <h3 className="flex items-center gap-2 text-[18px] font-extrabold text-deep">
            <AlertTriangle className="size-5" /> Blockerande brister
          </h3>
          <ul className="mt-3 space-y-1 text-[16px] text-deep">
            {blocker.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </Card>
      ) : (
        <p className="flex items-center gap-2 text-[16px] font-semibold text-deep">
          <CheckCircle2 className="size-5 text-ok" /> Underlaget räcker för att skapa balans.
        </p>
      )}

      <Card className="rounded-[28px] border-transparent bg-gradient-to-br from-white to-primary-soft/35 p-10 shadow-lift-lg">
        <h2 className="text-[28px] font-extrabold text-deep">Skapa balans</h2>
        <p className="mt-3 text-[16px] text-muted-foreground">
          {pagaende ? "Beräkningen pågår." : "Motorn tar fram ett förslag utifrån underlaget."}
        </p>
        <Button
          className="mt-7 h-14 rounded-2xl px-8 text-[16px]"
          size="lg"
          data-cta="skapa-bemanningsbalans"
          disabled={!r.ready || pagaende}
          onClick={() => void korBemanningsbalans({ api, state })}
        >
          <Sparkles /> {pagaende ? "Skapar balans…" : "Skapa balans"}
        </Button>
        <Button variant="outline" className="mt-3 ml-3" onClick={() => api.setTab("planering")}>
          <ArrowRight /> Tillbaka till planering
        </Button>
        <div className="mt-6">
          <BalansPagar job={jobb} />
        </div>
      </Card>
    </div>
  );
}
