/**
 * Unit tests for KnowledgePanel.
 *
 * Verifies that the Knowledge settings panel:
 * - Renders the LLM, embedding, and dimension sections.
 * - Reflects the current effective values from props.
 * - Calls onUpdate when the LLM ModelSelect trigger is used.
 * - Calls onUpdate when the embedding input is committed (blur / Enter).
 * - Picks up the embedding dimension when a suggested model is selected.
 *
 * NOTE: The LLM section now uses <ModelSelect> (not a plain <select>).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

import { KnowledgePanel } from '../components/settings/KnowledgePanel';
import type { KnowledgeSettings, ModelInfo } from '../types/settings';

const mockModels: ModelInfo[] = [
  { id: 'anthropic/claude-haiku-4-5', label: 'Claude Haiku 4.5', provider_id: 'anthropic' },
  { id: 'openai/gpt-5',               label: 'GPT-5',            provider_id: 'openai' },
  // embedding model — should be filtered out of the chat picker
  { id: 'openai/text-embedding-3-small', label: 'OpenAI Embedding', provider_id: 'openai' },
];

const defaults: KnowledgeSettings = {
  knowledge_llm_model: '',
  knowledge_embedding_model: '',
  knowledge_embedding_dimension: 384,
};

// Helper: open the ModelSelect dropdown (click the trigger button)
function openLlmDropdown() {
  const trigger = screen.getAllByRole('button').find(
    (b) =>
      b.textContent?.includes('Use server default') ||
      b.textContent?.includes('Claude Haiku') ||
      b.textContent?.includes('GPT-5'),
  );
  if (!trigger) throw new Error('ModelSelect trigger button not found');
  fireEvent.click(trigger);
  return trigger;
}

describe('KnowledgePanel', () => {
  it('renders LLM, embedding, and dimension sections', () => {
    const onUpdate = vi.fn();
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);

    expect(screen.getByText(/Knowledge Models/i)).toBeInTheDocument();
    expect(screen.getByText(/^LLM Model$/i)).toBeInTheDocument();
    expect(screen.getByText(/^Embedding Model$/i)).toBeInTheDocument();
    expect(screen.getByText(/^Embedding Dimension$/i)).toBeInTheDocument();
  });

  it('shows the selected model label in the trigger when an LLM is set', () => {
    const onUpdate = vi.fn();
    render(
      <KnowledgePanel
        knowledge={{ ...defaults, knowledge_llm_model: 'anthropic/claude-haiku-4-5' }}
        onUpdate={onUpdate}
        allModels={mockModels}
      />,
    );
    expect(screen.getByText(/Claude Haiku 4\.5/i)).toBeInTheDocument();
  });

  it('filters out embedding models from the LLM picker dropdown', () => {
    const onUpdate = vi.fn();
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);

    openLlmDropdown();

    expect(screen.getByText(/Claude Haiku 4\.5/)).toBeInTheDocument();
    expect(screen.getByText(/GPT-5/)).toBeInTheDocument();
    expect(screen.queryByText(/OpenAI Embedding/)).not.toBeInTheDocument();
  });

  it('shows the placeholder when no LLM is set', () => {
    const onUpdate = vi.fn();
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);
    expect(screen.getAllByText(/server default/i).length).toBeGreaterThanOrEqual(2);
  });

  it('calls onUpdate when a model is selected from the LLM picker', async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);

    openLlmDropdown();

    const option = screen.getByRole('button', { name: /GPT-5/ });
    fireEvent.click(option);

    expect(onUpdate).toHaveBeenCalledWith({ knowledge_llm_model: 'openai/gpt-5' });
  });

  it('calls onUpdate with model + dimension when a suggested embedding is clicked', async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);

    const button = screen.getByRole('button', { name: /BAAI\/bge-base-en-v1\.5/ });
    fireEvent.click(button);

    expect(onUpdate).toHaveBeenCalledWith({
      knowledge_embedding_model: 'BAAI/bge-base-en-v1.5',
      knowledge_embedding_dimension: 768,
    });
  });

  it('calls onUpdate when the embedding input is changed and blurred with a custom id', () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={mockModels} />);
    const input = screen.getByPlaceholderText(/BAAI\/bge-small-en-v1\.5/);
    fireEvent.change(input, { target: { value: 'custom/model-id' } });
    fireEvent.blur(input);
    expect(onUpdate).toHaveBeenCalledWith({
      knowledge_embedding_model: 'custom/model-id',
      knowledge_embedding_dimension: 384,
    });
  });

  it('does not call onUpdate when the embedding value is unchanged on blur', () => {
    const onUpdate = vi.fn();
    render(
      <KnowledgePanel
        knowledge={{ ...defaults, knowledge_embedding_model: 'BAAI/bge-small-en-v1.5' }}
        onUpdate={onUpdate}
        allModels={mockModels}
      />,
    );
    const input = screen.getByPlaceholderText(/BAAI\/bge-small-en-v1\.5/);
    fireEvent.blur(input);
    expect(onUpdate).not.toHaveBeenCalled();
  });

  it('shows the read-only embedding dimension', () => {
    const onUpdate = vi.fn();
    render(
      <KnowledgePanel
        knowledge={{ ...defaults, knowledge_embedding_dimension: 768 }}
        onUpdate={onUpdate}
        allModels={mockModels}
      />,
    );
    expect(screen.getByText('768')).toBeInTheDocument();
    expect(screen.getByText(/dimensions/i)).toBeInTheDocument();
  });

  it('shows the "no providers" warning and placeholder when no models are configured', () => {
    const onUpdate = vi.fn();
    render(<KnowledgePanel knowledge={defaults} onUpdate={onUpdate} allModels={[]} />);
    expect(screen.getByText(/Use server default/)).toBeInTheDocument();
    expect(screen.getByText(/No providers configured/i)).toBeInTheDocument();
  });
});
