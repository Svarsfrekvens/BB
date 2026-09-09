import { useState, useRef, useEffect, useSyncExternalStore } from "react";
import { MessageCircleQuestion, X, ArrowUp } from "lucide-react";
import { bbVy } from "@/lib/bb/vy";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type Rad = { vem: "du" | "app"; text: string };

const HALSNING: Rad = {
  vem: "app",
  text: "Hej! Skriv vad du vill göra – till exempel visa ekonomin eller hur är kundnära tiden?",
};

/** "Fråga appen": en liten kommandoruta. Tolkningen sker i logiklagret. */
export function FragaAppen() {
  const v = useSyncExternalStore(
    (f) => bbVy.subscribe(f),
    () => bbVy.get(),
    () => bbVy.get(),
  );
  const [oppen, setOppen] = useState(false);
  const [rader, setRader] = useState<Rad[]>([HALSNING]);
  const [text, setText] = useState("");
  const loggRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (loggRef.current) loggRef.current.scrollTop = loggRef.current.scrollHeight;
  }, [rader, oppen]);

  function skicka() {
    const fraga = text.trim();
    if (!fraga || !v.api) return;
    const svar = v.api.chatFraga(fraga);
    setText("");
    setRader((r) => [...r, { vem: "du", text: fraga }, ...(svar ? [{ vem: "app" as const, text: svar }] : [])]);
  }

  if (!oppen) {
    return (
      <Button
        variant="outline"
        size="sm"
        className="fixed right-5 bottom-5 z-30 bg-card px-3 text-[13px] opacity-90 shadow-lift-lg transition-opacity hover:opacity-100"
        onClick={() => setOppen(true)}
      >
        <MessageCircleQuestion /> Fråga appen
      </Button>
    );
  }

  return (
    <div className="fixed right-5 bottom-5 z-40 flex max-h-[70vh] w-[min(22rem,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-lift-lg">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <strong className="flex items-center gap-2 text-sm font-extrabold text-deep">
          <MessageCircleQuestion className="size-4 text-primary" /> Fråga appen
        </strong>
        <button
          type="button"
          aria-label="Stäng"
          className="grid size-7 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-deep"
          onClick={() => setOppen(false)}
        >
          <X className="size-4" />
        </button>
      </div>

      <div ref={loggRef} className="flex flex-1 flex-col gap-2 overflow-y-auto px-4 py-3">
        {rader.map((r, i) => (
          <div
            key={i}
            className={cn(
              "max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed",
              r.vem === "du"
                ? "self-end bg-primary text-primary-foreground"
                : "self-start bg-muted text-deep",
            )}
          >
            {r.text}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 border-t border-border p-3">
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") skicka();
          }}
          placeholder="Skriv vad du vill göra…"
          autoComplete="off"
          aria-label="Din fråga"
        />
        <Button size="icon" aria-label="Skicka" onClick={skicka}>
          <ArrowUp />
        </Button>
      </div>
    </div>
  );
}
