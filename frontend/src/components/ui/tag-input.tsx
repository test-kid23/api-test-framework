import { useState, useRef, type KeyboardEvent } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  className?: string;
  maxTags?: number;
}

export function TagInput({
  value,
  onChange,
  placeholder = "输入标签后按回车...",
  className,
  maxTags = 20,
}: TagInputProps) {
  const [inputValue, setInputValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (!trimmed) return;
    if (value.includes(trimmed)) return;
    if (value.length >= maxTags) return;
    onChange([...value, trimmed]);
    setInputValue("");
  };

  const removeTag = (tag: string) => {
    onChange(value.filter((t) => t !== tag));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addTag(inputValue);
    }
    if (e.key === "Backspace" && !inputValue && value.length > 0) {
      removeTag(value[value.length - 1]);
    }
    if (e.key === "," || e.key === "，") {
      e.preventDefault();
      addTag(inputValue);
    }
  };

  const handleBlur = () => {
    if (inputValue) {
      addTag(inputValue);
    }
  };

  return (
    <div
      className={cn(
        "flex min-h-[40px] flex-wrap items-center gap-1.5 rounded-md border border-input bg-background px-3 py-2",
        "focus-within:outline-none focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1",
        className
      )}
      onClick={() => inputRef.current?.focus()}
    >
      {value.map((tag) => (
        <Badge key={tag} variant="secondary" className="gap-1 pr-1">
          {tag}
          <button
            type="button"
            className="ml-0.5 rounded-full outline-none hover:bg-muted-foreground/20"
            onClick={(e) => {
              e.stopPropagation();
              removeTag(tag);
            }}
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>
      ))}
      {value.length < maxTags && (
        <Input
          ref={inputRef}
          type="text"
          className="h-auto min-w-[80px] flex-1 border-0 bg-transparent p-0 text-sm shadow-none outline-none focus-visible:ring-0"
          placeholder={value.length === 0 ? placeholder : ""}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
        />
      )}
    </div>
  );
}
