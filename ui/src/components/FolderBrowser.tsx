/**
 * Folder Browser Component
 *
 * Server-side filesystem browser for selecting project directories.
 * Cross-platform support for Windows, macOS, and Linux.
 */

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Folder,
  FolderOpen,
  ChevronRight,
  HardDrive,
  Loader2,
  AlertCircle,
  FolderPlus,
  ArrowLeft,
} from "lucide-react";
import * as api from "../lib/api";
import type { DirectoryEntry, DriveInfo } from "../lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";

interface FolderBrowserProps {
  onSelect: (path: string) => void;
  onCancel: () => void;
  initialPath?: string;
}

export function FolderBrowser({
  onSelect,
  onCancel,
  initialPath,
}: FolderBrowserProps) {
  const [currentPath, setCurrentPath] = useState<string | undefined>(
    initialPath,
  );
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  // Fetch directory listing
  const {
    data: directoryData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["filesystem", "list", currentPath],
    queryFn: () => api.listDirectory(currentPath),
  });

  // Update selected path when directory changes
  useEffect(() => {
    if (directoryData?.current_path) {
      setSelectedPath(directoryData.current_path);
    }
  }, [directoryData?.current_path]);

  const handleNavigate = (path: string) => {
    setCurrentPath(path);
    setSelectedPath(path);
    setIsCreatingFolder(false);
    setNewFolderName("");
    setCreateError(null);
  };

  const handleNavigateUp = () => {
    if (directoryData?.parent_path) {
      handleNavigate(directoryData.parent_path);
    }
  };

  const handleDriveSelect = (drive: DriveInfo) => {
    handleNavigate(`${drive.letter}:/`);
  };

  const handleEntryClick = (entry: DirectoryEntry) => {
    if (entry.is_directory) {
      handleNavigate(entry.path);
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) {
      setCreateError("Folder name is required");
      return;
    }

    // Basic validation
    if (!/^[a-zA-Z0-9_\-. ]+$/.test(newFolderName)) {
      setCreateError("Invalid folder name");
      return;
    }

    const newPath = `${directoryData?.current_path}/${newFolderName.trim()}`;

    try {
      await api.createDirectory(newPath);
      // Refresh the directory listing
      await refetch();
      // Navigate to the new folder
      handleNavigate(newPath);
    } catch (err) {
      setCreateError(
        err instanceof Error ? err.message : "Failed to create folder",
      );
    }
  };

  const handleSelect = () => {
    if (selectedPath) {
      onSelect(selectedPath);
    }
  };

  // Parse breadcrumb segments from path
  const getBreadcrumbs = (path: string): { name: string; path: string }[] => {
    if (!path) return [];

    const segments: { name: string; path: string }[] = [];

    // Handle Windows drive letters
    if (/^[A-Za-z]:/.test(path)) {
      const drive = path.slice(0, 2);
      segments.push({ name: drive, path: `${drive}/` });
      path = path.slice(3);
    } else if (path.startsWith("/")) {
      segments.push({ name: "/", path: "/" });
      path = path.slice(1);
    }

    // Split remaining path
    const parts = path.split("/").filter(Boolean);
    let currentPath = segments.length > 0 ? segments[0].path : "";

    for (const part of parts) {
      currentPath = currentPath.endsWith("/")
        ? currentPath + part
        : currentPath + "/" + part;
      segments.push({ name: part, path: currentPath });
    }

    return segments;
  };

  const breadcrumbs = directoryData?.current_path
    ? getBreadcrumbs(directoryData.current_path)
    : [];

  return (
    <div className="flex flex-col h-full max-h-[70vh]">
      {/* Header with breadcrumb navigation */}
      <div className="flex-shrink-0 p-4 border-b bg-card">
        <div className="flex items-center gap-2 mb-3">
          <Folder size={20} className="text-primary" />
          <span className="font-semibold">Select Project Folder</span>
        </div>

        {/* Breadcrumb navigation */}
        <div className="flex items-center gap-1 flex-wrap text-sm">
          {directoryData?.parent_path && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={handleNavigateUp}
              title="Go up"
            >
              <ArrowLeft size={16} />
            </Button>
          )}

          {breadcrumbs.map((crumb, index) => (
            <div key={crumb.path} className="flex items-center">
              {index > 0 && (
                <ChevronRight
                  size={14}
                  className="text-muted-foreground mx-1"
                />
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleNavigate(crumb.path)}
                className={
                  index === breadcrumbs.length - 1 ? "font-semibold" : ""
                }
              >
                {crumb.name}
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Drive selector (Windows only) */}
      {directoryData?.drives && directoryData.drives.length > 0 && (
        <div className="flex-shrink-0 p-3 border-b bg-muted/50">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-muted-foreground">
              Drives:
            </span>
            {directoryData.drives.map((drive) => (
              <Button
                key={drive.letter}
                variant={
                  currentPath?.startsWith(drive.letter) ? "default" : "outline"
                }
                size="sm"
                onClick={() => handleDriveSelect(drive)}
              >
                <HardDrive size={14} />
                {drive.letter}: {drive.label && `(${drive.label})`}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Directory listing */}
      <div className="flex-1 min-h-0 overflow-y-auto bg-card">
        <div className="p-2">
          {isLoading ? (
            <div className="flex items-center justify-center p-8">
              <Loader2 size={24} className="animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="p-4 text-center">
              <AlertCircle
                size={32}
                className="mx-auto mb-2 text-destructive"
              />
              <p className="text-destructive">
                {error instanceof Error
                  ? error.message
                  : "Failed to load directory"}
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                className="mt-2"
              >
                Retry
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-1">
              {/* Directory entries - only show directories */}
              {directoryData?.entries
                .filter((entry) => entry.is_directory)
                .map((entry) => (
                  <button
                    key={entry.path}
                    onClick={() => handleEntryClick(entry)}
                    onDoubleClick={() => handleNavigate(entry.path)}
                    className={`
                      w-full text-left p-2 rounded-md
                      flex items-center gap-2
                      hover:bg-muted
                      border-2 border-transparent transition-colors
                      ${selectedPath === entry.path ? "bg-primary/10 border-primary" : ""}
                    `}
                  >
                    {selectedPath === entry.path ? (
                      <FolderOpen
                        size={18}
                        className="text-primary flex-shrink-0"
                      />
                    ) : (
                      <Folder
                        size={18}
                        className="text-muted-foreground flex-shrink-0"
                      />
                    )}
                    <span className="truncate flex-1">{entry.name}</span>
                    {entry.has_children && (
                      <ChevronRight
                        size={14}
                        className="ml-auto text-muted-foreground flex-shrink-0"
                      />
                    )}
                  </button>
                ))}

              {/* Empty state */}
              {directoryData?.entries.filter((e) => e.is_directory).length ===
                0 && (
                <div className="p-4 text-center text-muted-foreground">
                  <Folder size={32} className="mx-auto mb-2 opacity-50" />
                  <p>No subfolders</p>
                  <p className="text-sm">
                    You can create a new folder or select this directory.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* New folder creation */}
          {isCreatingFolder && (
            <Card className="mt-2">
              <CardContent className="p-3">
                <div className="flex items-center gap-2">
                  <FolderPlus size={18} className="text-primary" />
                  <Input
                    type="text"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    placeholder="New folder name"
                    className="flex-1"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleCreateFolder();
                      if (e.key === "Escape") {
                        setIsCreatingFolder(false);
                        setNewFolderName("");
                        setCreateError(null);
                      }
                    }}
                  />
                  <Button onClick={handleCreateFolder} size="sm">
                    Create
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setIsCreatingFolder(false);
                      setNewFolderName("");
                      setCreateError(null);
                    }}
                  >
                    Cancel
                  </Button>
                </div>
                {createError && (
                  <p className="text-sm text-destructive mt-1">{createError}</p>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Footer with selected path and actions */}
      <div className="flex-shrink-0 p-4 border-t bg-card">
        {/* Selected path display */}
        <Card className="mb-3">
          <CardContent className="p-2">
            <div className="text-xs text-muted-foreground mb-1">
              Selected path:
            </div>
            <div className="font-mono text-sm truncate">
              {selectedPath || "No folder selected"}
            </div>
            {selectedPath && (
              <div className="text-xs text-muted-foreground mt-2 italic">
                This folder will contain all project files
              </div>
            )}
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            onClick={() => setIsCreatingFolder(true)}
            disabled={isCreatingFolder}
          >
            <FolderPlus size={16} />
            New Folder
          </Button>

          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button onClick={handleSelect} disabled={!selectedPath}>
              Select This Folder
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
