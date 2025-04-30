# Combining multimodal RAG with multimodal Knowledge Graphs

## Core Insights

### Multimodal Knowledge Graphs (MKGs):

- Structure entities and relationships plus attach multimodal data (e.g., images linked to entities) using an ontology designed for multiple modalities.
- Use graph databases like Neo4j, JanusGraph, or RDF-based stores to manage structured multimodal knowledge.

### Static + Dynamic Graph Construction:

- Initial construction: extract structured data from text and images using NLP/computer vision (automated multimodal graph builder).
- Dynamic updates: continuously ingest new data and update the graph incrementally without full recomputations.

### Multimodal Retrieval-Augmented Generation (RAG):

- Retrieval uses complementary channels:
    - Unstructured retrieval (semantic search via embeddings).
    - Structured retrieval (knowledge graph queries): Factual Backbone including Entities, attributes, relationships. Stored in explicit form for reasoning, graph traversal, explainability, and fact verification.
    - Unstructured Retrieval of KG Elements via embeddings = Semantic Access Layer: By embedding entities, we enable semantic retrieval even if queries don’t match KG labels exactly, as well as allowing to query the graph by images or multimodal data!

### Graph-first or Retrieval-first Decision Strategies:

- Based on use case or query type, decide whether to query KG first or unstructured retrieval first (or both).
- Use dynamic orchestration to manage query routing and fusion of results for the LLM.

### Practical Implication
- You can design a hybrid RAG system that retrieves structured multimodal knowledge and complements it with unstructured context for richer, more accurate responses. 

# VR Simulations integration:

Multimodal KGs and RAG snhance VR simulations by functioning as a semantic brain for your virtual environment. 

## Usage

1. **Using a Multimodal KG to Build the Simulation**

The MKG becomes a world model. We can:
- Use KG entities as asset references (tools, environments, components).
- Use relationships to position or constrain objects (e.g., "the grounding clamp is connected to conductor X").
- Use procedural nodes to define training steps (e.g., step-by-step instructions linked to equipment).
**We can expand the automated unreal engine scripting tool to support multimodality so that we can build entire simulations from the ground up starting from unstructured data.**

2. **Updating the KG from Simulation Events**

As the simulation runs, we can:
- Add/modify facts in the KG dynamically (e.g., “User attached clamp to line X at time T”).
- Record trajectories and actions as event nodes.
- Tag user errors and associate them with learning objectives.

This allows to:
- Build a graph of user behavior (for replay or personalized feedback).
- Feed the KG back into training analytics.
- Optionally, use LLMs to summarize or score sequences stored in the KG.
This turns the KG into a self-updating memory structure, creating a "simulated knowledge diary." 

3. **Live Retrieval and Question Answering During Simulation**

A multimodal KG + RAG setup can power in-simulation agents or copilots.

Example interactions:
- “What is this object?” → Identify via camera raycast → map to KG entity → retrieve name, function, instructions.
- “What’s my next task?” → Query KG for the procedure chain → return next step.
- “What’s the safety rating of this component?” → Retrieve structured info or textual explanations.
- “Show me how to use it.” → Fetch associated image, video, or run animation.
This creates a conversational, multimodal assistant inside VR, powered by RAG over the KG + linked documents/manuals/images.

