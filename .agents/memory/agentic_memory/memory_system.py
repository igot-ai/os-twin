import keyword
from typing import List, Dict, Optional, Any, Tuple
import uuid
from datetime import datetime
from .llm_controller import LLMController
from .retrievers import ChromaRetriever, ZvecRetriever
from .memory_note import MemoryNote  # canonical definition lives here now
import json
import logging
import numpy as np
import os
from abc import ABC, abstractmethod
import pickle
from pathlib import Path
import time

# Lazy imports for heavy ML libraries (torch, transformers, sentence-transformers, litellm)
# These take 6+ seconds to import and are not all needed for every backend.
SentenceTransformer = None
AutoModel = None
AutoTokenizer = None
word_tokenize = None
BM25Okapi = None
cosine_similarity = None
completion = None


def _ensure_ml_imports():
    """Import heavy ML libraries on first use."""
    global \
        SentenceTransformer, \
        AutoModel, \
        AutoTokenizer, \
        word_tokenize, \
        BM25Okapi, \
        cosine_similarity, \
        completion
    if completion is not None:
        return  # already imported
    from sentence_transformers import SentenceTransformer as _ST
    from transformers import AutoModel as _AM, AutoTokenizer as _AT
    from nltk.tokenize import word_tokenize as _wt
    from rank_bm25 import BM25Okapi as _BM
    from sklearn.metrics.pairwise import cosine_similarity as _cs
    from litellm import completion as _comp

    SentenceTransformer = _ST
    AutoModel = _AM
    AutoTokenizer = _AT
    word_tokenize = _wt
    BM25Okapi = _BM
    cosine_similarity = _cs
    completion = _comp


logger = logging.getLogger(__name__)

# MemoryNote moved to .memory_note (re-exported above) — single source of
# truth so lightweight consumers (dashboard, scripts) can import it without
# triggering the heavy retriever stack.


