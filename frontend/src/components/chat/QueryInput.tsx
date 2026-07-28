import { useId, useState, type FormEvent, type KeyboardEvent } from "react";

interface QueryInputProps {
  onSubmit: (query: string) => void;
}

/**
 * A single labeled text field for submitting a query. Section 12.10 success
 * criterion 3.3.2 requires a real <label>, not a placeholder-only affordance,
 * so the placeholder here is supplementary example text only; the <label>
 * element is the actual accessible name.
 */
export function QueryInput({ onSubmit }: QueryInputProps) {
  const [value, setValue] = useState("");
  const inputId = useId();

  const submitIfNonEmpty = () => {
    const trimmed = value.trim();
    if (trimmed.length > 0) {
      onSubmit(trimmed);
      setValue("");
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitIfNonEmpty();
  };

  // Explicit Enter handling rather than relying only on native implicit form
  // submission: keeps behavior consistent across browsers and jsdom, and
  // preventDefault() here stops the native implicit submit from also firing,
  // so submitIfNonEmpty() runs exactly once per Enter press.
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submitIfNonEmpty();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="query-input">
      <label htmlFor={inputId}>Ask a question</label>
      <input
        id={inputId}
        name="query"
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="e.g. What genes are associated with cystic fibrosis?"
        autoComplete="off"
      />
      <button type="submit">Search</button>
    </form>
  );
}
