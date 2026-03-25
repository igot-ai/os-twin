'use client';

interface PlanEditorTabProps {
  content: string;
  onChange: (content: string) => void;
}

export default function PlanEditorTab({ content, onChange }: PlanEditorTabProps) {
  return (
    <textarea
      className="w-full h-full font-mono text-sm bg-background border-none resize-none p-4 focus:outline-none custom-scrollbar text-text-main placeholder:text-text-faint"
      value={content}
      onChange={(e) => onChange(e.target.value)}
      placeholder={"# Plan: My Feature\n\n## Config\nworking_dir: .\n\n## EPIC-001 — Feature Title\n..."}
      spellCheck={false}
    />
  );
}
