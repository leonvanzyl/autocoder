/**
 * Spec Creation Chat Component
 *
 * Full chat interface for interactive spec creation with Claude.
 * Handles the 7-phase conversation flow for creating app specifications.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Send,
  X,
  CheckCircle2,
  AlertCircle,
  Wifi,
  WifiOff,
  RotateCcw,
  Loader2,
  ArrowRight,
  Zap,
  Paperclip,
  ExternalLink,
  FileText,
} from "lucide-react";
import { useSpecChat } from "../hooks/useSpecChat";
import { ChatMessage } from "./ChatMessage";
import { QuestionOptions } from "./QuestionOptions";
import { TypingIndicator } from "./TypingIndicator";
import type { ImageAttachment } from "../lib/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

// Image upload validation constants
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
const ALLOWED_TYPES = ["image/jpeg", "image/png"];

// Sample prompt for quick testing
const SAMPLE_PROMPT = `Let's call it Simple Todo. This is a really simple web app that I can use to track my to-do items using a Kanban board. I should be able to add to-dos and then drag and drop them through the Kanban board. The different columns in the Kanban board are:

- To Do
- In Progress
- Done

The app should use a neobrutalism design.

There is no need for user authentication either. All the to-dos will be stored in local storage, so each user has access to all of their to-dos when they open their browser. So do not worry about implementing a backend with user authentication or a database. Simply store everything in local storage. As for the design, please try to avoid AI slop, so use your front-end design skills to design something beautiful and practical. As for the content of the to-dos, we should store:

- The name or the title at the very least
- Optionally, we can also set tags, due dates, and priorities which should be represented as beautiful little badges on the to-do card

Users should have the ability to easily clear out all the completed To-Dos. They should also be able to filter and search for To-Dos as well.

You choose the rest. Keep it simple. Should be 25 features.`;

type InitializerStatus = "idle" | "starting" | "error";

interface SpecCreationChatProps {
  projectName: string;
  onComplete: (specPath: string, yoloMode?: boolean) => void;
  onCancel: () => void;
  onExitToProject: () => void; // Exit to project without starting agent
  initializerStatus?: InitializerStatus;
  initializerError?: string | null;
  onRetryInitializer?: () => void;
}

export function SpecCreationChat({
  projectName,
  onComplete,
  onCancel,
  onExitToProject,
  initializerStatus = "idle",
  initializerError = null,
  onRetryInitializer,
}: SpecCreationChatProps) {
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [yoloEnabled, setYoloEnabled] = useState(false);
  const [pendingAttachments, setPendingAttachments] = useState<
    ImageAttachment[]
  >([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    messages,
    isLoading,
    isComplete,
    connectionStatus,
    currentQuestions,
    start,
    sendMessage,
    sendAnswer,
    disconnect,
  } = useSpecChat({
    projectName,
    onComplete,
    onError: (err) => setError(err),
  });

  // Start the chat session when component mounts
  useEffect(() => {
    start();

    return () => {
      disconnect();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentQuestions, isLoading]);

  // Focus input when not loading and no questions
  useEffect(() => {
    if (!isLoading && !currentQuestions && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isLoading, currentQuestions]);

  const handleSendMessage = () => {
    const trimmed = input.trim();
    // Allow sending if there's text OR attachments
    if ((!trimmed && pendingAttachments.length === 0) || isLoading) return;

    // Detect /exit command - exit to project without sending to Claude
    if (/^\s*\/exit\s*$/i.test(trimmed)) {
      setInput("");
      onExitToProject();
      return;
    }

    sendMessage(
      trimmed,
      pendingAttachments.length > 0 ? pendingAttachments : undefined,
    );
    setInput("");
    setPendingAttachments([]); // Clear attachments after sending
    // Reset textarea height after sending
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleAnswerSubmit = (answers: Record<string, string | string[]>) => {
    sendAnswer(answers);
  };

  // File handling for image attachments
  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return;

    Array.from(files).forEach((file) => {
      // Validate file type
      if (!ALLOWED_TYPES.includes(file.type)) {
        setError(
          `Invalid file type: ${file.name}. Only JPEG and PNG are supported.`,
        );
        return;
      }

      // Validate file size
      if (file.size > MAX_FILE_SIZE) {
        setError(`File too large: ${file.name}. Maximum size is 5 MB.`);
        return;
      }

      // Read and convert to base64
      const reader = new FileReader();
      reader.onload = (e) => {
        const dataUrl = e.target?.result as string;
        // dataUrl is "data:image/png;base64,XXXXXX"
        const base64Data = dataUrl.split(",")[1];

        const attachment: ImageAttachment = {
          id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
          filename: file.name,
          mimeType: file.type as "image/jpeg" | "image/png",
          base64Data,
          previewUrl: dataUrl,
          size: file.size,
        };

        setPendingAttachments((prev) => [...prev, attachment]);
      };
      reader.readAsDataURL(file);
    });
  }, []);

  const handleRemoveAttachment = useCallback((id: string) => {
    setPendingAttachments((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      handleFileSelect(e.dataTransfer.files);
    },
    [handleFileSelect],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  // Connection status indicator
  const ConnectionIndicator = () => {
    switch (connectionStatus) {
      case "connected":
        return (
          <span className="flex items-center gap-1 text-xs text-green-500">
            <Wifi size={12} />
            Connected
          </span>
        );
      case "connecting":
        return (
          <span className="flex items-center gap-1 text-xs text-yellow-500">
            <Wifi size={12} className="animate-pulse" />
            Connecting...
          </span>
        );
      case "error":
        return (
          <span className="flex items-center gap-1 text-xs text-destructive">
            <WifiOff size={12} />
            Error
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <WifiOff size={12} />
            Disconnected
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b-2 border-border bg-card">
        <div className="flex items-center gap-3">
          <h2 className="font-display font-bold text-lg text-foreground">
            Create Spec: {projectName}
          </h2>
          <ConnectionIndicator />
        </div>

        <div className="flex items-center gap-2">
          {isComplete && (
            <span className="flex items-center gap-1 text-sm text-green-500 font-bold">
              <CheckCircle2 size={16} />
              Complete
            </span>
          )}

          {/* Load Sample Prompt */}
          <Button
            onClick={() => {
              setInput(SAMPLE_PROMPT);
              // Also resize the textarea to fit content
              if (inputRef.current) {
                inputRef.current.style.height = "auto";
                inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 200)}px`;
              }
            }}
            variant="ghost"
            size="sm"
            title="Load sample prompt (Simple Todo app)"
          >
            <FileText size={16} />
            Load Sample
          </Button>

          {/* Exit to Project - always visible escape hatch */}
          <Button
            onClick={onExitToProject}
            variant="ghost"
            size="sm"
            title="Exit chat and go to project (you can start the agent manually)"
          >
            <ExternalLink size={16} />
            Exit to Project
          </Button>

          <Button onClick={onCancel} variant="ghost" size="icon" title="Cancel">
            <X size={20} />
          </Button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <Alert
          variant="destructive"
          className="rounded-none border-x-0 border-t-0"
        >
          <AlertCircle size={16} />
          <AlertDescription className="flex-1">{error}</AlertDescription>
          <Button
            onClick={() => setError(null)}
            variant="ghost"
            size="icon"
            className="h-6 w-6"
          >
            <X size={14} />
          </Button>
        </Alert>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto py-4">
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full text-center p-8">
            <Card className="p-6 max-w-md">
              <CardContent className="p-0">
                <h3 className="font-display font-bold text-lg mb-2">
                  Starting Spec Creation
                </h3>
                <p className="text-sm text-muted-foreground">
                  Connecting to Claude to help you create your app
                  specification...
                </p>
                {connectionStatus === "error" && (
                  <Button onClick={start} className="mt-4" size="sm">
                    <RotateCcw size={14} />
                    Retry Connection
                  </Button>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        {/* Structured questions */}
        {currentQuestions && currentQuestions.length > 0 && (
          <QuestionOptions
            questions={currentQuestions}
            onSubmit={handleAnswerSubmit}
            disabled={isLoading}
          />
        )}

        {/* Typing indicator - don't show when we have questions (waiting for user) */}
        {isLoading && !currentQuestions && <TypingIndicator />}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      {!isComplete && (
        <div
          className="p-4 border-t-2 border-border bg-card"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          {/* Attachment previews */}
          {pendingAttachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {pendingAttachments.map((attachment) => (
                <div
                  key={attachment.id}
                  className="relative group border-2 border-border p-1 bg-card rounded shadow-sm"
                >
                  <img
                    src={attachment.previewUrl}
                    alt={attachment.filename}
                    className="w-16 h-16 object-cover rounded"
                  />
                  <button
                    onClick={() => handleRemoveAttachment(attachment.id)}
                    className="absolute -top-2 -right-2 bg-destructive text-destructive-foreground rounded-full p-0.5 border-2 border-border hover:scale-110 transition-transform"
                    title="Remove attachment"
                  >
                    <X size={12} />
                  </button>
                  <span className="text-xs truncate block max-w-16 mt-1 text-center text-muted-foreground">
                    {attachment.filename.length > 10
                      ? `${attachment.filename.substring(0, 7)}...`
                      : attachment.filename}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-3">
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png"
              multiple
              onChange={(e) => handleFileSelect(e.target.files)}
              className="hidden"
            />

            {/* Attach button */}
            <Button
              onClick={() => fileInputRef.current?.click()}
              disabled={connectionStatus !== "connected"}
              variant="ghost"
              size="icon"
              title="Attach image (JPEG, PNG - max 5MB)"
            >
              <Paperclip size={18} />
            </Button>

            <Textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                // Auto-resize the textarea
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
              }}
              onKeyDown={handleKeyDown}
              placeholder={
                currentQuestions
                  ? "Or type a custom response..."
                  : pendingAttachments.length > 0
                    ? "Add a message with your image(s)..."
                    : "Type your response... (or /exit to go to project)"
              }
              className="flex-1 resize-none min-h-[46px] max-h-[200px] overflow-y-auto"
              disabled={
                (isLoading && !currentQuestions) ||
                connectionStatus !== "connected"
              }
              rows={1}
            />
            <Button
              onClick={handleSendMessage}
              disabled={
                (!input.trim() && pendingAttachments.length === 0) ||
                (isLoading && !currentQuestions) ||
                connectionStatus !== "connected"
              }
              className="px-6"
            >
              <Send size={18} />
            </Button>
          </div>

          {/* Help text */}
          <p className="text-xs text-muted-foreground mt-2">
            Press Enter to send, Shift+Enter for new line. Drag & drop or click{" "}
            <Paperclip size={12} className="inline" /> to attach images
            (JPEG/PNG, max 5MB).
          </p>
        </div>
      )}

      {/* Completion footer */}
      {isComplete && (
        <div
          className={`p-4 border-t-2 border-border ${
            initializerStatus === "error" ? "bg-destructive" : "bg-green-500"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {initializerStatus === "starting" ? (
                <>
                  <Loader2 size={20} className="animate-spin text-white" />
                  <span className="font-bold text-white">
                    Starting agent{yoloEnabled ? " (YOLO mode)" : ""}...
                  </span>
                </>
              ) : initializerStatus === "error" ? (
                <>
                  <AlertCircle size={20} className="text-white" />
                  <span className="font-bold text-white">
                    {initializerError || "Failed to start agent"}
                  </span>
                </>
              ) : (
                <>
                  <CheckCircle2 size={20} className="text-white" />
                  <span className="font-bold text-white">
                    Specification created successfully!
                  </span>
                </>
              )}
            </div>
            <div className="flex items-center gap-2">
              {initializerStatus === "error" && onRetryInitializer && (
                <Button onClick={onRetryInitializer} variant="secondary">
                  <RotateCcw size={14} />
                  Retry
                </Button>
              )}
              {initializerStatus === "idle" && (
                <>
                  {/* YOLO Mode Toggle */}
                  <Button
                    onClick={() => setYoloEnabled(!yoloEnabled)}
                    variant={yoloEnabled ? "default" : "secondary"}
                    size="sm"
                    className={
                      yoloEnabled
                        ? "bg-yellow-500 hover:bg-yellow-600 text-yellow-900"
                        : ""
                    }
                    title="YOLO Mode: Skip testing for rapid prototyping"
                  >
                    <Zap size={16} />
                    <span className={yoloEnabled ? "font-bold" : ""}>YOLO</span>
                  </Button>
                  <Button onClick={() => onComplete("", yoloEnabled)}>
                    Continue to Project
                    <ArrowRight size={16} />
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
