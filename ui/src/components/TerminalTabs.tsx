/**
 * Terminal Tabs Component
 *
 * Manages multiple terminal tabs with add, rename, and close functionality.
 * Supports inline rename via double-click and context menu.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { Plus, X } from "lucide-react";
import type { TerminalInfo } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface TerminalTabsProps {
  terminals: TerminalInfo[];
  activeTerminalId: string | null;
  onSelect: (terminalId: string) => void;
  onCreate: () => void;
  onRename: (terminalId: string, newName: string) => void;
  onClose: (terminalId: string) => void;
}

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  terminalId: string | null;
}

export function TerminalTabs({
  terminals,
  activeTerminalId,
  onSelect,
  onCreate,
  onRename,
  onClose,
}: TerminalTabsProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    terminalId: null,
  });
  const inputRef = useRef<HTMLInputElement>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  // Focus input when editing starts
  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  // Close context menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        contextMenuRef.current &&
        !contextMenuRef.current.contains(e.target as Node)
      ) {
        setContextMenu((prev) => ({ ...prev, visible: false }));
      }
    };

    if (contextMenu.visible) {
      document.addEventListener("mousedown", handleClickOutside);
      return () =>
        document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [contextMenu.visible]);

  // Start editing a terminal name
  const startEditing = useCallback((terminal: TerminalInfo) => {
    setEditingId(terminal.id);
    setEditValue(terminal.name);
    setContextMenu((prev) => ({ ...prev, visible: false }));
  }, []);

  // Handle edit submission
  const submitEdit = useCallback(() => {
    if (editingId && editValue.trim()) {
      onRename(editingId, editValue.trim());
    }
    setEditingId(null);
    setEditValue("");
  }, [editingId, editValue, onRename]);

  // Cancel editing
  const cancelEdit = useCallback(() => {
    setEditingId(null);
    setEditValue("");
  }, []);

  // Handle key events during editing
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        submitEdit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        cancelEdit();
      }
    },
    [submitEdit, cancelEdit],
  );

  // Handle double-click to start editing
  const handleDoubleClick = useCallback(
    (terminal: TerminalInfo) => {
      startEditing(terminal);
    },
    [startEditing],
  );

  // Handle context menu
  const handleContextMenu = useCallback(
    (e: React.MouseEvent, terminalId: string) => {
      e.preventDefault();
      setContextMenu({
        visible: true,
        x: e.clientX,
        y: e.clientY,
        terminalId,
      });
    },
    [],
  );

  // Handle context menu actions
  const handleContextMenuRename = useCallback(() => {
    if (contextMenu.terminalId) {
      const terminal = terminals.find((t) => t.id === contextMenu.terminalId);
      if (terminal) {
        startEditing(terminal);
      }
    }
  }, [contextMenu.terminalId, terminals, startEditing]);

  const handleContextMenuClose = useCallback(() => {
    if (contextMenu.terminalId) {
      onClose(contextMenu.terminalId);
    }
    setContextMenu((prev) => ({ ...prev, visible: false }));
  }, [contextMenu.terminalId, onClose]);

  // Handle tab close with confirmation if needed
  const handleClose = useCallback(
    (e: React.MouseEvent, terminalId: string) => {
      e.stopPropagation();
      onClose(terminalId);
    },
    [onClose],
  );

  return (
    <div className="flex items-center gap-1 px-2 py-1 bg-zinc-900 border-b border-border overflow-x-auto">
      {/* Terminal tabs */}
      {terminals.map((terminal) => (
        <div
          key={terminal.id}
          className={`
            group flex items-center gap-1 px-3 py-1 rounded cursor-pointer
            transition-colors duration-100 select-none min-w-0
            ${
              activeTerminalId === terminal.id
                ? "bg-primary text-primary-foreground"
                : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
            }
          `}
          onClick={() => onSelect(terminal.id)}
          onDoubleClick={() => handleDoubleClick(terminal)}
          onContextMenu={(e) => handleContextMenu(e, terminal.id)}
        >
          {editingId === terminal.id ? (
            <Input
              ref={inputRef}
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={submitEdit}
              onKeyDown={handleKeyDown}
              className="h-6 px-1 py-0 text-sm font-mono w-24"
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span className="text-sm font-mono truncate max-w-[120px]">
              {terminal.name}
            </span>
          )}

          {/* Close button */}
          {terminals.length > 1 && (
            <button
              onClick={(e) => handleClose(e, terminal.id)}
              className={`
                p-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity
                ${
                  activeTerminalId === terminal.id
                    ? "hover:bg-black/20"
                    : "hover:bg-white/20"
                }
              `}
              title="Close terminal"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      ))}

      {/* Add new terminal button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={onCreate}
        className="h-8 w-8 bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
        title="New terminal"
      >
        <Plus className="w-4 h-4" />
      </Button>

      {/* Context menu */}
      {contextMenu.visible && (
        <div
          ref={contextMenuRef}
          className="fixed z-50 bg-popover border border-border rounded-md py-1 min-w-[120px] shadow-md"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button
            onClick={handleContextMenuRename}
            className="w-full px-3 py-1.5 text-left text-sm font-mono hover:bg-accent transition-colors"
          >
            Rename
          </button>
          {terminals.length > 1 && (
            <button
              onClick={handleContextMenuClose}
              className="w-full px-3 py-1.5 text-left text-sm font-mono text-destructive hover:bg-destructive hover:text-destructive-foreground transition-colors"
            >
              Close
            </button>
          )}
        </div>
      )}
    </div>
  );
}
