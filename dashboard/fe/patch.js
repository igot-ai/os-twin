const fs = require('fs');
let content = fs.readFileSync('src/components/settings/KnowledgePanel.tsx', 'utf-8');

// The file now has `handleEmbedModelSelect` duplicated and messed up.
// Let's clean up lines 341-374 which contain the duplicated code.

content = content.replace(/const handleLlmModelSelect = \(modelId: string\) => {[\s\S]*?const handleEmbedModelSelect = \(compositeId: string\) => {[\s\S]*?setEmbedModelInput\(modelId\);\n  };/m, 
`const handleLlmModelSelect = (modelId: string) => {
    updateDraft({ knowledge_llm_model: modelId });
    setLlmModelInput(modelId);
  };

  const commitLlmModelInput = () => {
    if (llmModelInput !== draft.knowledge_llm_model) {
      updateDraft({ knowledge_llm_model: llmModelInput });
    }
  };

  // ── Embedding handlers ──────────────────────────────────────────────────

  const handleEmbedBackendChange = (backend: string) => {
    const suggestions = EMBEDDING_MODEL_SUGGESTIONS[backend] ?? [];
    const model = suggestions[0]?.model ?? '';
    updateDraft({
      knowledge_embedding_backend: backend as MemoryEmbeddingBackend | '',
      knowledge_embedding_model: model,
      knowledge_embedding_dimension: 768,
    });
    setEmbedModelInput(model);
  };

  const handleEmbedModelSelect = (modelId: string) => {
    updateDraft({ knowledge_embedding_model: modelId, knowledge_embedding_dimension: 768 });
    setEmbedModelInput(modelId);
  };`);

fs.writeFileSync('src/components/settings/KnowledgePanel.tsx', content);
