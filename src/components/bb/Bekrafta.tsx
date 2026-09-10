import { useState, type ReactNode } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

/** Bekräftelseruta för åtgärder som inte ska ske av misstag.
 *  Enter bekräftar, Esc stänger (Dialog sköter Esc). */
export function BekraftaDialog({
  open,
  onOpenChange,
  rubrik,
  text,
  bekraftaText = "Ta bort",
  onBekrafta,
  extraText,
  onExtra,
  ton = "destructive",
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  rubrik: string;
  text: ReactNode;
  bekraftaText?: string;
  onBekrafta: () => void;
  extraText?: string;
  onExtra?: () => void;
  ton?: "destructive" | "default";
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-md rounded-2xl"
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            onOpenChange(false);
            onBekrafta();
          }
        }}
      >
        <DialogHeader>
          <DialogTitle className="text-xl font-extrabold tracking-tight text-deep">{rubrik}</DialogTitle>
          <DialogDescription className="text-sm leading-relaxed">{text}</DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex-wrap gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Avbryt
          </Button>
          {extraText && onExtra ? (
            <Button variant="outline" onClick={() => onExtra()}>
              {extraText}
            </Button>
          ) : null}
          <Button variant={ton === "destructive" ? "destructive" : "default"} autoFocus onClick={() => { onOpenChange(false); onBekrafta(); }}>
            {bekraftaText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Enkelt tillstånd för en bekräftelse som gäller ett namngivet objekt. */
export function useBekrafta<T>() {
  const [mal, setMal] = useState<T | null>(null);
  return { mal, fraga: setMal, stang: () => setMal(null), open: mal != null };
}
