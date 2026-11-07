"use client";
// "Sign out of ClinicDesk?": asked before signing out, so a stray click in
// the account menu never drops someone out in the middle of the day.
import { useState } from "react";
import { Loader2, LogOut } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogMedia, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { PRODUCT_NAME } from "@/lib/product";
import { signOut } from "./gates";

export function SignOutDialog({ email, open, onOpenChange }: { email: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [leaving, setLeaving] = useState(false);
  return (
    <AlertDialog open={open} onOpenChange={(next) => { if (!leaving) onOpenChange(next); }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogMedia className="bg-primary/10 text-primary"><LogOut /></AlertDialogMedia>
          <AlertDialogTitle>Sign out of {PRODUCT_NAME}?</AlertDialogTitle>
          <AlertDialogDescription>
            You&apos;re signed in as <span className="font-medium text-foreground">{email}</span>. To come back, sign in
            again with this Google account.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={leaving}>Stay signed in</AlertDialogCancel>
          <AlertDialogAction
            disabled={leaving}
            onClick={(e) => {
              e.preventDefault(); // keep the dialog open while signing out
              setLeaving(true);
              void signOut();
            }}
          >
            {leaving ? <><Loader2 className="animate-spin" /> Signing out…</> : "Sign out"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
