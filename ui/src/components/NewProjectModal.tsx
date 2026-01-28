/**
 * New Project Modal Component
 *
 * Multi-step modal for creating new projects:
 * 1. Enter project name
 * 2. Select project folder
 * 3. Choose spec method (Claude or manual)
 * 4a. If Claude: Show SpecCreationChat
 * 4b. If manual: Create project and close
 */

import { useState } from "react";
import {
  Bot,
  FileEdit,
  ArrowRight,
  ArrowLeft,
  Loader2,
  CheckCircle2,
  Folder,
} from "lucide-react";
import { useCreateProject } from "../hooks/useProjects";
import { SpecCreationChat } from "./SpecCreationChat";
import { FolderBrowser } from "./FolderBrowser";
import { startAgent } from "../lib/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

type InitializerStatus = "idle" | "starting" | "error";

type Step = "name" | "folder" | "method" | "chat" | "complete";
type SpecMethod = "claude" | "manual";

interface NewProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectCreated: (projectName: string) => void;
  onStepChange?: (step: Step) => void;
}

export function NewProjectModal({
  isOpen,
  onClose,
  onProjectCreated,
  onStepChange,
}: NewProjectModalProps) {
  const [step, setStep] = useState<Step>("name");
  const [projectName, setProjectName] = useState("");
  const [projectPath, setProjectPath] = useState<string | null>(null);
  const [_specMethod, setSpecMethod] = useState<SpecMethod | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [initializerStatus, setInitializerStatus] =
    useState<InitializerStatus>("idle");
  const [initializerError, setInitializerError] = useState<string | null>(null);
  const [yoloModeSelected, setYoloModeSelected] = useState(false);

  // Suppress unused variable warning - specMethod may be used in future
  void _specMethod;

  const createProject = useCreateProject();

  // Wrapper to notify parent of step changes
  const changeStep = (newStep: Step) => {
    setStep(newStep);
    onStepChange?.(newStep);
  };

  if (!isOpen) return null;

  const handleNameSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = projectName.trim();

    if (!trimmed) {
      setError("Please enter a project name");
      return;
    }

    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      setError(
        "Project name can only contain letters, numbers, hyphens, and underscores",
      );
      return;
    }

    setError(null);
    changeStep("folder");
  };

  const handleFolderSelect = (path: string) => {
    setProjectPath(path);
    changeStep("method");
  };

  const handleFolderCancel = () => {
    changeStep("name");
  };

  const handleMethodSelect = async (method: SpecMethod) => {
    setSpecMethod(method);

    if (!projectPath) {
      setError("Please select a project folder first");
      changeStep("folder");
      return;
    }

    if (method === "manual") {
      // Create project immediately with manual method
      try {
        const project = await createProject.mutateAsync({
          name: projectName.trim(),
          path: projectPath,
          specMethod: "manual",
        });
        changeStep("complete");
        setTimeout(() => {
          onProjectCreated(project.name);
          handleClose();
        }, 1500);
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : "Failed to create project",
        );
      }
    } else {
      // Create project then show chat
      try {
        await createProject.mutateAsync({
          name: projectName.trim(),
          path: projectPath,
          specMethod: "claude",
        });
        changeStep("chat");
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : "Failed to create project",
        );
      }
    }
  };

  const handleSpecComplete = async (
    _specPath: string,
    yoloMode: boolean = false,
  ) => {
    // Save yoloMode for retry
    setYoloModeSelected(yoloMode);
    // Auto-start the initializer agent
    setInitializerStatus("starting");
    try {
      // Use default concurrency of 3 to match AgentControl.tsx default
      await startAgent(projectName.trim(), {
        yoloMode,
        maxConcurrency: 3,
      });
      // Success - navigate to project
      changeStep("complete");
      setTimeout(() => {
        onProjectCreated(projectName.trim());
        handleClose();
      }, 1500);
    } catch (err) {
      setInitializerStatus("error");
      setInitializerError(
        err instanceof Error ? err.message : "Failed to start agent",
      );
    }
  };

  const handleRetryInitializer = () => {
    setInitializerError(null);
    setInitializerStatus("idle");
    handleSpecComplete("", yoloModeSelected);
  };

  const handleChatCancel = () => {
    // Go back to method selection but keep the project
    changeStep("method");
    setSpecMethod(null);
  };

  const handleExitToProject = () => {
    // Exit chat and go directly to project - user can start agent manually
    onProjectCreated(projectName.trim());
    handleClose();
  };

  const handleClose = () => {
    changeStep("name");
    setProjectName("");
    setProjectPath(null);
    setSpecMethod(null);
    setError(null);
    setInitializerStatus("idle");
    setInitializerError(null);
    setYoloModeSelected(false);
    onClose();
  };

  const handleBack = () => {
    if (step === "method") {
      changeStep("folder");
      setSpecMethod(null);
    } else if (step === "folder") {
      changeStep("name");
      setProjectPath(null);
    }
  };

  // Full-screen chat view
  if (step === "chat") {
    return (
      <div className="fixed inset-0 z-50 bg-background">
        <SpecCreationChat
          projectName={projectName.trim()}
          onComplete={handleSpecComplete}
          onCancel={handleChatCancel}
          onExitToProject={handleExitToProject}
          initializerStatus={initializerStatus}
          initializerError={initializerError}
          onRetryInitializer={handleRetryInitializer}
        />
      </div>
    );
  }

  // Folder step uses larger modal
  if (step === "folder") {
    return (
      <Dialog open={true} onOpenChange={(open) => !open && handleClose()}>
        <DialogContent className="sm:max-w-3xl max-h-[85vh] flex flex-col p-0">
          {/* Header */}
          <DialogHeader className="p-6 pb-4 border-b">
            <div className="flex items-center gap-3">
              <Folder size={24} className="text-primary" />
              <div>
                <DialogTitle>Select Project Location</DialogTitle>
                <DialogDescription>
                  Select the folder to use for project{" "}
                  <span className="font-semibold font-mono">{projectName}</span>
                  . Create a new folder or choose an existing one.
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          {/* Folder Browser */}
          <div className="flex-1 overflow-hidden">
            <FolderBrowser
              onSelect={handleFolderSelect}
              onCancel={handleFolderCancel}
            />
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={true} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {step === "name" && "Create New Project"}
            {step === "method" && "Choose Setup Method"}
            {step === "complete" && "Project Created!"}
          </DialogTitle>
        </DialogHeader>

        {/* Step 1: Project Name */}
        {step === "name" && (
          <form onSubmit={handleNameSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="project-name">Project Name</Label>
              <Input
                id="project-name"
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="my-awesome-app"
                pattern="^[a-zA-Z0-9_-]+$"
                autoFocus
              />
              <p className="text-sm text-muted-foreground">
                Use letters, numbers, hyphens, and underscores only.
              </p>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <DialogFooter>
              <Button type="submit" disabled={!projectName.trim()}>
                Next
                <ArrowRight size={16} />
              </Button>
            </DialogFooter>
          </form>
        )}

        {/* Step 2: Spec Method */}
        {step === "method" && (
          <div className="space-y-4">
            <DialogDescription>
              How would you like to define your project?
            </DialogDescription>

            <div className="space-y-3">
              {/* Claude option */}
              <Card
                className="cursor-pointer hover:border-primary transition-colors"
                onClick={() =>
                  !createProject.isPending && handleMethodSelect("claude")
                }
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-primary/10 rounded-lg">
                      <Bot size={24} className="text-primary" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">
                          Create with Claude
                        </span>
                        <Badge>Recommended</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        Interactive conversation to define features and generate
                        your app specification automatically.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Manual option */}
              <Card
                className="cursor-pointer hover:border-primary transition-colors"
                onClick={() =>
                  !createProject.isPending && handleMethodSelect("manual")
                }
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-secondary rounded-lg">
                      <FileEdit
                        size={24}
                        className="text-secondary-foreground"
                      />
                    </div>
                    <div className="flex-1">
                      <span className="font-semibold">
                        Edit Templates Manually
                      </span>
                      <p className="text-sm text-muted-foreground mt-1">
                        Edit the template files directly. Best for developers
                        who want full control.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {createProject.isPending && (
              <div className="flex items-center justify-center gap-2 text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                <span>Creating project...</span>
              </div>
            )}

            <DialogFooter className="sm:justify-start">
              <Button
                variant="ghost"
                onClick={handleBack}
                disabled={createProject.isPending}
              >
                <ArrowLeft size={16} />
                Back
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 3: Complete */}
        {step === "complete" && (
          <div className="text-center py-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-full mb-4">
              <CheckCircle2 size={32} className="text-primary" />
            </div>
            <h3 className="font-semibold text-xl mb-2">{projectName}</h3>
            <p className="text-muted-foreground">
              Your project has been created successfully!
            </p>
            <div className="mt-4 flex items-center justify-center gap-2">
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm text-muted-foreground">
                Redirecting...
              </span>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
