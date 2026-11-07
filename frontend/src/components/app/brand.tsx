import { useId } from "react";
import { PRODUCT_NAME } from "@/lib/product";
import { cn } from "@/lib/utils";

/** The glyph: a speech bubble with three voice bars cut out of it, the
 *  receptionist that talks. Drawn in currentColor; the bars show the tile
 *  behind. src/app/icon.svg is the same drawing for the browser tab. */
export function BrandGlyph({ className }: { className?: string }) {
  const cut = useId(); // a mask id per instance: several marks on one page
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <mask id={cut}>
        <path fill="white" d="M6 3.5h12A3.5 3.5 0 0 1 21.5 7v7.5A3.5 3.5 0 0 1 18 18h-6.2l-4.6 3.6a.7.7 0 0 1-1.2-.55V18A3.5 3.5 0 0 1 2.5 14.5V7A3.5 3.5 0 0 1 6 3.5z" />
        <g stroke="black" strokeWidth="2.1" strokeLinecap="round">
          <path d="M8 9.6v2.3M12 7.6v6.3M16 9v3.5" />
        </g>
      </mask>
      <rect width="24" height="24" fill="currentColor" mask={`url(#${cut})`} />
    </svg>
  );
}

/** The mark: the glyph on a rounded tile. Tile colour comes from className. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground shadow-sm", className)}>
      <BrandGlyph className="size-[62%]" />
    </span>
  );
}

export function Brand({ className, markClassName, size = "md" }: {
  className?: string; markClassName?: string; size?: "md" | "lg";
}) {
  const lg = size === "lg";
  return (
    <div className={cn("flex items-center", lg ? "gap-3" : "gap-2.5", className)}>
      <BrandMark className={cn(lg && "size-11 rounded-xl", markClassName)} />
      <span className={cn("font-semibold tracking-tight", lg ? "text-[22px]" : "text-base")}>{PRODUCT_NAME}</span>
    </div>
  );
}
