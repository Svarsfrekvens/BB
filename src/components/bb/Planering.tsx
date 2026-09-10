import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { VyApi } from "@/lib/bb/vy";

/** Kompakt sektion för sparade planeringsaktiviteter och kontaktpersoner. */
export function Planering({ api }: { api: VyApi }) {
  const [visa, setVisa] = useState(false);
  const [visaKontakt, setVisaKontakt] = useState(false);
  const aktiviteter = api.planAktiviteter();
  const aktiva = aktiviteter.filter((a) => a.aktiv);
  const koll = api.underlagKoll();
  const med = api.medarbetare();
  const kunder = api.kunderForKontakt();
  const kontakt = api.kontaktpersoner();

  return (
    <div className="space-y-4 px-6 py-5">
      <div>
        <strong className="block text-sm font-extrabold text-deep">Planeringsaktiviteter</strong>
        <p className="mt-1 text-[13px] text-muted-foreground">
          {aktiva.length ? `${aktiva.length} planeringsaktiviteter aktiva` : "Inga tillval aktiva – samma nästa period tills du ändrar."}
        </p>
        <Button variant="outline" size="sm" className="mt-2" onClick={() => setVisa((v) => !v)}>
          {visa ? "Dölj" : "Visa och ändra"}
        </Button>
        {visa ? (
          <ul className="mt-3 space-y-2 text-sm">
            {aktiviteter.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-2">
                <input
                  type="checkbox"
                  checked={a.aktiv}
                  onChange={(e) => api.setPlanAktivitet(a.id, "aktiv", e.target.checked)}
                />
                <span className="flex-1 text-deep">
                  {a.aktiv ? "✓ " : ""}
                  {a.namn}
                  {a.aktiv
                    ? ` – ${a.omfattning} ${a.enhet === "timmar" ? "h" : "min"} · ${a.tidstyp === "separat_tid" ? "separat tid" : "inom pass"}`
                    : ""}
                </span>
                {a.aktiv ? (
                  <>
                    <input
                      className="h-8 w-16 rounded border border-input px-2 text-sm tabular-nums"
                      value={String(a.omfattning)}
                      onChange={(e) => api.setPlanAktivitet(a.id, "omfattning", Number(e.target.value) || 0)}
                    />
                    <select
                      className="h-8 rounded border border-input px-1 text-[12px]"
                      value={a.tidstyp || "inom_pass"}
                      onChange={(e) => api.setPlanAktivitet(a.id, "tidstyp", e.target.value)}
                    >
                      <option value="inom_pass">Inom pass</option>
                      <option value="separat_tid">Separat tid</option>
                    </select>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        ) : aktiva.length ? (
          <ul className="mt-2 space-y-1 text-[13px] text-deep">
            {aktiva.slice(0, 8).map((a) => (
              <li key={a.id}>
                ✓ {a.namn} – {a.omfattning} {a.enhet === "timmar" ? "h" : "min"}
                {a.tidstyp === "separat_tid" ? " · separat tid" : " · inom pass"}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div>
        <strong className="block text-sm font-extrabold text-deep">Kontaktperson</strong>
        <p className="mt-1 text-[13px] text-muted-foreground">
          {koll.kontakt} av {kunder.length} kunder har kontaktperson
          {koll.saknarKontakt.length ? ` · ${koll.saknarKontakt.length} saknas` : ""}
        </p>
        <Button variant="outline" size="sm" className="mt-2" onClick={() => setVisaKontakt((v) => !v)}>
          {visaKontakt ? "Dölj" : "Koppla kund → medarbetare"}
        </Button>
        {visaKontakt ? (
          <ul className="mt-3 space-y-2 text-sm">
            {kunder.map((k) => (
              <li key={k} className="flex flex-wrap items-center gap-2">
                <span className="min-w-40 font-semibold text-deep">{k}</span>
                <select
                  className="h-9 rounded-lg border border-input bg-background px-2"
                  value={kontakt[k] || ""}
                  onChange={(e) => api.setKontaktperson(k, e.target.value)}
                >
                  <option value="">Välj</option>
                  {med.map((m) => (
                    <option key={m.namn} value={m.namn}>
                      {m.namn}
                    </option>
                  ))}
                </select>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="rounded-xl bg-muted/60 p-4 text-sm text-deep">
        <strong className="block font-extrabold">Checklista underlag</strong>
        <ul className="mt-2 space-y-1 text-[13px]">
          <li>{koll.kundGodkand ? "✓" : "○"} Kundbehov {koll.kundGodkand ? "godkänt" : "ej godkänt"}</li>
          <li>{koll.schemaGodkand ? "✓" : "○"} Schema {koll.schemaGodkand ? "godkänt" : "ej godkänt"}</li>
          <li>{koll.aktiviteter ? "✓" : "○"} {koll.aktiviteter} planeringsaktiviteter aktiva</li>
          <li>{koll.medarbetare ? "✓" : "○"} {koll.medarbetare} medarbetare</li>
          <li>{koll.villkor ? "✓" : "○"} {koll.villkor} individuella villkor aktiva</li>
          <li>{koll.kontakt ? "✓" : "○"} {koll.kontakt} kunder har kontaktperson</li>
        </ul>
        {koll.saknarKontakt.length ? (
          <p className="mt-2 text-[13px] font-semibold text-destructive">
            {koll.saknarKontakt.length} kund{koll.saknarKontakt.length > 1 ? "er" : ""} saknar kontaktperson för aktiverad avstämning.
          </p>
        ) : null}
      </div>
    </div>
  );
}
