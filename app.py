import streamlit as st
import os
from dotenv import load_dotenv
from backend import SQLAgent

# --- MODEL PROVIDER SDKs ---
import ollama
from openai import OpenAI
import google.generativeai as google_genai_legacy  # Renamed to avoid namespace collision

# Load env vars from .env file (if present)
load_dotenv()

# Set up Streamlit page configuration
st.set_page_config(page_title="SQL Data Agent", layout="wide")

# --- HELPER: FETCH MODELS ---
def get_available_models(provider, api_key=None):
    """
    Dynamically fetches models from the provider's API using the given Key.
    
    Args:
        provider (str): The name of the model provider ("Ollama", "OpenAI", "Gemini", "Anthropic").
        api_key (str, optional): The API key for the provider. Required for cloud providers.
        
    Returns:
        list: A list of available model names (strings). Returns an empty list on error.
    """
    try:
        if provider == "Ollama":
            models_info = ollama.list()
            # Handle list of objects vs list of dicts depending on version
            if hasattr(models_info, 'models'):
                return [m.model for m in models_info.models]
            return [m['name'] for m in models_info['models']]
            
        elif provider == "OpenAI":
            if not api_key: return []
            client = OpenAI(api_key=api_key)
            # Fetch all models, filter for chat models (gpt-3.5, gpt-4, o1, etc.)
            models = client.models.list()
            return sorted([m.id for m in models if "gpt" in m.id or "o1" in m.id], reverse=True)
            
        elif provider == "Gemini":
            if not api_key: return []
            # Fix: Use google.generativeai SDK properly with explicit alias
            google_genai_legacy.configure(api_key=api_key)
            models = google_genai_legacy.list_models()
            # Filter for generation models
            return [m.name.replace("models/", "") for m in models if 'generateContent' in m.supported_generation_methods]
            
        elif provider == "Anthropic":
            # Anthropic currently does NOT have a public 'list models' API endpoint.
            # We must use a curated list of their latest supported models.
            return [
                "claude-3-5-sonnet-latest", 
                "claude-3-5-haiku-latest",
                "claude-3-opus-latest"
            ]
            
    except Exception as e:
        st.error(f"Error fetching models for {provider}: {str(e)}")
        return []

# --- HELPER: INIT LLM ---
def get_llm_instance(provider, model_name, api_key=None):
    """
    Initializes and returns the LangChain Chat Model instance based on provider and model name.
    
    Args:
        provider (str): The model provider to use ("Ollama", "OpenAI", "Gemini", "Anthropic").
        model_name (str): The specific model identifier to load (e.g., "gpt-4o", "llama3").
        api_key (str, optional): The API key for authentication.
        
    Returns:
        BaseChatModel: A configured LangChain chat model instance ready for invocation.
    """
    if provider == "Ollama":
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(model=model_name)
        
    elif provider == "OpenAI":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(api_key=api_key, model=model_name)
        
    elif provider == "Gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(google_api_key=api_key, model=model_name)
        
    elif provider == "Anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(api_key=api_key, model=model_name)

# --- UI SIDEBAR ---
# Allows user to configure the model provider and API key
st.sidebar.title("🤖 Agent Config")
provider = st.sidebar.selectbox("Select Provider", ["Ollama", "Gemini", "OpenAI", "Anthropic"])

api_key = None
env_key_name = ""

# Map provider to environment variable name
if provider == "Gemini": env_key_name = "GOOGLE_API_KEY"
elif provider == "OpenAI": env_key_name = "OPENAI_API_KEY"
elif provider == "Anthropic": env_key_name = "ANTHROPIC_API_KEY"

# Check if Key exists in System/Env
system_key = os.getenv(env_key_name) if env_key_name else None

if provider != "Ollama":
    if system_key:
        # Key found in environment variables
        st.sidebar.success(f"✅ {provider} Key Loaded from System")
        use_manual_key = st.sidebar.checkbox("Change API Key", value=False)
        if use_manual_key:
            api_key = st.sidebar.text_input(f"Enter {provider} API Key", type="password")
        else:
            api_key = system_key
    else:
        # No system key found -> Force Input
        api_key = st.sidebar.text_input(f"Enter {provider} API Key", type="password")
        if not api_key:
            st.sidebar.warning(f"⚠️ API Key required for {provider}")

# Fetch Models Button
# Fetches available models from the provider using the API key
if provider == "Ollama" or api_key:
    if st.sidebar.button("🔄 Fetch Available Models"):
        with st.spinner(f"Connecting to {provider}..."):
            fetched_models = get_available_models(provider, api_key)
            if fetched_models:
                st.session_state.models = fetched_models
                st.sidebar.success(f"Found {len(fetched_models)} models.")
            else:
                st.sidebar.warning("No models found. Check your Key.")

# Model Dropdown (Defaults if empty)
# Shows the list of models to choose from
model_options = st.session_state.get("models", [])
if not model_options:
    if provider == "Ollama": model_options = ["llama3", "mistral"]
    if provider == "Gemini": model_options = ["gemini-1.5-flash", "gemini-pro"]
    if provider == "OpenAI": model_options = ["gpt-4o", "gpt-3.5-turbo"]
    if provider == "Anthropic": model_options = ["claude-3-5-sonnet-latest"]

selected_model = st.sidebar.selectbox("Select Model", model_options)

# --- MAIN CHAT UI ---
st.title("📊 AI SQL Data Analyst")
st.markdown(f"**Powered by:** `{provider}` / `{selected_model}`")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Input
user_query = st.chat_input("Ask about the data (e.g., 'Total Engineering salary?')")

if user_query:
    # Append user message to history
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # Initialize Agent
    try:
        # Check if key is required but missing
        if provider != "Ollama" and not api_key:
            st.error(f"Please enter an API Key for {provider} in the sidebar.")
            st.stop()

        # Create Agent Instance
        llm = get_llm_instance(provider, selected_model, api_key)
        agent = SQLAgent(llm)
        app = agent.get_workflow()
        
        inputs = {"question": user_query, "retry_count": 0, "error": ""}
        
        # Run Agent & Stream Steps
        with st.chat_message("assistant"):
            status_container = st.status("🧠 Agent Thinking...", expanded=True)
            final_response = ""
            
            # Stream events from LangGraph
            for event in app.stream(inputs):
                for node_name, state_update in event.items():
                    if node_name == "fetch_schema":
                        status_container.write("🔍 Fetched Database Schema")
                    elif node_name == "writer":
                        status_container.write(f"✍️ Drafted SQL: `{state_update['sql_query']}`")
                    elif node_name == "guardian":
                        if state_update['sql_safe']:
                            status_container.write("🛡️ Security Check Passed")
                        else:
                            status_container.error(f"🛡️ Security Block: {state_update['error']}")
                    elif node_name == "executor":
                        if state_update.get('error'):
                            status_container.error(f"⚠️ SQL Error: {state_update['error']}")
                        else:
                            status_container.write(f"🚀 Query Result: `{state_update['result']}`")
                    elif node_name == "summarizer":
                        final_response = state_update['result']
            
            # Update status and display final answer
            status_container.update(label="✅ Analysis Complete", state="complete", expanded=False)
            st.markdown(final_response)
            st.session_state.messages.append({"role": "assistant", "content": final_response})

    except Exception as e:
        st.error(f"Error: {str(e)}")
