import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  EXTRA_RESURS_SLAG,
  tomExtraResurs,
  tolkaDatumlista,
  type ExtraResurs,
  type ExtraResursSlag,
} from "@/lib/bb/extraResurs";

const SLAG_TEXT: Record<ExtraResursSlag, string> = {
  vikarie: "Vikarie",
  extern: "Extern resurs",
  tillfallig: "Annan registrerad tillfällig resurs",
};

export function KompletteraResursDialog({
  open,
  onOpenChange,
  onSpara,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSpara: (r: ExtraResurs) => { ok: boolean; fel: string[] };
}) {
  const [form, setForm] = useState<ExtraResurs>(() => tomExtraResurs());
  const [datumText, setDatumText] = useState("");
  const [kompetensText, setKompetensText] = useState("");
  const [fel, setFel] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    setForm(tomExtraResurs());
    setDatumText("");
    setKompetensText("");
    setFel([]);
  }, [open]);

  const set = <K extends keyof ExtraResurs>(k: K, v: ExtraResurs[K]) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto" data-dialog="komplettera-resurs">
        <DialogHeader>
          <DialogTitle>Komplettera resurs</DialogTitle>
          <DialogDescription>
            BB har identifierat behovet. Du anger vilken faktisk resurs som finns tillgänglig. Inget fylls i automatiskt.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="extra-namn">Namn eller benämning</Label>
            <Input id="extra-namn" value={form.namn} onChange={(e) => set("namn", e.target.value)} placeholder="Extern jourresurs" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="extra-slag">Resurstyp</Label>
            <select
              id="extra-slag"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
              value={form.slag}
              onChange={(e) => set("slag", e.target.value as ExtraResursSlag)}
            >
              {EXTRA_RESURS_SLAG.map((s) => (
                <option key={s} value={s}>
                  {SLAG_TEXT[s]}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="extra-datum">Tillgängliga datum (ett per rad, ÅÅÅÅ-MM-DD)</Label>
            <Textarea
              id="extra-datum"
              value={datumText}
              onChange={(e) => {
                setDatumText(e.target.value);
                set("tillgangligaDatum", tolkaDatumlista(e.target.value));
              }}
              placeholder="2026-08-14"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="extra-from">Tillgänglig från</Label>
              <Input id="extra-from" value={form.tidigastStart} onChange={(e) => set("tidigastStart", e.target.value)} placeholder="23:00" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="extra-to">Tillgänglig till</Label>
              <Input id="extra-to" value={form.senastSlut} onChange={(e) => set("senastSlut", e.target.value)} placeholder="06:30" />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={form.jour} onCheckedChange={(v) => set("jour", v === true)} />
            Jourbehörighet
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={form.nattbehorig} onCheckedChange={(v) => set("nattbehorig", v === true)} />
            Nattbehörighet
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={form.delegering} onCheckedChange={(v) => set("delegering", v === true)} />
            Delegering
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={form.helg} onCheckedChange={(v) => set("helg", v === true)} />
            Helgtillgänglighet (endast de helgdatum du angett)
          </label>
          <div className="grid gap-1.5">
            <Label htmlFor="extra-komp">Kompetenser (kommaseparerat)</Label>
            <Input
              id="extra-komp"
              value={kompetensText}
              onChange={(e) => {
                setKompetensText(e.target.value);
                set(
                  "kompetenser",
                  e.target.value.split(",").map((x) => x.trim()).filter(Boolean),
                );
              }}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="extra-kostnad">Timkostnad (kr)</Label>
              <Input
                id="extra-kostnad"
                type="number"
                min={1}
                value={form.timkostnad ?? ""}
                onChange={(e) => set("timkostnad", e.target.value === "" ? null : Number(e.target.value))}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="extra-max">Max arbetstid (h), valfritt</Label>
              <Input
                id="extra-max"
                type="number"
                min={0}
                value={form.maxTimmar ?? ""}
                onChange={(e) => set("maxTimmar", e.target.value === "" ? null : Number(e.target.value))}
              />
            </div>
          </div>
          {fel.length ? (
            <ul className="list-disc pl-5 text-sm text-destructive">
              {fel.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          ) : null}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Avbryt
          </Button>
          <Button
            type="button"
            data-cta="spara-extra-resurs"
            onClick={() => {
              const r = { ...form, tillgangligaDatum: tolkaDatumlista(datumText) };
              const ut = onSpara(r);
              if (!ut.ok) setFel(ut.fel);
              else onOpenChange(false);
            }}
          >
            Spara
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function extraResursSammanfattning(r: ExtraResurs) {
  return [
    SLAG_TEXT[r.slag],
    r.jour ? "jour" : null,
    r.tillgangligaDatum.length ? `${r.tillgangligaDatum.length} datum` : "inga datum",
    r.timkostnad != null ? `${r.timkostnad} kr/h` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}
