# Disclaimer

Please read this before pointing NL2SQL Agent at a database you care about.

## You run this entirely on your own machine, with your own credentials

NL2SQL Agent is a local-first tool. There is no hosted version, no backend server operated by the author, and no account system. It connects to a SQLite or PostgreSQL database you provide, using whichever LLM provider you configure. API keys (`OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `HF_TOKEN`, `XAI_API_KEY`, `NL2SQL_AGNES_API_KEY`) and the PostgreSQL connection string are read only from your environment and are redacted from `config` output and audit logs — see [SECURITY.md](SECURITY.md).

## What actually leaves your machine

This is the part most disclaimers gloss over, so it's stated precisely:

- **Writing SQL:** your database **schema** (table/column names) and your **question** are sent to whichever LLM provider you've selected.
- **Summarizing the answer:** the **actual query result data** — the real rows your query returned — is sent to that same provider, along with the SQL and your question, so it can write a natural-language answer.
- **Local Ollama is the only path that keeps all of this on your machine.** Selecting any hosted provider (OpenAI, Google Gemini, Anthropic, xAI, Agnes AI, or a Hugging Face-routed model) means your schema, your question, and your real query results are transmitted to that provider's API.

## You are responsible for the data and database you connect

**You, and only you, are responsible for:**

- Deciding whether the database you point this at may have its schema and query results sent to a third-party LLM provider — this includes proprietary business data, customer records, or anything under a confidentiality or compliance obligation.
- Understanding and accepting your chosen provider's own data-handling, retention, and training-use policies.
- Any costs your provider charges for API usage. This project does not meter, cap, or reimburse API spend.
- The credentials and access scope of the database connection you provide — NL2SQL Agent enforces read-only query safety on its own side (see [ARCHITECTURE.md](ARCHITECTURE.md) and [SECURITY.md](SECURITY.md)), but a misconfigured connection string with write access is your responsibility, not the application's.

**If your data must never leave your machine, use only the local Ollama provider.**

## No warranty, no liability

This software is provided "as is," without warranty of any kind, as stated in the [MIT License](LICENSE). The author is not liable for any damage, data loss, unintended disclosure, API costs, or other consequences arising from your use of this tool. Use it at your own risk.

## No financial support wanted

This project is free, open-source, and does not want or accept donations, sponsorships, or any other form of financial contribution — see [SUPPORT.md](SUPPORT.md).
