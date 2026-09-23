import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export type TomtAtgard = {
  text: string;
  onClick: () => void;
  ikon?: LucideIcon;
  variant?: "default" | "outline";
};

/** Ett tomt läge som visar vad man gör härnäst – samma form överallt. */
export function TomtLage({
  ikon: Ikon,
  rubrik,
  text,
  atgarder = [],
}: {
  ikon: LucideIcon;
  rubrik: string;
  text: string;
  atgarder?: TomtAtgard[];
}) {
  return (
    <Card className="mx-auto max-w-xl rounded-[28px] p-10 text-center shadow-lift">
      <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-primary-soft text-primary">
        <Ikon className="size-6" />
      </div>
      <h2 className="mt-4 text-[26px] font-extrabold text-deep">{rubrik}</h2>
      <p className="mx-auto mt-3 max-w-md text-base leading-relaxed text-muted-foreground">{text}</p>
      {atgarder.length ? (
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {atgarder.map((a) => {
            const AIkon = a.ikon;
            return (
              <Button key={a.text} variant={a.variant ?? "default"} onClick={a.onClick}>
                {AIkon ? <AIkon /> : null} {a.text}
              </Button>
            );
          })}
        </div>
      ) : null}
    </Card>
  );
}
