// The frame of every signed-out page: one continuous dark canvas.
// - `pitch` (the sign-in page): the pitch and the example call on the left,
//   the card floating on the right; phones stack pitch, card, call.
// - without it (No clinic, Can't connect, …): just the card, centred.
// Always this look, whatever the viewer's theme: it is the first impression.
import type { ReactNode } from "react";
import { Brand } from "@/components/app/brand";
import { PRODUCT_NAME } from "@/lib/product";
import { Backdrop } from "./backdrop";
import { glassMark } from "./glass";
import { LiveCall } from "./live-call";

function Pitch() {
  return (
    <section className="self-end lg:[grid-area:copy]">
      <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium text-teal-200 backdrop-blur">
        <span className="size-1.5 rounded-full bg-teal-300" />
        AI voice receptionist for clinics
      </p>
      <p className="mt-5 max-w-xl text-4xl leading-[1.08] font-semibold tracking-tight text-balance sm:text-5xl">
        Your clinic&apos;s receptionist,{" "}
        <span className="bg-gradient-to-r from-teal-200 via-emerald-200 to-cyan-200 bg-clip-text text-transparent">speaking Hindi.</span>
      </p>
      <p className="mt-5 max-w-lg text-base leading-relaxed text-pretty text-white/60 sm:text-lg">
        Patients book, move or cancel their visit just by talking. Your staff see every call and the day&apos;s diary here.
      </p>
    </section>
  );
}

export function AuthFrame({ children, pitch = false }: { children: ReactNode; pitch?: boolean }) {
  return (
    <div className="relative isolate flex min-h-screen flex-col overflow-hidden bg-[#041416] text-white">
      <Backdrop />
      <header className="mx-auto w-full max-w-6xl px-5 py-6 sm:px-8">
        <Brand size="lg" markClassName={glassMark} className="text-white" />
      </header>

      {pitch ? (
        <main className="mx-auto grid w-full max-w-6xl flex-1 gap-10 px-5 pb-12 sm:px-8 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-x-20 lg:gap-y-10 lg:[grid-template-areas:'copy_card'_'call_card'] lg:py-8">
          <Pitch />
          <div className="w-full max-w-[400px] justify-self-center lg:row-span-2 lg:self-center lg:[grid-area:card]">{children}</div>
          <LiveCall className="w-full max-w-lg self-start lg:[grid-area:call]" />
        </main>
      ) : (
        <main className="flex flex-1 items-center justify-center px-5 pb-16 sm:px-8">
          <div className="w-full max-w-[400px]">{children}</div>
        </main>
      )}

      <footer className="mx-auto w-full max-w-6xl px-5 py-6 text-xs text-white/40 sm:px-8">
        © {new Date().getFullYear()} {PRODUCT_NAME}
      </footer>
    </div>
  );
}
