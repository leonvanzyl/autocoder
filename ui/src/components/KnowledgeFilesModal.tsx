import { useState, useRef, useEffect } from "react";
import {
  X,
  Loader2,
  AlertCircle,
  FileText,
  Trash2,
  Upload,
  Plus,
  Eye,
  Edit2,
} from "lucide-react";
import {
  useKnowledgeFiles,
  useKnowledgeFile,
  useUploadKnowledgeFile,
  useDeleteKnowledgeFile,
} from "../hooks/useProjects";
import type { KnowledgeFile } from "../lib/types";

interface KnowledgeFilesModalProps {
  projectName: string;
  onClose: () => void;
}

type ViewMode = "list" | "view" | "edit" | "create";

export function KnowledgeFilesModal({
  projectName,
  onClose,
}: KnowledgeFilesModalProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [newFileName, setNewFileName] = useState("");
  const [editContent, setEditContent] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const {
    data: filesData,
    isLoading,
    isError,
    refetch,
  } = useKnowledgeFiles(projectName);
  const { data: fileContent, isLoading: isLoadingContent } = useKnowledgeFile(
    projectName,
    viewMode === "view" || viewMode === "edit" ? selectedFile : null,
  );
  const uploadFile = useUploadKnowledgeFile(projectName);
  const deleteFile = useDeleteKnowledgeFile(projectName);

  // Load content into edit textarea when viewing a file for editing
  useEffect(() => {
    if (viewMode === "edit" && fileContent) {
      setEditContent(fileContent.content);
    }
  }, [viewMode, fileContent]);

  // Focus trap and escape key handling
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (deleteConfirm) {
          setDeleteConfirm(null);
        } else if (viewMode !== "list") {
          setViewMode("list");
          setSelectedFile(null);
          setNewFileName("");
          setEditContent("");
        } else {
          onClose();
        }
      }
    };

    document.addEventListener("keydown", handleEscape);
    closeButtonRef.current?.focus();

    return () => document.removeEventListener("keydown", handleEscape);
  }, [onClose, viewMode, deleteConfirm]);

  const handleViewFile = (filename: string) => {
    setSelectedFile(filename);
    setViewMode("view");
  };

  const handleEditFile = (filename: string) => {
    setSelectedFile(filename);
    setViewMode("edit");
  };

  const handleCreateNew = () => {
    setNewFileName("");
    setEditContent("");
    setViewMode("create");
  };

  const handleSaveFile = () => {
    const filename = viewMode === "create" ? newFileName : selectedFile;
    if (!filename) return;

    // Ensure .md extension
    const finalFilename = filename.endsWith(".md")
      ? filename
      : `${filename}.md`;

    uploadFile.mutate(
      { filename: finalFilename, content: editContent },
      {
        onSuccess: () => {
          setViewMode("list");
          setSelectedFile(null);
          setNewFileName("");
          setEditContent("");
        },
      },
    );
  };

  const handleDeleteFile = (filename: string) => {
    deleteFile.mutate(filename, {
      onSuccess: () => {
        setDeleteConfirm(null);
        if (selectedFile === filename) {
          setViewMode("list");
          setSelectedFile(null);
        }
      },
    });
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const renderList = () => (
    <>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="font-display text-xl font-bold">Knowledge Files</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCreateNew}
            className="neo-btn neo-btn-primary text-sm py-2 px-3 flex items-center gap-2"
          >
            <Plus size={16} />
            New File
          </button>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            className="neo-btn neo-btn-ghost p-2"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>
      </div>

      <p className="text-sm text-[var(--color-neo-text-secondary)] mb-4">
        Upload markdown files with additional context, requirements, or
        documentation for the agent.
      </p>

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="animate-spin" size={24} />
          <span className="ml-2">Loading files...</span>
        </div>
      )}

      {/* Error State */}
      {isError && (
        <div className="p-4 bg-[var(--color-neo-danger)] text-white border-3 border-[var(--color-neo-border)] mb-4">
          <div className="flex items-center gap-2">
            <AlertCircle size={18} />
            <span>Failed to load knowledge files</span>
          </div>
          <button onClick={() => refetch()} className="mt-2 underline text-sm">
            Retry
          </button>
        </div>
      )}

      {/* File List */}
      {filesData && !isLoading && (
        <>
          {filesData.files.length === 0 ? (
            <div className="text-center py-8 text-[var(--color-neo-text-secondary)]">
              <FileText size={48} className="mx-auto mb-4 opacity-50" />
              <p>No knowledge files yet.</p>
              <p className="text-sm mt-2">
                Create a new file to add context for the agent.
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {filesData.files.map((file: KnowledgeFile) => (
                <div
                  key={file.name}
                  className="neo-card p-3 flex items-center justify-between group"
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <FileText
                      size={20}
                      className="text-[var(--color-neo-accent)] flex-shrink-0"
                    />
                    <div className="min-w-0">
                      <div className="font-medium truncate">{file.name}</div>
                      <div className="text-xs text-[var(--color-neo-text-secondary)]">
                        {formatFileSize(file.size)} •{" "}
                        {formatDate(file.modified)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => handleViewFile(file.name)}
                      className="neo-btn neo-btn-ghost p-2"
                      title="View"
                    >
                      <Eye size={16} />
                    </button>
                    <button
                      onClick={() => handleEditFile(file.name)}
                      className="neo-btn neo-btn-ghost p-2"
                      title="Edit"
                    >
                      <Edit2 size={16} />
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(file.name)}
                      className="neo-btn neo-btn-ghost p-2 text-[var(--color-neo-danger)]"
                      title="Delete"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Delete Confirmation */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="neo-card p-6 max-w-sm mx-4">
            <h3 className="font-display font-bold text-lg mb-4">
              Delete File?
            </h3>
            <p className="text-sm text-[var(--color-neo-text-secondary)] mb-4">
              Are you sure you want to delete <strong>{deleteConfirm}</strong>?
              This action cannot be undone.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="neo-btn neo-btn-ghost"
                disabled={deleteFile.isPending}
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteFile(deleteConfirm)}
                className="neo-btn bg-[var(--color-neo-danger)] text-white"
                disabled={deleteFile.isPending}
              >
                {deleteFile.isPending ? (
                  <Loader2 className="animate-spin" size={16} />
                ) : (
                  "Delete"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );

  const renderView = () => (
    <>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setViewMode("list");
              setSelectedFile(null);
            }}
            className="neo-btn neo-btn-ghost p-2"
          >
            ←
          </button>
          <h2 className="font-display text-lg font-bold truncate">
            {selectedFile}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode("edit")}
            className="neo-btn neo-btn-primary text-sm py-2 px-3 flex items-center gap-2"
          >
            <Edit2 size={16} />
            Edit
          </button>
          <button onClick={onClose} className="neo-btn neo-btn-ghost p-2">
            <X size={20} />
          </button>
        </div>
      </div>

      {isLoadingContent ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="animate-spin" size={24} />
        </div>
      ) : (
        <div className="neo-card p-4 max-h-[60vh] overflow-y-auto">
          <pre className="whitespace-pre-wrap text-sm font-mono">
            {fileContent?.content}
          </pre>
        </div>
      )}
    </>
  );

  const renderEdit = () => (
    <>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setViewMode(selectedFile ? "view" : "list");
              if (!selectedFile) {
                setNewFileName("");
                setEditContent("");
              }
            }}
            className="neo-btn neo-btn-ghost p-2"
            disabled={uploadFile.isPending}
          >
            ←
          </button>
          <h2 className="font-display text-lg font-bold">
            {viewMode === "create"
              ? "Create New File"
              : `Edit: ${selectedFile}`}
          </h2>
        </div>
        <button onClick={onClose} className="neo-btn neo-btn-ghost p-2">
          <X size={20} />
        </button>
      </div>

      {viewMode === "create" && (
        <div className="mb-4">
          <label className="block text-sm font-medium mb-1">Filename</label>
          <input
            type="text"
            value={newFileName}
            onChange={(e) => setNewFileName(e.target.value)}
            placeholder="my-document.md"
            className="neo-input w-full"
            disabled={uploadFile.isPending}
          />
          <p className="text-xs text-[var(--color-neo-text-secondary)] mt-1">
            .md extension will be added automatically if not provided
          </p>
        </div>
      )}

      <div className="mb-4">
        <label className="block text-sm font-medium mb-1">Content</label>
        <textarea
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          placeholder="# My Document&#10;&#10;Write your markdown content here..."
          className="neo-input w-full h-64 font-mono text-sm resize-y"
          disabled={uploadFile.isPending}
        />
      </div>

      {uploadFile.isError && (
        <div className="p-3 bg-red-50 border-3 border-red-200 text-red-700 text-sm mb-4">
          Failed to save file. Please try again.
        </div>
      )}

      <div className="flex gap-2 justify-end">
        <button
          onClick={() => {
            setViewMode(selectedFile ? "view" : "list");
            if (!selectedFile) {
              setNewFileName("");
              setEditContent("");
            }
          }}
          className="neo-btn neo-btn-ghost"
          disabled={uploadFile.isPending}
        >
          Cancel
        </button>
        <button
          onClick={handleSaveFile}
          className="neo-btn neo-btn-primary flex items-center gap-2"
          disabled={
            uploadFile.isPending ||
            !editContent.trim() ||
            (viewMode === "create" && !newFileName.trim())
          }
        >
          {uploadFile.isPending ? (
            <Loader2 className="animate-spin" size={16} />
          ) : (
            <Upload size={16} />
          )}
          Save
        </button>
      </div>
    </>
  );

  return (
    <div className="neo-modal-backdrop" onClick={onClose} role="presentation">
      <div
        ref={modalRef}
        className="neo-modal w-full max-w-2xl p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="knowledge-files-title"
        aria-modal="true"
      >
        {viewMode === "list" && renderList()}
        {viewMode === "view" && renderView()}
        {(viewMode === "edit" || viewMode === "create") && renderEdit()}
      </div>
    </div>
  );
}
