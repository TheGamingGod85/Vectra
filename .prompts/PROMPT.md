# ROLE

You are a senior AI systems engineer specializing in multi-agent architectures. Your task is to build a production-style prototype of **BugRewind**, an AI-powered secure deployment system using proper agent orchestration.

Focus on **working multi-agent flow using LangGraph**, not theoretical design.


---

# TECH STACK (MANDATORY)

* Python 3.11+
* Package manager: uv
* LLM: Ollama API (kimi-k2.5:cloud or codellama)
* Agent framework: LangGraph (preferred) or LangChain
* MCP Server: FastMCP
* Docker CLI (subprocess)

---

# PROJECT GOAL

Build a **true multi-agent system** where agents:

* have distinct roles
* communicate via structured state
* operate in a controlled workflow graph

System should:

1. Analyze codebase
2. Detect vulnerabilities
3. Iteratively fix issues
4. Generate deployment configs
5. Validate via Docker
6. Deploy locally
7. Output summary

---

# AGENT DEFINITIONS

## 1. Orchestrator Agent

* Role:

  * Entry point
  * Understand repo + user intent
  * Create execution plan
* Output:

  * structured task plan
  * instructions for other agents

---

## 2. Critic Agent

* Role:

  * Security + quality reviewer
* Access:

  * Full codebase
* Output:

  * list of vulnerabilities
  * severity levels
  * relevant code snippets

Must detect:

* secrets
* unsafe shell usage
* dependency risks
* missing Dockerfile

---

## 3. Coder Agent

* Role:

  * Apply fixes
* Input:

  * critic findings
  * selected code snippets
* Constraint:

  * DO NOT rewrite entire repo
* Output:

  * patches / updated code

---

## 4. Solomon Agent

* Role:

  * Execution agent
* Only agent allowed to:

  * run shell commands
  * execute Docker

---

# LANGGRAPH DESIGN

Use LangGraph to define:

## State Object

```python
{
  "repo_path": str,
  "codebase": str,
  "issues": list,
  "patches": list,
  "iteration": int,
  "max_iterations": int,
  "docker_status": str,
  "logs": str
}
```

---

## Graph Flow

START → Orchestrator
→ Critic
→ Coder
→ Critic
→ (loop until iteration limit)
→ Docker Generation
→ Validation
→ Solomon
→ END

---

## Iteration Logic

* Loop between Critic and Coder
* Stop when:

  * iteration == max_iterations
  * OR no issues remain

---

# TOOLING

## LLM Wrapper

Implement:

```python
def call_ollama(prompt: str) -> str
```

Endpoint:

* http://localhost:11434/api/generate

---

## Tools (for Solomon)

* docker_build_tool
* docker_run_tool

Use subprocess safely.

---

# MCP SERVER

Using FastMCP:

Expose:

```python
orchestrator_tool(repo_path: str, deploy_prompt: str)
```

This should:

* initialize LangGraph
* execute full workflow
* return summary

---

# DOCKER GENERATION

Coder or separate node must generate:

* Dockerfile
* .dockerignore

Keep minimal but correct.

---

# VALIDATION STEP

Before final deployment:

* docker build must succeed
* container must start

If failure:

* send logs back into graph
* allow critic to analyze

---

# SUMMARY OUTPUT

Generate:
outputs/summary.md

Include:

* issues found
* fixes applied
* number of iterations
* docker status
* final result

---

# PROJECT STRUCTURE

bugrewind/
│── main.py
│── graph/
│   ├── workflow.py
│   ├── state.py
│── agents/
│   ├── orchestrator.py
│   ├── critic.py
│   ├── coder.py
│   ├── solomon.py
│── tools/
│   ├── docker_tools.py
│── mcp_server.py
│── utils/
│   ├── llm.py
│   ├── file_ops.py
│── outputs/
│   └── summary.md

---

# REQUIREMENTS

* Use uv (pyproject.toml required)
* No cloud dependencies
* Fully local execution
* Clean modular code

---

# CONSTRAINTS

* Use LangGraph properly (nodes + edges + state)
* No fake sequential scripting
* Each agent must be a distinct node
* Maintain clear separation of responsibilities

---

# OUTPUT FORMAT

Return:

1. Full project code
2. Setup instructions
3. Example run command

---

# IMPORTANT

* Do NOT explain theory
* Do NOT skip files
* Ensure code runs
* If uncertain, make reasonable assumptions and proceed
