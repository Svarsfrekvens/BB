import { HelpCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** Ett litet frågetecken som förklarar ett begrepp i en mening. */
export function Hjalp({ text, etikett }: { text: string; etikett: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={`Vad betyder ${etikett}?`}
          className="inline-grid size-5 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-deep"
        >
          <HelpCircle className="size-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-64 text-[13px] leading-snug">{text}</TooltipContent>
    </Tooltip>
  );
}
