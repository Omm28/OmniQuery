# OmniQuery

AI-powered web search agent built using a local LLM stack (Ollama + LangGraph) with a chat-based interface and persistent conversations.

---

## 🚀 Overview

OmniQuery is a full-stack AI application that allows users to interact with a web search agent through a chat interface. It leverages local LLMs for query processing and uses a modular backend design to support extensibility and future enhancements.
The system uses a graph-based execution model (LangGraph) to orchestrate query processing through modular nodes and middleware.

---

## ✨ Current Features

- Chat-based interface for interacting with the agent
- Conversation persistence using SQLite
- Sidebar with chat history and session loading
- FastAPI backend for handling API requests
- Modular architecture (nodes, tools, middleware structure)
- Frontend built with HTML, CSS, and Vanilla JavaScript

---

## 🛠️ Tech Stack

- **Backend:** FastAPI (Python)
- **LLM Orchestration:** LangGraph + Ollama
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript
- **Version Control:** Git

---

## 📁 Project Structure

```
OmniQuery/
│── app/                # Core backend logic
│   ├── middleware/     # Middleware (filters, processing layers)
│   ├── tools/          # External tools (e.g., search)
│   ├── main.py         # FastAPI entry point
│   ├── graph.py        # LangGraph workflow
│   └── ...
│
│── frontend/           # UI (HTML, CSS, JS)
│── run.py              # App runner
│── requirements.txt    # Dependencies
```

---

## ⚙️ Setup & Run

### 1. Clone the repository

```
git clone https://github.com/yourusername/OmniQuery.git
cd OmniQuery
```

### 2. Create virtual environment

```
python -m venv .venv
.venv\Scripts\activate   # Windows
```

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Run the application

```
python run.py
```

---

## 🧪 Current Status

This project is actively being developed as part of an AI engineering internship.

### Planned Improvements

- Convert workflow into a full agent architecture
- OAuth 2.0 authentication
- Integration of ORM for database management
- Git version control improvements

---

## 📌 Notes

- `.env` is not included — use `.env.example` as reference
- SQLite is used for local persistence
- Designed to evolve into a modular, production-ready AI system

---

## 📜 License

This project is for educational and development purposes.
