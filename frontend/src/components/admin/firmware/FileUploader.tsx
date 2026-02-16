import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Upload, File, X, CheckCircle2, AlertCircle } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface FileWithStatus {
  file: File;
  status: "pending" | "uploading" | "success" | "error";
  progress: number;
  checksum?: string;
  error?: string;
}

interface FileUploaderProps {
  onFilesChange: (files: File[]) => void;
  accept?: string;
  maxFiles?: number;
  maxSize?: number; // in bytes
}

export function FileUploader({
  onFilesChange,
  accept = ".py,.json",
  maxFiles = 10,
  maxSize = 500 * 1024, // 500KB default
}: FileUploaderProps) {
  const [files, setFiles] = useState<FileWithStatus[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;

    const newFiles: FileWithStatus[] = [];
    for (let i = 0; i < selectedFiles.length; i++) {
      const file = selectedFiles[i];

      // Check file size
      if (file.size > maxSize) {
        newFiles.push({
          file,
          status: "error",
          progress: 0,
          error: `File too large (max ${(maxSize / 1024).toFixed(0)}KB)`,
        });
        continue;
      }

      // Check file type
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (accept && !accept.includes(ext)) {
        newFiles.push({
          file,
          status: "error",
          progress: 0,
          error: "Invalid file type",
        });
        continue;
      }

      newFiles.push({
        file,
        status: "pending",
        progress: 0,
      });
    }

    const updatedFiles = [...files, ...newFiles].slice(0, maxFiles);
    setFiles(updatedFiles);

    // Notify parent of valid files
    const validFiles = updatedFiles
      .filter((f) => f.status !== "error")
      .map((f) => f.file);
    onFilesChange(validFiles);

    // Simulate checksum calculation
    updatedFiles.forEach((fileWithStatus, index) => {
      if (fileWithStatus.status === "pending") {
        setTimeout(() => {
          const checksum = generateMockChecksum(fileWithStatus.file);
          setFiles((prev) =>
            prev.map((f, i) =>
              i === files.length + index
                ? { ...f, status: "success", progress: 100, checksum }
                : f
            )
          );
        }, 500);
      }
    });
  };

  const generateMockChecksum = (file: File): string => {
    // Mock SHA256 checksum - in real app, use crypto.subtle.digest
    return `sha256:${file.name.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0).toString(16).padStart(64, "0")}`;
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const removeFile = (index: number) => {
    const updatedFiles = files.filter((_, i) => i !== index);
    setFiles(updatedFiles);

    const validFiles = updatedFiles
      .filter((f) => f.status !== "error")
      .map((f) => f.file);
    onFilesChange(validFiles);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={cn(
          "border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer",
          isDragging
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/50"
        )}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={accept}
          onChange={(e) => handleFileSelect(e.target.files)}
          className="hidden"
        />

        <Upload className="h-10 w-10 mx-auto mb-4 text-muted-foreground" />
        <h3 className="text-lg font-semibold mb-2">
          Drop files here or click to browse
        </h3>
        <p className="text-sm text-muted-foreground mb-2">
          {accept.split(",").join(", ")} files only
        </p>
        <p className="text-xs text-muted-foreground">
          Maximum {maxFiles} files, up to {(maxSize / 1024).toFixed(0)}KB each
        </p>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((fileWithStatus, index) => (
            <Card key={index}>
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  {/* Status Icon */}
                  <div className="flex-shrink-0 mt-1">
                    {fileWithStatus.status === "success" && (
                      <CheckCircle2 className="h-5 w-5 text-green-600" />
                    )}
                    {fileWithStatus.status === "error" && (
                      <AlertCircle className="h-5 w-5 text-destructive" />
                    )}
                    {(fileWithStatus.status === "pending" ||
                      fileWithStatus.status === "uploading") && (
                      <File className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>

                  {/* File Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-sm font-medium truncate">
                        {fileWithStatus.file.name}
                      </p>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 flex-shrink-0"
                        onClick={() => removeFile(index)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>

                    <p className="text-xs text-muted-foreground mb-2">
                      {formatFileSize(fileWithStatus.file.size)}
                      {fileWithStatus.checksum && (
                        <span className="ml-2 font-mono">
                          {fileWithStatus.checksum.slice(0, 16)}...
                        </span>
                      )}
                    </p>

                    {/* Progress Bar */}
                    {fileWithStatus.status === "uploading" && (
                      <Progress value={fileWithStatus.progress} className="h-1" />
                    )}

                    {/* Error Message */}
                    {fileWithStatus.status === "error" && (
                      <p className="text-xs text-destructive">
                        {fileWithStatus.error}
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Summary */}
      {files.length > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {files.filter((f) => f.status === "success").length} of {files.length}{" "}
            files ready
          </span>
          <span>
            Total size:{" "}
            {formatFileSize(
              files.reduce((acc, f) => acc + f.file.size, 0)
            )}
          </span>
        </div>
      )}
    </div>
  );
}
