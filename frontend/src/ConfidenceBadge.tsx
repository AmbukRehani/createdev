interface ConfidenceBadgeProps {
  confidence: number;
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const pct = Math.round(confidence * 100);
  const level = confidence >= 0.75 ? "high" : confidence >= 0.5 ? "medium" : "low";

  return (
    <span className={`confidence-badge confidence-badge--${level}`}>
      {pct}% confidence
    </span>
  );
}
