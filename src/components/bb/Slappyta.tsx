import { useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Dra-och-släpp-yta för Excel-filer. Bara utseende – filen skickas vidare. */
export function Slappyta({
  text,
  hjalp,
  onFil,
  onValj,
}: {
  text: string;
  hjalp: string;
  onFil: (f: File) => void;
  onValj: () => void;
}) {
  const [over, setOver] = useState(false);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFil(f);
      }}
      className={cn(
        "mt-4 flex flex-col items-center rounded-2xl border-2 border-dashed px-6 py-9 text-center transition-colors",
        over ? "border-primary bg-primary-soft" : "border-border bg-muted/40",
      )}
    >
      <span className="grid size-11 place-items-center rounded-xl bg-card text-primary shadow-sm">
        <Upload className="size-5" />
      </span>
      <strong className="mt-3 block text-sm font-extrabold text-deep">{text}</strong>
      <span className="mt-1 block text-xs text-muted-foreground">{hjalp}</span>
      <Button className="mt-4" variant="outline" onClick={onValj}>
        <Upload /> Välj fil
      </Button>
    </div>
  );
}
