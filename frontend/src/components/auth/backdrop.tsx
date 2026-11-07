// The canvas behind every signed-out page: deep teal ink, slow-drifting
// light, and a fine grid that fades out toward the edges. Never stops moving,
// never asks for attention (motion-safe).
export function Backdrop() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden bg-[#041416]">
      <div className="absolute -top-[20%] -left-[10%] size-[55vw] rounded-full bg-teal-500/20 blur-[120px] motion-safe:animate-drift" />
      <div className="absolute top-[30%] -right-[15%] size-[45vw] rounded-full bg-cyan-500/10 blur-[120px] motion-safe:animate-drift motion-safe:direction-alternate-reverse" />
      <div className="absolute -bottom-[25%] left-[25%] size-[40vw] rounded-full bg-emerald-500/10 blur-[120px] motion-safe:animate-drift [animation-duration:30s]" />
      <div className="absolute inset-0 opacity-[0.06] [background-image:linear-gradient(white_1px,transparent_1px),linear-gradient(90deg,white_1px,transparent_1px)] [background-size:56px_56px] [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_75%)]" />
    </div>
  );
}
