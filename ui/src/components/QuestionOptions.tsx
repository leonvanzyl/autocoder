/**
 * Question Options Component
 *
 * Renders structured questions from AskUserQuestion tool.
 * Shows clickable option buttons.
 */

import { useState } from "react";
import { Check } from "lucide-react";
import type { SpecQuestion } from "../lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface QuestionOptionsProps {
  questions: SpecQuestion[];
  onSubmit: (answers: Record<string, string | string[]>) => void;
  disabled?: boolean;
}

export function QuestionOptions({
  questions,
  onSubmit,
  disabled = false,
}: QuestionOptionsProps) {
  // Track selected answers for each question
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [customInputs, setCustomInputs] = useState<Record<string, string>>({});
  const [showCustomInput, setShowCustomInput] = useState<
    Record<string, boolean>
  >({});

  const handleOptionClick = (
    questionIdx: number,
    optionLabel: string,
    multiSelect: boolean,
  ) => {
    const key = String(questionIdx);

    if (optionLabel === "Other") {
      setShowCustomInput((prev) => ({ ...prev, [key]: true }));
      return;
    }

    setShowCustomInput((prev) => ({ ...prev, [key]: false }));

    setAnswers((prev) => {
      if (multiSelect) {
        const current = (prev[key] as string[]) || [];
        if (current.includes(optionLabel)) {
          return { ...prev, [key]: current.filter((o) => o !== optionLabel) };
        } else {
          return { ...prev, [key]: [...current, optionLabel] };
        }
      } else {
        return { ...prev, [key]: optionLabel };
      }
    });
  };

  const handleCustomInputChange = (questionIdx: number, value: string) => {
    const key = String(questionIdx);
    setCustomInputs((prev) => ({ ...prev, [key]: value }));
    setAnswers((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = () => {
    // Ensure all questions have answers
    const finalAnswers: Record<string, string | string[]> = {};

    questions.forEach((_, idx) => {
      const key = String(idx);
      if (showCustomInput[key] && customInputs[key]) {
        finalAnswers[key] = customInputs[key];
      } else if (answers[key]) {
        finalAnswers[key] = answers[key];
      }
    });

    onSubmit(finalAnswers);
  };

  const isOptionSelected = (
    questionIdx: number,
    optionLabel: string,
    multiSelect: boolean,
  ) => {
    const key = String(questionIdx);
    const answer = answers[key];

    if (multiSelect) {
      return Array.isArray(answer) && answer.includes(optionLabel);
    }
    return answer === optionLabel;
  };

  const hasAnswer = (questionIdx: number) => {
    const key = String(questionIdx);
    return !!(answers[key] || (showCustomInput[key] && customInputs[key]));
  };

  const allQuestionsAnswered = questions.every((_, idx) => hasAnswer(idx));

  return (
    <div className="space-y-6 p-4">
      {questions.map((q, questionIdx) => (
        <Card key={questionIdx}>
          <CardContent className="p-4">
            {/* Question header */}
            <div className="flex items-center gap-3 mb-4">
              <Badge>{q.header}</Badge>
              <span className="font-bold text-foreground">{q.question}</span>
              {q.multiSelect && (
                <span className="text-xs text-muted-foreground font-mono">
                  (select multiple)
                </span>
              )}
            </div>

            {/* Options grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {q.options.map((opt, optIdx) => {
                const isSelected = isOptionSelected(
                  questionIdx,
                  opt.label,
                  q.multiSelect,
                );

                return (
                  <button
                    key={optIdx}
                    onClick={() =>
                      handleOptionClick(questionIdx, opt.label, q.multiSelect)
                    }
                    disabled={disabled}
                    className={`
                      text-left p-4 rounded-lg border-2 transition-all duration-150
                      ${
                        isSelected
                          ? "bg-primary/10 border-primary"
                          : "bg-card border-border hover:border-primary/50 hover:bg-muted"
                      }
                      disabled:opacity-50 disabled:cursor-not-allowed
                    `}
                  >
                    <div className="flex items-start gap-2">
                      {/* Checkbox/Radio indicator */}
                      <div
                        className={`
                          w-5 h-5 flex-shrink-0 mt-0.5 border-2 flex items-center justify-center
                          ${q.multiSelect ? "rounded" : "rounded-full"}
                          ${isSelected ? "bg-primary border-primary text-primary-foreground" : "border-border bg-background"}
                        `}
                      >
                        {isSelected && <Check size={12} strokeWidth={3} />}
                      </div>

                      <div className="flex-1">
                        <div className="font-bold text-foreground">
                          {opt.label}
                        </div>
                        <div className="text-sm text-muted-foreground mt-1">
                          {opt.description}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}

              {/* "Other" option */}
              <button
                onClick={() =>
                  handleOptionClick(questionIdx, "Other", q.multiSelect)
                }
                disabled={disabled}
                className={`
                  text-left p-4 rounded-lg border-2 transition-all duration-150
                  ${
                    showCustomInput[String(questionIdx)]
                      ? "bg-primary/10 border-primary"
                      : "bg-card border-border hover:border-primary/50 hover:bg-muted"
                  }
                  disabled:opacity-50 disabled:cursor-not-allowed
                `}
              >
                <div className="flex items-start gap-2">
                  <div
                    className={`
                      w-5 h-5 flex-shrink-0 mt-0.5 border-2 flex items-center justify-center
                      ${q.multiSelect ? "rounded" : "rounded-full"}
                      ${showCustomInput[String(questionIdx)] ? "bg-primary border-primary text-primary-foreground" : "border-border bg-background"}
                    `}
                  >
                    {showCustomInput[String(questionIdx)] && (
                      <Check size={12} strokeWidth={3} />
                    )}
                  </div>

                  <div className="flex-1">
                    <div className="font-bold text-foreground">Other</div>
                    <div className="text-sm text-muted-foreground mt-1">
                      Provide a custom answer
                    </div>
                  </div>
                </div>
              </button>
            </div>

            {/* Custom input field */}
            {showCustomInput[String(questionIdx)] && (
              <div className="mt-4">
                <Input
                  type="text"
                  value={customInputs[String(questionIdx)] || ""}
                  onChange={(e) =>
                    handleCustomInputChange(questionIdx, e.target.value)
                  }
                  placeholder="Type your answer..."
                  autoFocus
                  disabled={disabled}
                />
              </div>
            )}
          </CardContent>
        </Card>
      ))}

      {/* Submit button */}
      <div className="flex justify-end">
        <Button
          onClick={handleSubmit}
          disabled={disabled || !allQuestionsAnswered}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
