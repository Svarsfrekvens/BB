import { useState } from "react";
import { AlertTriangle, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { jourPanelModell, lasPrecheck, lasSamtidighetsbrist, vakantaPassText, type JourDiagnos, type Samtidighetsbrist } from "@/lib/bb/jourDiagnos";
import type { ExtraResurs } from "@/lib/bb/extraResurs";
import type { VyApi, VyTillstand } from "@/lib/bb/vy";
import { korBemanningsbalans } from "@/lib/bb/korBemanningsbalans";
import { KompletteraResursDialog, extraResursSammanfattning } from "./KompletteraResursDialog";

export function ResursbristPanel({
  diagnos,
  visaKundbrist,
  extraResurser = [],
  samtidig = [],
  vakantaPass,
  onSparaExtra,
  onTaBortExtra,
  onSkapaBalansIgen,
}: {
  diagnos: JourDiagnos | null;
  visaKundbrist?: boolean;
  extraResurser?: ExtraResurs[];
  samtidig?: Samtidighetsbrist[];
  vakantaPass?: number | undefined;
  onSparaExtra?: (r: ExtraResurs) => { ok: boolean; fel: string[] };
  onTaBortExtra?: (id: string) => void;
  onSkapaBalansIgen?: () => void;
}) {
  const [dialog, setDialog] = useState(false);
  const m = jourPanelModell(diagnos);
  if (!m.visa) return null;
  return (
    <Card className="rounded-2xl border-warning/40 p-6 shadow-lift" data-resursbrist-panel="jour">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-bold tracking-widest text-warning uppercase">Resursbrist identifierad</p>
          <h3 className="mt-1 text-xl font-extrabold text-deep">{m.rubrik}</h3>
          <p className="mt-1 text-sm font-semibold text-deep">{m.ingress}</p>
          {m.jourBristRad ? (
            <p className="mt-2 text-sm font-semibold text-deep" data-jour-brist-rad="">
              {m.jourBristRad}
            </p>
          ) : null}
          <p className="mt-3 text-sm leading-relaxed text-deep" data-jour-huvudtext="">
            {m.huvud}
          </p>
          <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs text-muted-foreground">Jourpass som behöver bemannas</dt>
              <dd className="font-extrabold text-deep" data-jour-behov="">
                {m.jourpassBehov}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Möjliga med registrerad personal</dt>
              <dd className="font-extrabold text-deep" data-jour-coverable="">
                {m.mojligaMedRegistrerad ?? "–"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Ytterligare jourpass som krävs</dt>
              <dd className="font-extrabold text-deep" data-jour-external="">
                {m.ytterligareJourpass ?? "–"}
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-xs font-semibold text-muted-foreground">Bindande regler</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-deep">
            {m.bindandeRegler.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          {m.openFore ? (
            <p className="mt-3 text-sm text-deep" data-open-jour-fore="">
              <span className="font-semibold">Saknar namngiven resurs i Före-schema. </span>
              {m.openFore}
            </p>
          ) : null}
          {samtidig.length ? (
            <div className="mt-3" data-samtidighetsbrist="">
              <p className="text-sm font-semibold text-deep">{m.samtidighetIngress}</p>
              <ul className="mt-1 list-disc pl-5 text-sm text-deep">
                {samtidig.slice(0, 8).map((rad) => (
                  <li key={`${rad.date}-${rad.tidstext}`}>
                    {rad.tidstext}: behov {rad.need}, registrerade {rad.available}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {vakantaPassText(vakantaPass) ? (
            <p className="mt-3 text-sm text-deep" data-vakanta-pass-ej-personal="">
              {vakantaPassText(vakantaPass)}
            </p>
          ) : null}
          {m.datumVarning ? (
            <p className="mt-3 text-sm text-muted-foreground" data-jour-datum-osakra="">
              {m.datumVarning}
            </p>
          ) : null}
          <div className="mt-4 space-y-2 rounded-xl bg-muted/50 p-3 text-sm">
            <p data-problemtyp="hard-jour">
              <span className="font-semibold">Obligatorisk bemanningsbrist: </span>
              {m.hardJourText}
            </p>
            {visaKundbrist ? (
              <p data-problemtyp="soft-customer">
                <span className="font-semibold">Otäckt kundbehov: </span>
                {m.kundbristText}
              </p>
            ) : null}
          </div>
          {extraResurser.length ? (
            <ul className="mt-4 space-y-2" data-extra-resurser="">
              {extraResurser.map((r) => (
                <li key={r.id} className="flex items-start justify-between gap-2 rounded-xl border border-border px-3 py-2 text-sm">
                  <div>
                    <p className="font-semibold text-deep">{r.namn}</p>
                    <p className="text-xs text-muted-foreground">{extraResursSammanfattning(r)}</p>
                  </div>
                  <Button type="button" variant="ghost" size="sm" onClick={() => onTaBortExtra?.(r.id)}>
                    Ta bort
                  </Button>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => setDialog(true)} data-cta="komplettera-resurs">
              <Users /> {m.kompletteraCta}
            </Button>
            {extraResurser.length && onSkapaBalansIgen ? (
              <Button type="button" onClick={onSkapaBalansIgen} data-cta="skapa-balans-igen">
                Skapa balans igen
              </Button>
            ) : null}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{m.kompletteraHjalp}</p>
        </div>
      </div>
      <KompletteraResursDialog
        open={dialog}
        onOpenChange={setDialog}
        onSpara={(r) => onSparaExtra?.(r) || { ok: false, fel: ["Kan inte spara."] }}
      />
    </Card>
  );
}

export function resursbristProps(api: VyApi, state?: VyTillstand | Record<string, unknown> | null) {
  const diag = (api.motorResultat() as { resourceDiagnostics?: unknown } | null)?.resourceDiagnostics;
  return {
    extraResurser: api.extraResurser?.() || [],
    samtidig: lasSamtidighetsbrist(lasPrecheck(diag)),
    vakantaPass: api.underlag()?.schema?.vakantaPass,
    onSparaExtra: (r: ExtraResurs) => api.sparaExtraResurs?.(r) || { ok: false, fel: ["Kan inte spara."] },
    onTaBortExtra: (id: string) => api.taBortExtraResurs?.(id),
    onSkapaBalansIgen: () => {
      void korBemanningsbalans({ api, state: state ?? null });
    },
  };
}
