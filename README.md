# 🌉 BridgeCF: Adaptive Codeforces Hint Engine

BridgeCF is a high-performance browser extension designed for competitive programmers. Instead of immediately spoiling solutions or searching for generic tags, BridgeCF acts as an automated, personalized tutor. 

By calculating the mathematical gap between your historical Codeforces submissions and a target problem, it routes you to optimal "Bridge Problems" (slightly easier version of the problem) and generates Socratic, step-by-step hints using local AI inference.

---

## 🧰 Tech Stack & Infrastructure

<table>
  <tr>
    <td align="center" width="25%">
      <h3>⚙️ Core Engine</h3>
      <img src="https://img.shields.io/badge/C++-11%2B-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white" alt="C++" />
      <br><br>
      <img src="https://img.shields.io/badge/ctypes-Bridge-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="ctypes" />
    </td>
    <td align="center" width="25%">
      <h3>🧠 AI & NLP</h3>
      <img src="https://img.shields.io/badge/Ollama-Local_LLM-FFFFFF?style=for-the-badge&logo=ollama&logoColor=black" alt="Ollama" />
      <br><br>
      <img src="https://img.shields.io/badge/FAISS-Vector_DB-172B4D?style=for-the-badge" alt="FAISS" />
    </td>
    <td align="center" width="25%">
      <h3>🌐 Backend API</h3>
      <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
      <br><br>
      <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
    </td>
    <td align="center" width="25%">
      <h3>🖥️ Client</h3>
      <img src="https://img.shields.io/badge/Chrome_V3-Extension-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Chrome" />
      <br><br>
      <img src="https://img.shields.io/badge/Vanilla_JS-Frontend-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="Vanilla JS" />
    </td>
  </tr>
</table>

---

## 📐 How It Works: The Architecture

BridgeCF discards standard API wrappers in favor of low-level system optimizations and deterministic graph theory. The intelligence is split across three isolated pipelines:

### 1. The Deterministic Graph Engine (C++)
At the core of BridgeCF is a custom **Heterogeneous Directed Acyclic Graph (DAG)** compiled into a shared memory library (`.so`) that calculates exactly what you *don't* know.
* **The Forward Pass:** The engine fetches your Codeforces handle history and traverses *backward* up the DAG's edges to map all the mathematical concepts you have successfully mastered.
* **The Target Pass:** It then looks at the problem you are stuck on and maps its required conceptual prerequisites.
* **The Bottleneck:** Executing a Multi-Source BFS in **<2ms**, it calculates the set difference (`Required \ Mastered`) to isolate the exact mathematical concept holding you back, completely bypassing the JSON serialization overhead using Python `ctypes`.

### 2. Semantic Vector Matching & JIT Ingestion (FAISS)
Once the missing concept is found, the system finds an easier "Bridge Problem" to help you practice it.
* **Vector Math:** Problems are encoded into 384-dimensional coordinate space using `SentenceTransformers`. A local FAISS index performs an L2 distance search to find structurally similar problems that share the same underlying logic.
* **Just-In-Time (JIT) Pipeline:** If you request a hint for a brand new Codeforces problem, BridgeCF uses `cloudscraper` to bypass Cloudflare, dynamically scrapes the problem text, embeds it, and updates the local FAISS index on the fly. This guarantees a **100% cache-miss resolution rate** in under 1.5 seconds.

### 3. Local Hint Generation (Ollama RAG)
Instead of pinging expensive cloud APIs, BridgeCF orchestrates local Small Language Models (SLMs like `Llama-3-8B` or `Phi-3`) directly on the machine's unified memory.
* **The Hidden Prompt:** The C++ engine passes the calculated "bottleneck concept" to the Python backend. The backend constructs a strict system prompt.
* **The Output:** The local LLM generates step-by-step, pedagogical hints that adapt to your exact skill level, all with **$0 cloud latency and zero cost**.

---
