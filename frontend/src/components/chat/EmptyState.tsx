// Hardcoded placeholder examples for this ticket. The golden-dataset-driven
// version (drawn from the 50-query eval set) is a later phase's job.
const EXAMPLE_QUESTIONS = [
  "What genes are associated with cystic fibrosis?",
  "Show me clinical trials for BRCA1-related breast cancer.",
  "What is the clinical significance of rs334?",
];

export function EmptyState() {
  return (
    <section aria-labelledby="empty-state-heading" className="empty-state">
      <h1 id="empty-state-heading">Ask the agent a biomedical question</h1>
      <p>
        Search across the NCBI knowledge graph, live NCBI APIs, and
        enrichment sources with every answer traced back to its source.
      </p>
      <div>
        <h2>Example questions</h2>
        <ul>
          {EXAMPLE_QUESTIONS.map((question) => (
            <li key={question}>{question}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
