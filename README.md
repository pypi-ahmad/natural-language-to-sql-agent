# Natural Language to SQL Data Analyst Agent

An intelligent, AI-powered data analyst agent that transforms natural language questions into secure SQL queries, executes them against a database, and provides insightful, human-readable summaries of the results.

Built with **LangGraph**, **LangChain**, and **Streamlit**. Supports multiple LLM providers including **Ollama**, **OpenAI**, **Google Gemini**, and **Anthropic**.

## 🚀 Features

- **Multi-Provider Support**: Seamlessly switch between local models (Ollama) and cloud-based models (OpenAI, Gemini, Anthropic).
- **Dynamic Model Fetching**: Automatically lists available models for your API key.
- **Secure SQL Execution**: Includes a guardian node that blocks destructive SQL commands (DROP, DELETE, etc.).
- **Schema-Aware**: Automatically fetches and understands the database schema to write accurate queries.
- **Interactive UI**: A clean, responsive Streamlit interface that visualizes the agent's thought process (schema fetching, SQL generation, security checks, execution).
- **Resilient Workflow**: Retries SQL generation if execution fails.

## 🛠️ Prerequisites

- **Python 3.10+**
- **Ollama** (optional, for local models)
- API Keys for cloud providers:
  - OpenAI API Key
  - Google Gemini API Key
  - Anthropic API Key

## 📦 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/pypi-ahmad/natural-language-to-sql-agent.git
   cd natural-language-to-sql-agent
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Environment Variables (Optional):**
   Create a `.env` file in the root directory to store your API keys securely. The application will automatically detect them.
   ```env
   OPENAI_API_KEY=your_openai_key
   GOOGLE_API_KEY=your_google_key
   ANTHROPIC_API_KEY=your_anthropic_key
   ```

## ▶️ How to Run

1. **Start the application:**
   ```bash
   streamlit run app.py
   ```

2. **Configure the Agent:**
   - Select your preferred **LLM Provider** from the sidebar.
   - If you haven't set up a `.env` file, enter your **API Key** when prompted.
   - Click **"Fetch Available Models"** to populate the model list.
   - Select a **Model**.

3. **Ask Questions:**
   - Type questions like:
     - *"What is the total salary for the Engineering department?"*
     - *"List all employees in San Francisco."*
     - *"Who has the highest salary?"*
   - Watch the agent think, generate SQL, check for security, and return the answer!

## 📂 Project Structure

```
├── app.py           # Frontend (Streamlit): Handles UI, user input, and model configuration.
├── backend.py       # Backend (LangGraph): Defines the agent workflow, database interactions, and state management.
├── requirements.txt # Python dependencies.
├── company.db       # SQLite database (automatically generated on first run).
├── .env             # Environment variables (not tracked by git).
└── README.md        # Project documentation.
```

## 🧠 How It Works

The agent uses a **LangGraph** workflow with the following nodes:

1.  **`fetch_schema`**: Retrieves the database structure (tables & columns).
2.  **`writer`**: Uses the LLM to generate a SQL query based on the user's question and schema.
3.  **`guardian`**: Checks the SQL query for forbidden keywords (e.g., `DROP`, `DELETE`) to ensure safety.
4.  **`executor`**: Runs the safe SQL query against the SQLite database.
5.  **`summarizer`**: Takes the raw query results and generates a natural language answer.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is open-source and available under the MIT License.

---

**Developed by [Ahmad](https://github.com/pypi-ahmad)**
