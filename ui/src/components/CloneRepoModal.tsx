import { useEffect, useState, type FormEvent } from "react";
import { GitBranch, Loader2 } from "lucide-react";
import { useCloneProjectRepository } from "../hooks/useProjects";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface CloneRepoModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectName: string | null;
}

export function CloneRepoModal({ isOpen, onClose, projectName }: CloneRepoModalProps) {
  const cloneRepo = useCloneProjectRepository(projectName);
  const [repoUrl, setRepoUrl] = useState("");
  const [targetDir, setTargetDir] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setRepoUrl("");
      setTargetDir("");
      setError(null);
      setSuccessMessage(null);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const handleClose = () => {
    if (cloneRepo.isPending) {
      return;
    }
    onClose();
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!projectName) {
      setError("Select a project first");
      return;
    }

    const trimmedUrl = repoUrl.trim();
    if (!trimmedUrl) {
      setError("Repository URL is required");
      return;
    }

    try {
      const result = await cloneRepo.mutateAsync({
        repoUrl: trimmedUrl,
        targetDir: targetDir.trim() || undefined,
      });
      setSuccessMessage(result.message);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to clone repository";
      setError(message);
    }
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) {
          handleClose();
        }
      }}
    >
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitBranch size={18} />
            Clone Repository
          </DialogTitle>
          <DialogDescription>
            Clone a git repository into the selected project
            {projectName ? `: ${projectName}` : ""}.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="repo-url">Repository URL</Label>
            <Input
              id="repo-url"
              placeholder="https://github.com/owner/repo.git"
              value={repoUrl}
              onChange={(event) => setRepoUrl(event.target.value)}
              disabled={cloneRepo.isPending}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="target-dir">Target Directory (optional)</Label>
            <Input
              id="target-dir"
              placeholder="repo-name"
              value={targetDir}
              onChange={(event) => setTargetDir(event.target.value)}
              disabled={cloneRepo.isPending}
            />
            <p className="text-xs text-muted-foreground">
              Leave blank to derive the folder name from the repository URL.
            </p>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {successMessage && (
            <Alert>
              <AlertDescription>{successMessage}</AlertDescription>
            </Alert>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={handleClose} disabled={cloneRepo.isPending}>
              Close
            </Button>
            <Button type="submit" disabled={cloneRepo.isPending || !projectName}>
              {cloneRepo.isPending ? (
                <span className="flex items-center gap-2">
                  <Loader2 size={16} className="animate-spin" />
                  Cloning...
                </span>
              ) : (
                "Clone"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
