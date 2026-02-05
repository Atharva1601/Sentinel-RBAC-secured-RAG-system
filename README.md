# 🔐 Sentinel — Secure RBAC-Based RAG System for Enterprise Knowledge

A **secure, document-only Retrieval-Augmented Generation (RAG) platform** designed for enterprise use.
Sentinel enforces **role-based access control (RBAC) at retrieval time**, ensuring users can only access information they are authorized to see.

> ⚠️ No model training. No hallucinations. No uncontrolled access.  
> Built for internal company documents, manuals, and knowledge bases.

---

## 🚀 Key Features

- 🔑 **Role-Based Access Control (RBAC)**
  - 3 authorization levels enforced during retrieval
  - Prevents data leakage across roles or departments

- 📄 **Document-Only Knowledge System**
  - PDFs uploaded, ingested, chunked, embedded, and securely retrieved
  - No internet access, no external knowledge

- 🧠 **Retrieval-Augmented Generation (RAG)**
  - Uses embeddings + semantic search
  - Context-only answers with safe failure handling

- 🧱 **Strict Safety Design**
  - Zero hallucination policy
  - Explicit responses for unauthorized access, no documents, and insufficient context

- 💬 **Chat-Style Interface**
  - Clean UI for querying enterprise documents
  - Admin dashboards for users and documents

---

## 🏗️ System Architecture

User Query  
→ Authentication (JWT)  
→ RBAC Authorization  
→ Metadata-Filtered Retrieval (ChromaDB)  
→ Top-K Context Selection  
→ LLM Response (Context-Only)

---

## 🛡️ Authorization Model

Each document chunk includes metadata:
- owner_department
- min_role_level
- min_clearance_level

Authorization is enforced **before retrieval**, ensuring unauthorized content is never sent to the LLM.

---

## ⚙️ Tech Stack

**Backend**
- FastAPI
- ChromaDB
- Hugging Face Embeddings
- JWT Authentication

**Frontend**
- React + TypeScript
- Admin dashboards
- Chat interface

**Infrastructure**
- Docker (optional)
- Designed for Render (backend) and Vercel (frontend)

---

## 📂 Project Structure
```text
.
├── backend/
│   ├── app/
│   │   ├── auth/
│   │   ├── embeddings/
│   │   ├── retrieval/
│   │   ├── routes/
│   │   ├── models/
│   │   └── main.py
│
├── frontend/
│   └── src/
│       ├── pages/
│       ├── context/
│       └── components/
│
├── samples/   # gitignored
├── chroma/    # gitignored
└── .env       # gitignored
```

---

## 🔒 Security & Safety Guarantees

- No training on user data
- No external knowledge access
- No hallucinations
- Explicit refusal on insufficient context
- RBAC enforced before retrieval

---

## 📈 Performance

- ~2s average response time
- Tested with 100+ document chunks
- Chunk size: 900 | Overlap: 180 | Top-K: 7

---

## 🚧 Future Improvements

- OCR support
- Hybrid search
- Permission editor

