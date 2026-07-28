import { EmptyState } from "../components/chat/EmptyState";
import { QueryInput } from "../components/chat/QueryInput";

interface HomePageProps {
  onSubmitQuery: (query: string) => void;
}

export function HomePage({ onSubmitQuery }: HomePageProps) {
  return (
    <main className="home-page">
      <EmptyState />
      <QueryInput onSubmit={onSubmitQuery} />
    </main>
  );
}
