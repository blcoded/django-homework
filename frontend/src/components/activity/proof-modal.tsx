"use client";

import * as React from "react";
import { Image as ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ProofModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  photoUrl: string | null;
}

export function ProofModal({ open, onOpenChange, title, photoUrl }: ProofModalProps) {
  if (!photoUrl) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]" data-testid="proof-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5 text-primary" />
            Verification Proof: {title}
          </DialogTitle>
          <DialogDescription>
            Roommate photo evidence submitted upon chore completion.
          </DialogDescription>
        </DialogHeader>

        <div className="py-2 flex items-center justify-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={photoUrl}
            alt={`Proof for ${title}`}
            data-testid="proof-modal-image"
            className="max-h-[350px] w-auto rounded-lg border object-contain shadow-sm"
          />
        </div>

        <DialogFooter>
          <Button type="button" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
