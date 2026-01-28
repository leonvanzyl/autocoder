/**
 * Floating Action Button for toggling the Assistant panel
 */

import { MessageCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface AssistantFABProps {
  onClick: () => void;
  isOpen: boolean;
}

export function AssistantFAB({ onClick, isOpen }: AssistantFABProps) {
  return (
    <Button
      onClick={onClick}
      size="icon"
      className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0.5"
      title={isOpen ? "Close Assistant (Press A)" : "Open Assistant (Press A)"}
      aria-label={isOpen ? "Close Assistant" : "Open Assistant"}
    >
      {isOpen ? <X size={24} /> : <MessageCircle size={24} />}
    </Button>
  );
}
