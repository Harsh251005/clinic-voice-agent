"use client";
// Erase a staff test call: undoes everything it booked, moved or cancelled,
// then deletes its record and transcript. Asked twice: it can't be undone.
import { Eraser } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useEraseTestCall } from "@/lib/queries";

export function EraseTestCall({ clinicId, callId, changes, onErased }: {
  clinicId: number; callId: number; changes: number; onErased?: () => void;
}) {
  const erase = useEraseTestCall(clinicId);
  const what = changes
    ? "Every appointment it booked, moved or cancelled goes back to how it was, and its record and conversation are deleted."
    : "It changed no appointments. Its record and conversation are deleted.";
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" className="text-destructive hover:text-destructive" disabled={erase.isPending}>
          <Eraser /> Erase this test call
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Erase this test call?</AlertDialogTitle>
          <AlertDialogDescription>
            {what} This can&apos;t be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep it</AlertDialogCancel>
          <AlertDialogAction onClick={() => erase.mutate(callId, { onSuccess: () => onErased?.() })}
            className="bg-destructive text-white hover:bg-destructive/90">
            Yes, erase it
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