class AgenticMemorySystem:
    """Core memory system that manages memory notes and their evolution.

    This system provides:
    - Memory creation, retrieval, update, and deletion
    - Content analysis and metadata extraction
    - Memory evolution and relationship management
    - Hybrid search capabilities
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        llm_backend: str = "openai",
        llm_model: str = "gpt-4o-mini",
        evo_threshold: int = 100,
        api_key: Optional[str] = None,
        sglang_host: str = "http://localhost",
        sglang_port: int = 30000,
        persist_dir: Optional[str] = None,
        embedding_backend: str = "sentence-transformer",
        vector_backend: str = "zvec",
        context_aware_analysis: bool = False,
        context_aware_tree: bool = False,
        max_links: Optional[int] = None,
        similarity_weight: float = 0.8,
        decay_half_life_days: float = 30.0,
        conflict_resolution: str = "last_modified",
    ):
        """Initialize the memory system.

        Args:
            model_name: Name of the embedding model
            llm_backend: LLM backend to use (openai/ollama/sglang/gemini)
            llm_model: Name of the LLM model
            evo_threshold: Number of memories before triggering evolution
            api_key: API key for the LLM service
            sglang_host: Host URL for SGLang server (default: http://localhost)
            sglang_port: Port for SGLang server (default: 30000)
            persist_dir: Directory for persistent storage. If None, uses in-memory mode.
            embedding_backend: Embedding backend ("sentence-transformer" or "gemini")
            vector_backend: Vector database backend ("chroma" or "zvec")
            context_aware_analysis: When True, analyze_content sees similar memories
                and directory paths to keep naming/categorization consistent.
            context_aware_tree: When True (requires context_aware_analysis=True),
                include full directory tree in analysis context so LLM can see
                the complete knowledge structure for better linking and placement.
            max_links: Maximum number of links created per note during evolution.
                If None, no limit (LLM decides freely).
            similarity_weight: Weight for vector similarity in search ranking
                (α in the formula). Default 0.8. Time-decay weight = 1 - α.
            decay_half_life_days: Half-life in days for the time-decay function.
                After this many days, the recency score drops to 0.5. Default 30.
        """
        _ensure_ml_imports()
        self.memories = {}
        self.model_name = model_name
        self.persist_dir = persist_dir
        self.embedding_backend = embedding_backend
        self.vector_backend = vector_backend
        self.context_aware_analysis = context_aware_analysis
        self.context_aware_tree = context_aware_tree
        self.max_links = max_links
        self.similarity_weight = max(0.0, min(1.0, similarity_weight))
        self.decay_half_life_days = max(0.01, decay_half_life_days)
        self.conflict_resolution = conflict_resolution
        self._initialize_evolution_prompt()

        # Set up subdirectories for persistence
        self._notes_dir = None
        self._vector_dir = None
        if self.persist_dir:
            self._notes_dir = os.path.join(self.persist_dir, "notes")
            self._vector_dir = os.path.join(self.persist_dir, "vectordb")
            os.makedirs(self._notes_dir, exist_ok=True)
            os.makedirs(self._vector_dir, exist_ok=True)

        if not self.persist_dir and self.vector_backend == "chroma":
            # In-memory mode: reset old ChromaDB collection
            try:
                temp = ChromaRetriever(
                    collection_name="memories",
                    model_name=self.model_name,
                    embedding_backend=self.embedding_backend,
                )
                temp.client.reset()
            except Exception as e:
                logger.warning(f"Could not reset ChromaDB collection: {e}")

        self.retriever = self._create_retriever()

        if self.persist_dir:
            self._load_notes()

        # Initialize LLM controller
        self.llm_controller = LLMController(
            llm_backend, llm_model, api_key, sglang_host, sglang_port
        )
        self.evo_cnt = 0
        self.evo_threshold = evo_threshold

    def _create_retriever(self):
        """Create the vector retriever based on configured backend."""
        if self.vector_backend == "zvec":
            return ZvecRetriever(
                collection_name="memories",
                model_name=self.model_name,
                persist_dir=self._vector_dir,
                embedding_backend=self.embedding_backend,
            )
        else:
            return ChromaRetriever(
                collection_name="memories",
                model_name=self.model_name,
                persist_dir=self._vector_dir,
                embedding_backend=self.embedding_backend,
            )

    # --- Persistence helpers ---

    def _save_note(self, note: MemoryNote, touch_modified: bool = True):
        """Save a single MemoryNote as a markdown file in its directory tree.

        Filepath collision handling:
        - Same UUID → normal overwrite (update in place).
        - Different UUID, same hash → true duplicate, skip the write.
        - Different UUID, different hash → real conflict. Resolved by
          ``last_modified`` (or LLM if configured). The loser's file
          stays untouched; the winner is written.

        Args:
            note: The note to persist.
            touch_modified: When True (default) update ``last_modified`` to now.
                Pass False when writing a note whose timestamp should be
                preserved (e.g. during merge when the disk version wins).
        """
        if not self._notes_dir:
            return
        if touch_modified:
            from datetime import datetime

            note.last_modified = datetime.now().strftime("%Y%m%d%H%M")

        # Refresh the hash so it reflects current content/metadata
        note.refresh_hash()

        filepath = os.path.join(self._notes_dir, note.filepath)

        # Check for filepath collision with a different note
        if os.path.exists(filepath):
            try:
                existing = MemoryNote.from_markdown(
                    open(filepath, "r", encoding="utf-8").read()
                )
                if existing.id != note.id:
                    if existing.content_hash == note.content_hash:
                        # True duplicate — same content, skip write
                        logger.info(
                            "skip duplicate: note %s has same hash as %s at %s",
                            note.id,
                            existing.id,
                            filepath,
                        )
                        return
                    # Real conflict — different content at same filepath
                    winner = self._resolve_conflict(note, existing)
                    if winner.id != note.id:
                        # Existing file wins, don't overwrite
                        logger.info(
                            "filepath conflict: existing note %s wins over %s at %s",
                            existing.id,
                            note.id,
                            filepath,
                        )
                        return
                    logger.info(
                        "filepath conflict: new note %s wins over %s at %s",
                        note.id,
                        existing.id,
                        filepath,
                    )
            except Exception:
                pass  # Can't parse existing file — safe to overwrite

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(note.to_markdown())

    def _resolve_conflict(self, note_a: MemoryNote, note_b: MemoryNote) -> MemoryNote:
        """Pick the winner between two conflicting notes.

        Strategy depends on ``self.conflict_resolution``:
        - ``"last_modified"`` (default): newer ``last_modified`` wins.
          Ties go to note_a (the incoming/newer write attempt).
        - ``"llm"``: asks the LLM to merge both versions into one.
          The merged note keeps note_a's ID. Falls back to
          ``last_modified`` if the LLM call fails.
        """
        if self.conflict_resolution == "llm":
            try:
                return self._llm_resolve_conflict(note_a, note_b)
            except Exception:
                logger.exception(
                    "LLM conflict resolution failed for %s vs %s, "
                    "falling back to last_modified",
                    note_a.id,
                    note_b.id,
                )

        # last_modified strategy (also the fallback)
        ts_a = note_a.last_modified or note_a.timestamp
        ts_b = note_b.last_modified or note_b.timestamp

        if ts_a >= ts_b:
            return note_a
        return note_b

    def _llm_resolve_conflict(
        self, note_a: MemoryNote, note_b: MemoryNote
    ) -> MemoryNote:
        """Use the LLM to merge two conflicting notes into one.

        The merged note keeps note_a's ID and has its ``last_modified``
        set to now.
        """
        from datetime import datetime

        prompt = (
            "Two versions of the same memory note exist with different content. "
            "Merge them into a single, comprehensive version that preserves all "
            "unique information from both. Return ONLY the merged content text, "
            "no headers or metadata.\n\n"
            f"--- Version A (modified: {note_a.last_modified}) ---\n"
            f"{note_a.content}\n\n"
            f"--- Version B (modified: {note_b.last_modified}) ---\n"
            f"{note_b.content}\n"
        )

        response = self.llm_controller.llm.get_completion(prompt)
        merged_content = response.strip() if response else None
        if not merged_content:
            raise ValueError("LLM returned empty merge result")

        logger.info(
            "LLM merged conflict for notes %s and %s (%d + %d → %d chars)",
            note_a.id,
            note_b.id,
            len(note_a.content),
            len(note_b.content),
            len(merged_content),
        )

        # Build merged note: keep note_a's identity, combine metadata
        merged = MemoryNote(
            content=merged_content,
            id=note_a.id,
            name=note_a.name or note_b.name,
            path=note_a.path or note_b.path,
            keywords=list(set(note_a.keywords + note_b.keywords)),
            links=list(set(note_a.links + note_b.links)),
            tags=list(set(note_a.tags + note_b.tags)),
            context=note_a.context if note_a.context != "General" else note_b.context,
            timestamp=min(note_a.timestamp, note_b.timestamp),
            last_modified=datetime.now().strftime("%Y%m%d%H%M"),
            summary=None,  # will be regenerated on next LLM analysis
        )
        merged.refresh_hash()
        return merged

    def _delete_note_file(self, memory_id: str):
        """Delete a MemoryNote's markdown file and clean up empty parent dirs."""
        if not self._notes_dir:
            return
        note = self.memories.get(memory_id)
        if note:
            filepath = os.path.join(self._notes_dir, note.filepath)
            if os.path.exists(filepath):
                os.remove(filepath)
                # Clean up empty parent directories
                parent = os.path.dirname(filepath)
                while parent != self._notes_dir:
                    if os.path.isdir(parent) and not os.listdir(parent):
                        os.rmdir(parent)
                        parent = os.path.dirname(parent)
                    else:
                        break

    def _load_notes(self):
        """Load all MemoryNotes from markdown files in the notes directory tree."""
        if not self._notes_dir:
            return
        for dirpath, _dirnames, filenames in os.walk(self._notes_dir):
            for filename in filenames:
                if not filename.endswith(".md"):
                    continue
                filepath = os.path.join(dirpath, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()
                try:
                    note = MemoryNote.from_markdown(text)
                    self.memories[note.id] = note
                except Exception as e:
                    logger.warning(f"Could not load note {filepath}: {e}")

        # Rebuild backlinks from links (backlinks are never persisted)
        self._rebuild_backlinks()

    def _rebuild_backlinks(self):
        """Derive all backlinks from forward links. Also prunes dead links."""
        # Clear all backlinks
        for note in self.memories.values():
            note.backlinks = []

        # Rebuild: if A.links contains B, then B.backlinks gets A
        for note in self.memories.values():
            valid_links = []
            for linked_id in note.links:
                if linked_id in self.memories:
                    valid_links.append(linked_id)
                    self.memories[linked_id].backlinks.append(note.id)
            # Prune links to notes that no longer exist
            if len(valid_links) != len(note.links):
                note.links = valid_links
                self._save_note(note)

        self._initialize_evolution_prompt()

    def _initialize_evolution_prompt(self):
        """Initialize the prompt used by the memory evolution flow."""
        self._evolution_system_prompt = """
                                You are an AI memory evolution agent responsible for managing and evolving a knowledge base.
                                Analyze the the new memory note according to keywords and context, also with their several nearest neighbors memory.
                                Make decisions about its evolution.

                                The new memory context:
                                {context}
                                content: {content}
                                keywords: {keywords}

                                The nearest neighbors memories (each line starts with memory_id):
                                {nearest_neighbors_memories}

                                Based on this information, determine:
                                1. Should this memory be evolved? Consider its relationships with other memories.
                                2. What specific actions should be taken (strengthen, update_neighbor)?
                                   2.1 If choose to strengthen the connection, which memory should it be connected to? Use the memory_id from the neighbors above. Can you give the updated tags of this memory?
                                   2.2 If choose to update_neighbor, you can update the context and tags of these memories based on the understanding of these memories. If the context and the tags are not updated, the new context and tags should be the same as the original ones. Generate the new context and tags in the sequential order of the input neighbors.
                                Tags should be determined by the content of these characteristic of these memories, which can be used to retrieve them later and categorize them.
                                Note that the length of new_tags_neighborhood must equal the number of input neighbors, and the length of new_context_neighborhood must equal the number of input neighbors.
                                The number of neighbors is {neighbor_number}.
                                Return your decision in JSON format with the following structure:
                                {{
                                    "should_evolve": True or False,
                                    "actions": ["strengthen", "update_neighbor"],
                                    "suggested_connections": ["memory_id_1", "memory_id_2", ...],
                                    "tags_to_update": ["tag_1",..."tag_n"],
                                    "new_context_neighborhood": ["new context",...,"new context"],
                                    "new_tags_neighborhood": [["tag_1",...,"tag_n"],...["tag_1",...,"tag_n"]],
                                }}
                                """

    # Approximate word count threshold for generating summary.
    # all-MiniLM-L6-v2 supports 256 tokens; enhanced_document appends
    # gemini embedding truncates to 512 tokens. To leave room for metadata like
    # context/keywords/tags, so we reserve ~100 tokens for metadata
    # and use ~250 words as the content threshold.
    SUMMARY_WORD_THRESHOLD = 250

    def tree(self) -> str:
        """Generate a tree-like string of the memory directory structure."""
        if not self.memories:
            return "(empty)"

        root = self._build_filepath_tree()
        return "\n".join(self._render_tree(root))

    def _build_filepath_tree(self) -> dict:
        """Build a nested dict from all note filepaths."""
        root: dict = {}
        for mem in sorted(self.memories.values(), key=lambda m: m.filepath):
            parts = mem.filepath.split(os.sep)
            node = root
            for part in parts:
                node = node.setdefault(part, {})
        return root

    @staticmethod
    def _render_tree(node: dict, prefix: str = "") -> List[str]:
        """Render a nested dict as a tree-like list of strings."""
        lines: List[str] = []
        items = list(node.items())
        for i, (name, children) in enumerate(items):
            last = i == len(items) - 1
            connector = "└── " if last else "├── "
            lines.append(f"{prefix}{connector}{name}")
            if children:
                extension = "    " if last else "│   "
                lines.extend(
                    AgenticMemorySystem._render_tree(children, prefix + extension)
                )
        return lines

    def _get_existing_context(self, content: str, include_tree: bool = False) -> str:
        """Collect context from similar memories and existing directory structure.

        Args:
            content: The note content to find similar memories for.
            include_tree: If True, include full directory tree in context.
        """
        if not self.memories:
            return ""

        lines = []
        self._append_similar_memories_context(content, lines)
        self._append_directory_context(include_tree, lines)
        return "\n            ".join(lines)

    def _append_similar_memories_context(self, content: str, lines: list) -> None:
        """Search for similar memories and append context lines."""
        try:
            results = self.retriever.search(content, k=5)
            ids = results.get("ids", [[]])[0]
            if not ids:
                return
            similar = []
            similar_tags: set = set()
            for doc_id in ids:
                mem = self.memories.get(doc_id)
                if mem:
                    similar.append(f"{mem.name} (path: {mem.path})")
                    similar_tags.update(mem.tags)
            if similar:
                lines.append(f"Similar memories: {', '.join(similar)}")
            if similar_tags:
                lines.append(f"Their tags: {', '.join(sorted(similar_tags)[:15])}")
        except Exception as exc:
            logger.debug("Vector search during context collection failed: %s", exc)

    def _append_directory_context(self, include_tree: bool, lines: list) -> None:
        """Append directory structure context lines."""
        if include_tree:
            lines.append(f"Full memory tree:\n{self.tree()}")
            return
        all_paths = sorted({m.path for m in self.memories.values() if m.path})
        if all_paths:
            tree_paths = sorted({"/".join(p.split("/")[:2]) for p in all_paths})
            lines.append(f"Existing directory tree: {', '.join(tree_paths)}")

    def analyze_content(self, content: str) -> Dict:
        """Analyze content using LLM to extract semantic metadata.

        Uses a language model to understand the content and extract:
        - Keywords: Important terms and concepts
        - Context: Overall domain or theme
        - Tags: Classification categories
        - Summary: A concise summary when content exceeds the embedding token limit

        Args:
            content (str): The text content to analyze

        Returns:
            Dict: Contains extracted metadata with keys:
                - keywords: List[str]
                - context: str
                - tags: List[str]
                - summary: Optional[str] (only when content is long)
        """
        needs_summary = len(content.split()) > self.SUMMARY_WORD_THRESHOLD

        summary_instruction = ""
        summary_schema = {}
        if needs_summary:
            summary_instruction = """
            4. Writing a concise summary (2-3 sentences, under 100 words) that captures
               the key information. This summary will be used for semantic search embedding,
               so it must preserve the most important concepts and terms."""
            summary_schema = {
                "summary": {
                    "type": "string",
                }
            }

        context_section = ""
        if self.context_aware_analysis:
            existing = self._get_existing_context(
                content, include_tree=self.context_aware_tree
            )
            if existing:
                context_section = f"""
            IMPORTANT - Existing knowledge base context:
            {existing}
            Reuse existing paths and tags when the content fits. Only create new ones
            if no existing option is appropriate. Keep naming consistent."""

        prompt = f"""Generate a structured analysis of the following content by:
            1. Creating a short, descriptive name (2-5 words, lowercase, like a file name)
            2. Creating a directory path that categorizes this content in a knowledge tree
            3. Identifying the most salient keywords (focus on nouns, verbs, and key concepts)
            4. Extracting core themes and contextual elements
            5. Creating relevant categorical tags
            {summary_instruction}
            {context_section}

            Format the response as a JSON object:
            {{
                "name":
                    // a short descriptive name for this memory (2-5 words, lowercase)
                    // e.g. "docker container basics", "postgresql jsonb indexing"
                ,
                "path":
                    // a directory path (2-4 levels, lowercase) that places this memory
                    // in a logical knowledge tree. Use broad domain first, then narrow topic.
                    // e.g. "devops/containerization", "backend/database",
                    //      "backend/middleware/auth", "ml/nlp", "devops/ci-cd"
                    // Keep segments short (1-2 words each), consistent, and reusable.
                ,
                "keywords": [
                    // several specific, distinct keywords that capture key concepts and terminology
                    // Order from most to least important
                    // Don't include keywords that are the name of the speaker or time
                    // At least three keywords, but don't be too redundant.
                ],
                "context":
                    // one sentence summarizing:
                    // - Main topic/domain
                    // - Key arguments/points
                    // - Intended audience/purpose
                ,
                "tags": [
                    // several broad categories/themes for classification
                    // Include domain, format, and type tags
                    // At least three tags, but don't be too redundant.
                ]{', "summary": "..."' if needs_summary else ""}
            }}

            Content for analysis:
            {content}"""

        schema_properties = {
            "name": {
                "type": "string",
            },
            "path": {
                "type": "string",
            },
            "keywords": {"type": "array", "items": {"type": "string"}},
            "context": {
                "type": "string",
            },
            "tags": {"type": "array", "items": {"type": "string"}},
        }
        schema_properties.update(summary_schema)

        try:
            response = self.llm_controller.llm.get_completion(
                prompt,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": {"type": "object", "properties": schema_properties},
                    },
                },
            )
            return json.loads(response)
        except Exception as e:
            print(f"Error analyzing content: {e}")
            return {"keywords": [], "context": "General", "tags": []}

    def _apply_llm_analysis(self, note: MemoryNote) -> None:
        """Run LLM analysis on a note and fill in missing metadata."""
        needs_analysis = not note.keywords or note.context == "General" or not note.tags
        if not needs_analysis:
            return

        analysis = self.analyze_content(note.content)
        if note.name is None:
            note.name = analysis.get("name")
        if note.path is None:
            note.path = analysis.get("path")
        if not note.keywords:
            note.keywords = self._coerce_str_list(analysis.get("keywords", []))
        if note.context == "General":
            ctx = analysis.get("context", "General")
            note.context = ctx if isinstance(ctx, str) else str(ctx)
        if not note.tags:
            note.tags = self._coerce_str_list(analysis.get("tags", []))
        if note.summary is None:
            note.summary = analysis.get("summary")

    @staticmethod
    def _build_note_metadata(note: MemoryNote) -> dict:
        """Build a metadata dict suitable for the vector store."""
        return {
            "id": note.id,
            "content_hash": note.content_hash,
            "content": note.content,
            "keywords": note.keywords,
            "links": note.links,
            "retrieval_count": note.retrieval_count,
            "timestamp": note.timestamp,
            "last_accessed": note.last_accessed,
            "context": note.context,
            "evolution_history": note.evolution_history,
            "category": note.category,
            "tags": note.tags,
            "summary": note.summary,
        }

    def add_note(self, content: str, time: Optional[str] = None, **kwargs) -> str:
        """Add a new memory note"""
        if time is not None:
            kwargs["timestamp"] = time
        note = MemoryNote(content=content, **kwargs)

        self._apply_llm_analysis(note)

        # Add to memories before evolution so add_link can find it
        self.memories[note.id] = note
        evo_label, note = self.process_memory(note)
        self._save_note(note)

        metadata = self._build_note_metadata(note)
        self.retriever.add_document(note.content, metadata, note.id)

        if evo_label is True:
            self.evo_cnt += 1
            if self.evo_cnt % self.evo_threshold == 0:
                self.consolidate_memories()
        return note.id

    # --- Disk ↔ Memory helpers ---

    def _load_disk_notes(self) -> Dict[str, MemoryNote]:
        """Read every ``.md`` file under ``notes/`` and return {id: note}."""
        disk_notes: Dict[str, MemoryNote] = {}
        if not self._notes_dir:
            return disk_notes
        for dirpath, _dirnames, filenames in os.walk(self._notes_dir):
            for filename in filenames:
                if not filename.endswith(".md"):
                    continue
                filepath = os.path.join(dirpath, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()
                try:
                    note = MemoryNote.from_markdown(text)
                    disk_notes[note.id] = note
                except Exception as e:
                    logger.warning("Could not load note %s: %s", filepath, e)
        return disk_notes

    # --- Bidirectional merge ---

    def merge_from_disk(self) -> Dict:
        """Bidirectional merge between on-disk notes and in-memory state.

        Reconciliation rules
        --------------------
        1. **On disk only** → add to ``self.memories`` + vectordb.
        2. **In memory only** → keep (caller writes to disk afterwards).
        3. **Both exist, same content** → skip (already consistent).
        4. **Both exist, different content** → the version with the latest
           ``last_modified`` wins. The loser is overwritten. Ties keep the
           disk version (external edits are assumed intentional).

        Unlike the old ``sync_from_disk``, this method **never deletes**
        notes that exist only in memory (they were created by the current
        process and just haven't been written yet). And it does **not** do
        a full vectordb rebuild — only the notes that actually changed get
        their embeddings updated.

        Returns:
            Dict with counts: added_from_disk, updated_from_disk,
            updated_from_memory, unchanged, memory_only.
        """
        if not self._notes_dir:
            return {"error": "No persist_dir configured"}

        disk_notes = self._load_disk_notes()

        added_from_disk = 0
        updated_from_disk = 0  # disk won the conflict
        updated_from_memory = 0  # memory won the conflict
        unchanged = 0
        memory_only = 0

        disk_ids = set(disk_notes.keys())
        mem_ids = set(self.memories.keys())

        # 1. Notes on disk but not in memory → adopt from disk
        for nid in disk_ids - mem_ids:
            disk_note = disk_notes[nid]
            self.memories[nid] = disk_note
            metadata = self._build_note_metadata(disk_note)
            self.retriever.add_document(disk_note.content, metadata, nid)
            added_from_disk += 1

        # 2. Notes in memory but not on disk → keep (no action needed here,
        #    sync_to_disk will write them later)
        memory_only = len(mem_ids - disk_ids)

        # 3/4. Notes that exist in both — compare by hash, not raw content
        for nid in disk_ids & mem_ids:
            disk_note = disk_notes[nid]
            mem_note = self.memories[nid]

            if disk_note.content_hash == mem_note.content_hash:
                unchanged += 1
                continue

            # Conflict: use _resolve_conflict (last_modified or LLM)
            # disk_note is note_a so ties go to disk (external edits
            # are assumed intentional)
            winner = self._resolve_conflict(disk_note, mem_note)
            if winner.id == mem_note.id and winner is mem_note:
                # Memory wins — keep in-memory version, will be written
                # to disk by sync_to_disk. No vectordb change needed.
                updated_from_memory += 1
            else:
                # Disk wins — adopt disk version
                self.memories[nid] = disk_note
                # Update vectordb entry
                self.retriever.delete_document(nid)
                metadata = self._build_note_metadata(disk_note)
                self.retriever.add_document(disk_note.content, metadata, nid)
                updated_from_disk += 1

        self._rebuild_backlinks()

        # 5. Verify vectordb ↔ notes consistency using content_hash.
        #    For each note, check if vectordb has the same hash. Three cases:
        #    - Missing from vectordb entirely → embed and insert
        #    - Hash mismatch (stale vector) → re-embed
        #    - Hash matches → consistent, skip
        all_mem_ids = list(self.memories.keys())
        stored_hashes = self.retriever.get_stored_hashes(all_mem_ids)
        vectors_repaired = 0
        for nid in all_mem_ids:
            note = self.memories[nid]
            stored_hash = stored_hashes.get(nid)

            if stored_hash == note.content_hash:
                continue  # consistent

            if stored_hash is None:
                logger.warning("merge: note %s missing from vectordb, adding", nid)
            else:
                logger.warning(
                    "merge: note %s has stale vector (hash %s vs %s), re-embedding",
                    nid,
                    stored_hash,
                    note.content_hash,
                )
                self.retriever.delete_document(nid)

            metadata = self._build_note_metadata(note)
            self.retriever.add_document(note.content, metadata, nid)
            vectors_repaired += 1

        return {
            "added_from_disk": added_from_disk,
            "updated_from_disk": updated_from_disk,
            "updated_from_memory": updated_from_memory,
            "unchanged": unchanged,
            "memory_only": memory_only,
            "vectors_repaired": vectors_repaired,
        }

    # --- One-directional syncs (kept for backwards compat) ---

    def sync_from_disk(self) -> Dict:
        """Sync: read current persistent files → update in-memory state + vectordb.

        Loads all markdown files from disk, detects added/modified/deleted notes
        compared to current in-memory state, and rebuilds the vector index.

        Caveats:
        - Notes that exist on disk but not in memory are ADDED.
        - Notes that exist in memory but not on disk are REMOVED.
        - Notes whose content differs on disk are UPDATED (disk wins).
        - Vector index is fully rebuilt after sync.
        - Backlinks are rebuilt from forward links.

        Returns:
            Dict with counts of added, updated, removed notes.
        """
        if not self._notes_dir:
            return {"error": "No persist_dir configured"}

        disk_notes = self._load_disk_notes()

        added = 0
        updated = 0
        removed = 0

        # Detect added and updated
        for nid, disk_note in disk_notes.items():
            if nid not in self.memories:
                added += 1
            elif disk_note.content != self.memories[nid].content:
                updated += 1
            self.memories[nid] = disk_note

        # Detect removed (in memory but not on disk)
        removed_ids = [nid for nid in self.memories if nid not in disk_notes]
        for nid in removed_ids:
            del self.memories[nid]
            removed += 1

        # Rebuild backlinks and vector index
        self._rebuild_backlinks()
        self.consolidate_memories()

        return {"added": added, "updated": updated, "removed": removed}

    def sync_to_disk(self) -> Dict:
        """Sync: merge disk state, then write unified state to disk.

        1. Calls ``merge_from_disk()`` to reconcile disk ↔ memory.
        2. Writes all in-memory notes to disk.
        3. Does **not** delete orphan files (they may belong to another
           agent process running concurrently).

        Returns:
            Dict with merge result and count of files written.
        """
        if not self._notes_dir:
            return {"error": "No persist_dir configured"}

        # Step 1: merge first so we don't clobber another agent's work
        merge_result = self.merge_from_disk()

        # Step 2: write all in-memory notes (now includes merged disk notes)
        written = 0
        for note in self.memories.values():
            self._save_note(note, touch_modified=False)
            written += 1

        return {
            "merge": merge_result,
            "written": written,
        }

    def _remove_orphan_files(self, orphans: set) -> None:
        """Delete orphan markdown files and clean up empty parent directories."""
        for orphan_path in orphans:
            os.remove(orphan_path)
            parent = os.path.dirname(orphan_path)
            while parent != self._notes_dir:
                if os.path.isdir(parent) and not os.listdir(parent):
                    os.rmdir(parent)
                    parent = os.path.dirname(parent)
                else:
                    break

    def consolidate_memories(self):
        """Consolidate memories: rebuild the vector index from current in-memory state."""
        self.retriever.clear()

        # Re-add all memory documents with their complete metadata
        for memory in self.memories.values():
            metadata = {
                "id": memory.id,
                "content": memory.content,
                "keywords": memory.keywords,
                "links": memory.links,
                "retrieval_count": memory.retrieval_count,
                "timestamp": memory.timestamp,
                "last_accessed": memory.last_accessed,
                "context": memory.context,
                "evolution_history": memory.evolution_history,
                "category": memory.category,
                "tags": memory.tags,
                "summary": memory.summary,
            }
            self.retriever.add_document(memory.content, metadata, memory.id)

    def find_related_memories(self, query: str, k: int = 5) -> Tuple[str, List[str]]:
        """Find related memories using ChromaDB retrieval

        Returns:
            Tuple[str, List[str]]: (formatted_memory_string, list_of_memory_ids)
        """
        if not self.memories:
            return "", []

        try:
            # Get results from ChromaDB
            results = self.retriever.search(query, k)

            # Convert to list of memories
            memory_str = ""
            memory_ids = []

            if (
                "ids" in results
                and results["ids"]
                and len(results["ids"]) > 0
                and len(results["ids"][0]) > 0
            ):
                for i, doc_id in enumerate(results["ids"][0]):
                    # Get metadata from ChromaDB results
                    if i < len(results["metadatas"][0]):
                        metadata = results["metadatas"][0][i]
                        # Format memory string with actual memory ID
                        memory_str += f"memory_id:{doc_id}\ttalk start time:{metadata.get('timestamp', '')}\tmemory content: {metadata.get('content', '')}\tmemory context: {metadata.get('context', '')}\tmemory keywords: {str(metadata.get('keywords', []))}\tmemory tags: {str(metadata.get('tags', []))}\n"
                        memory_ids.append(doc_id)

            return memory_str, memory_ids
        except Exception as e:
            logger.error(f"Error in find_related_memories: {str(e)}")
            return "", []

    def find_related_memories_raw(self, query: str, k: int = 5) -> str:
        """Find related memories using ChromaDB retrieval in raw format"""
        if not self.memories:
            return ""

        results = self.retriever.search(query, k)
        if "ids" not in results or not results["ids"] or len(results["ids"]) == 0:
            return ""

        parts: list = []
        for i, doc_id in enumerate(results["ids"][0][:k]):
            if i >= len(results["metadatas"][0]):
                continue
            metadata = results["metadatas"][0][i]
            parts.append(self._format_memory_raw(metadata))
            self._append_linked_raw(metadata.get("links", []), k, parts)
        return "".join(parts)

    @staticmethod
    def _format_memory_raw(metadata: dict) -> str:
        """Format a single memory metadata dict as a raw-text line."""
        return (
            f"talk start time:{metadata.get('timestamp', '')}\t"
            f"memory content: {metadata.get('content', '')}\t"
            f"memory context: {metadata.get('context', '')}\t"
            f"memory keywords: {str(metadata.get('keywords', []))}\t"
            f"memory tags: {str(metadata.get('tags', []))}\n"
        )

    def _append_linked_raw(self, links: list, k: int, parts: list) -> None:
        """Append raw-text lines for linked neighbor memories."""
        j = 0
        for link_id in links:
            if link_id in self.memories and j < k:
                neighbor = self.memories[link_id]
                parts.append(
                    f"talk start time:{neighbor.timestamp}\t"
                    f"memory content: {neighbor.content}\t"
                    f"memory context: {neighbor.context}\t"
                    f"memory keywords: {str(neighbor.keywords)}\t"
                    f"memory tags: {str(neighbor.tags)}\n"
                )
                j += 1

    def read(self, memory_id: str) -> Optional[MemoryNote]:
        """Retrieve a memory note by its ID.

        Args:
            memory_id (str): ID of the memory to retrieve

        Returns:
            MemoryNote if found, None otherwise
        """
        return self.memories.get(memory_id)

    def update(self, memory_id: str, **kwargs) -> bool:
        """Update a memory note.

        When content changes, all LLM-derived metadata (name, keywords, context,
        tags, summary) is re-generated. The old markdown file is removed if the
        filename changes.

        Args:
            memory_id: ID of memory to update
            **kwargs: Fields to update

        Returns:
            bool: True if update successful
        """
        if memory_id not in self.memories:
            return False

        note = self.memories[memory_id]
        old_filepath = note.filepath

        # Update fields
        for key, value in kwargs.items():
            if hasattr(note, key):
                setattr(note, key, value)

        # Re-analyze all metadata when content changes
        if "content" in kwargs:
            self._reanalyze_note_metadata(note, kwargs)

        # Delete old markdown file if filepath changed
        self._cleanup_old_note_file(old_filepath, note.filepath)

        # Update in ChromaDB
        metadata = self._build_note_metadata(note)
        self.retriever.delete_document(memory_id)
        self.retriever.add_document(
            document=note.content, metadata=metadata, doc_id=memory_id
        )
        self._save_note(note)

        return True

    def _reanalyze_note_metadata(self, note: MemoryNote, kwargs: dict) -> None:
        """Re-generate LLM-derived fields that were not explicitly provided."""
        analysis = self.analyze_content(note.content)
        if "name" not in kwargs:
            note.name = analysis.get("name", note.name)
        if "path" not in kwargs:
            note.path = analysis.get("path", note.path)
        if "keywords" not in kwargs:
            note.keywords = analysis.get("keywords", note.keywords)
        if "context" not in kwargs:
            note.context = analysis.get("context", note.context)
        if "tags" not in kwargs:
            note.tags = analysis.get("tags", note.tags)
        if "summary" not in kwargs:
            note.summary = analysis.get("summary")

    def _cleanup_old_note_file(self, old_filepath: str, new_filepath: str) -> None:
        """Remove old markdown file and empty parent dirs if filepath changed."""
        if not self._notes_dir or old_filepath == new_filepath:
            return
        old_full_path = os.path.join(self._notes_dir, old_filepath)
        if not os.path.exists(old_full_path):
            return
        os.remove(old_full_path)
        parent = os.path.dirname(old_full_path)
        while parent != self._notes_dir:
            if os.path.isdir(parent) and not os.listdir(parent):
                os.rmdir(parent)
                parent = os.path.dirname(parent)
            else:
                break

    def add_link(self, from_id: str, to_id: str):
        """Create a forward link from one note to another. Backlink is auto-created."""
        if from_id not in self.memories or to_id not in self.memories:
            return
        from_note = self.memories[from_id]
        to_note = self.memories[to_id]
        if to_id not in from_note.links:
            from_note.links.append(to_id)
            self._save_note(from_note)
        if from_id not in to_note.backlinks:
            to_note.backlinks.append(from_id)

    def remove_link(self, from_id: str, to_id: str):
        """Remove a forward link. Backlink is auto-removed."""
        if from_id not in self.memories or to_id not in self.memories:
            return
        from_note = self.memories[from_id]
        to_note = self.memories[to_id]
        if to_id in from_note.links:
            from_note.links.remove(to_id)
            self._save_note(from_note)
        if from_id in to_note.backlinks:
            to_note.backlinks.remove(from_id)

    def delete(self, memory_id: str) -> bool:
        """Delete a memory note by its ID.

        Args:
            memory_id (str): ID of the memory to delete

        Returns:
            bool: True if memory was deleted, False if not found
        """
        if memory_id in self.memories:
            note = self.memories[memory_id]

            # Clean up all links/backlinks via interface
            for linked_id in note.links[:]:
                self.remove_link(memory_id, linked_id)
            for backlinked_id in note.backlinks[:]:
                self.remove_link(backlinked_id, memory_id)

            # Delete markdown file first (needs note for filename)
            self._delete_note_file(memory_id)
            # Delete from ChromaDB
            self.retriever.delete_document(memory_id)
            # Delete from local storage
            del self.memories[memory_id]
            return True
        return False

    def _search_raw(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Internal search method that returns raw results from ChromaDB.

        This is used internally by the memory evolution system to find
        related memories for potential evolution.

        Args:
            query (str): The search query text
            k (int): Maximum number of results to return

        Returns:
            List[Dict[str, Any]]: Raw search results from ChromaDB
        """
        results = self.retriever.search(query, k)
        return [
            {"id": doc_id, "score": score}
            for doc_id, score in zip(results["ids"][0], results["distances"][0])
        ]

    def _compute_time_decay_score(self, similarity: float, last_accessed: str) -> float:
        """Compute combined score using time-decay re-ranking.

        Formula: score = α * sim + (1 - α) * 0.5^(age_days / h)

        Where:
            α   = self.similarity_weight (default 0.8)
            sim = normalized cosine similarity [0, 1]
            age_days = days since last_accessed
            h   = self.decay_half_life_days (default 7)
        """
        from datetime import datetime

        # Normalize similarity to [0, 1].
        # Zvec cosine returns 0..1 (higher = more similar).
        # ChromaDB returns distance (lower = more similar), so invert.
        sim = max(0.0, min(1.0, similarity))

        # Parse last_accessed (format: YYYYMMDDHHMM)
        try:
            last_dt = datetime.strptime(last_accessed, "%Y%m%d%H%M")
            age_days = max(0.0, (datetime.now() - last_dt).total_seconds() / 86400.0)
        except (ValueError, TypeError):
            age_days = 0.0  # unknown → treat as fresh

        recency = 0.5 ** (age_days / self.decay_half_life_days)
        return self.similarity_weight * sim + (1 - self.similarity_weight) * recency

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for memories using vector similarity with time-decay re-ranking.

        Retrieves 2*k candidates from the vector store, then re-ranks them using:
            score = α * cosine_sim + (1 - α) * 0.5^(age_days / half_life)

        Returns the top-k results sorted by combined score (descending).
        """
        # Fetch extra candidates to allow re-ranking to surface recent notes
        fetch_k = max(k * 2, 10)
        search_results = self.retriever.search(query, fetch_k)
        memories = []

        # Process results and compute combined scores
        for i, doc_id in enumerate(search_results["ids"][0]):
            memory = self.memories.get(doc_id)
            if memory:
                raw_sim = search_results["distances"][0][i]
                combined_score = self._compute_time_decay_score(
                    raw_sim, memory.last_accessed
                )
                memories.append(
                    {
                        "id": doc_id,
                        "content": memory.content,
                        "context": memory.context,
                        "keywords": memory.keywords,
                        "tags": memory.tags,
                        "score": combined_score,
                        "similarity": raw_sim,
                    }
                )

        # Re-rank by combined score (highest first)
        memories.sort(key=lambda m: m["score"], reverse=True)

        # Update last_accessed for returned results
        now = datetime.now().strftime("%Y%m%d%H%M")
        for m in memories[:k]:
            note = self.memories.get(m["id"])
            if note:
                note.last_accessed = now
                note.retrieval_count += 1

        return memories[:k]

    def _search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for memories using a hybrid retrieval approach.

        This method combines results from both:
        1. ChromaDB vector store (semantic similarity)
        2. Embedding-based retrieval (dense vectors)

        The results are deduplicated and ranked by relevance.

        Args:
            query (str): The search query text
            k (int): Maximum number of results to return

        Returns:
            List[Dict[str, Any]]: List of search results, each containing:
                - id: Memory ID
                - content: Memory content
                - context: Memory context
                - keywords: Memory keywords
                - tags: Memory tags
                - score: Similarity score
        """
        # Get results from ChromaDB
        chroma_results = self.retriever.search(query, k)
        memories = []

        # Process ChromaDB results
        for i, doc_id in enumerate(chroma_results["ids"][0]):
            memory = self.memories.get(doc_id)
            if memory:
                memories.append(
                    {
                        "id": doc_id,
                        "content": memory.content,
                        "context": memory.context,
                        "keywords": memory.keywords,
                        "tags": memory.tags,
                        "score": chroma_results["distances"][0][i],
                    }
                )

        # Get results from embedding retriever
        embedding_results = self.retriever.search(query, k)

        # Combine results with deduplication
        seen_ids = {m["id"] for m in memories}
        for result in embedding_results:
            memory_id = result.get("id")
            if memory_id and memory_id not in seen_ids:
                memory = self.memories.get(memory_id)
                if memory:
                    memories.append(
                        {
                            "id": memory_id,
                            "content": memory.content,
                            "context": memory.context,
                            "keywords": memory.keywords,
                            "tags": memory.tags,
                            "score": result.get("score", 0.0),
                        }
                    )
                    seen_ids.add(memory_id)

        return memories[:k]

    def search_agentic(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for memories using vector retrieval with link-following and time-decay."""
        if not self.memories:
            return []

        try:
            fetch_k = max(k * 2, 10)
            results = self.retriever.search(query, fetch_k)
            if not self._has_valid_ids(results):
                return []

            memories: List[Dict[str, Any]] = []
            seen_ids: set = set()
            self._collect_search_results(results, k * 2, memories, seen_ids)
            self._collect_neighbor_results(memories, seen_ids, k)

            # Apply time-decay re-ranking to all collected results
            for m in memories:
                note = self.memories.get(m["id"])
                raw_sim = m.get("score", 0.0)
                if note:
                    m["score"] = self._compute_time_decay_score(
                        raw_sim, note.last_accessed
                    )
                    m["similarity"] = raw_sim

            memories.sort(key=lambda m: m.get("score", 0), reverse=True)
            return memories[:k]
        except Exception as e:
            logger.error(f"Error in search_agentic: {e}")
            return []

    @staticmethod
    def _has_valid_ids(results: dict) -> bool:
        """Check whether retriever results contain at least one ID."""
        return (
            "ids" in results
            and results["ids"]
            and len(results["ids"]) > 0
            and len(results["ids"][0]) > 0
        )

    @staticmethod
    def _build_memory_dict(
        doc_id: str, metadata: dict, results: dict, index: int
    ) -> Dict[str, Any]:
        """Build a single result dict from retriever metadata."""
        memory_dict: Dict[str, Any] = {
            "id": doc_id,
            "content": metadata.get("content", ""),
            "context": metadata.get("context", ""),
            "keywords": metadata.get("keywords", []),
            "tags": metadata.get("tags", []),
            "timestamp": metadata.get("timestamp", ""),
            "category": metadata.get("category", "Uncategorized"),
            "is_neighbor": False,
        }
        if (
            "distances" in results
            and len(results["distances"]) > 0
            and index < len(results["distances"][0])
        ):
            memory_dict["score"] = results["distances"][0][index]
        return memory_dict

    def _collect_search_results(
        self, results: dict, k: int, memories: list, seen_ids: set
    ) -> None:
        """Extract primary search hits from retriever results."""
        for i, doc_id in enumerate(results["ids"][0][:k]):
            if doc_id in seen_ids:
                continue
            if i < len(results["metadatas"][0]):
                memories.append(
                    self._build_memory_dict(
                        doc_id, results["metadatas"][0][i], results, i
                    )
                )
                seen_ids.add(doc_id)

    def _collect_neighbor_results(self, memories: list, seen_ids: set, k: int) -> None:
        """Append linked (neighbor) memories to the result list."""
        neighbor_count = 0
        for memory in list(memories):
            if neighbor_count >= k:
                break
            links = self._resolve_links(memory)
            for link_id in links:
                if link_id in seen_ids or neighbor_count >= k:
                    continue
                neighbor = self.memories.get(link_id)
                if not neighbor:
                    continue
                memories.append(
                    {
                        "id": link_id,
                        "content": neighbor.content,
                        "context": neighbor.context,
                        "keywords": neighbor.keywords,
                        "tags": neighbor.tags,
                        "timestamp": neighbor.timestamp,
                        "category": neighbor.category,
                        "is_neighbor": True,
                    }
                )
                seen_ids.add(link_id)
                neighbor_count += 1

    def _resolve_links(self, memory: dict) -> list:
        """Get link IDs from a result dict, falling back to the in-memory object."""
        links = memory.get("links", [])
        if not links and "id" in memory:
            mem_obj = self.memories.get(memory["id"])
            if mem_obj:
                links = mem_obj.links
        return links

    _EVOLUTION_RESPONSE_FORMAT = {
        "type": "json_schema",
        "json_schema": {
            "name": "response",
            "schema": {
                "type": "object",
                "properties": {
                    "should_evolve": {"type": "boolean"},
                    "actions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "suggested_connections": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "new_context_neighborhood": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "tags_to_update": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "new_tags_neighborhood": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "required": [
                    "should_evolve",
                    "actions",
                    "suggested_connections",
                    "tags_to_update",
                    "new_context_neighborhood",
                    "new_tags_neighborhood",
                ],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }

    def process_memory(self, note: MemoryNote) -> Tuple[bool, MemoryNote]:
        """Process a memory note and determine if it should evolve.

        Args:
            note: The memory note to process

        Returns:
            Tuple[bool, MemoryNote]: (should_evolve, processed_note)
        """
        if not self.memories:
            return False, note

        try:
            neighbors_text, memory_ids = self.find_related_memories(note.content, k=5)
            if not neighbors_text or not memory_ids:
                return False, note

            response_json = self._get_evolution_decision(
                note, neighbors_text, memory_ids
            )
            should_evolve = response_json["should_evolve"]

            if should_evolve:
                self._apply_evolution_actions(note, response_json, memory_ids)

            return should_evolve, note

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error in memory evolution: {str(e)}")
            return False, note
        except Exception as e:
            logger.error(f"Error in process_memory: {str(e)}")
            return False, note

    def _get_evolution_decision(
        self, note: MemoryNote, neighbors_text: str, memory_ids: List[str]
    ) -> dict:
        """Query LLM for evolution decision and return parsed response."""
        prompt = self._evolution_system_prompt.format(
            content=note.content,
            context=note.context,
            keywords=note.keywords,
            nearest_neighbors_memories=neighbors_text,
            neighbor_number=len(memory_ids),
        )
        response = self.llm_controller.llm.get_completion(
            prompt, response_format=self._EVOLUTION_RESPONSE_FORMAT
        )
        return json.loads(response)

    def _apply_evolution_actions(
        self, note: MemoryNote, response_json: dict, memory_ids: List[str]
    ) -> None:
        """Apply evolution actions (strengthen, update_neighbor) from the LLM response."""
        for action in response_json["actions"]:
            if action == "strengthen":
                self._apply_strengthen(note, response_json)
            elif action == "update_neighbor":
                self._apply_update_neighbors(response_json, memory_ids)

    @staticmethod
    def _coerce_str_list(items: list) -> List[str]:
        """Ensure every element in *items* is a plain string.

        Small local models sometimes return tags/keywords as dicts or nested
        structures.  This normalises them so downstream code (e.g. the
        retriever's ``', '.join(tags)``) never crashes on non-string elements.
        """
        out: List[str] = []
        for item in items:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                # {"tag": "value"} → take the first string value
                for v in item.values():
                    if isinstance(v, str):
                        out.append(v)
                        break
            else:
                out.append(str(item))
        return out

    def _apply_strengthen(self, note: MemoryNote, response_json: dict) -> None:
        """Strengthen connections by adding links and updating tags."""
        connections = response_json["suggested_connections"]
        if self.max_links is not None:
            connections = connections[: self.max_links]
        for conn_id in connections:
            self.add_link(note.id, conn_id)
        note.tags = self._coerce_str_list(response_json["tags_to_update"])

    def _apply_update_neighbors(
        self, response_json: dict, memory_ids: List[str]
    ) -> None:
        """Update neighbor memories with new context and tags."""
        new_contexts = response_json["new_context_neighborhood"]
        new_tags = response_json["new_tags_neighborhood"]

        for i in range(min(len(memory_ids), len(new_tags))):
            memory_id = memory_ids[i]
            if memory_id not in self.memories:
                continue

            neighbor = self.memories[memory_id]
            if i < len(new_tags):
                neighbor.tags = self._coerce_str_list(new_tags[i])
            if i < len(new_contexts):
                ctx = new_contexts[i]
                neighbor.context = ctx if isinstance(ctx, str) else str(ctx)

            self.memories[memory_id] = neighbor
            self._save_note(neighbor)
