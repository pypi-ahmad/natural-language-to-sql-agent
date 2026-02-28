import re
import sqlite3
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

# Define State
# This dictionary tracks the progress of the agent through the workflow.
class AgentState(TypedDict):
    question: str      # The user's original question
    schema: str        # The database schema string
    sql_query: str     # The generated SQL query
    sql_safe: bool     # Security check result (True/False)
    result: str        # The result of the SQL query execution
    error: str         # Any error message encountered
    retry_count: int   # Number of times the agent tried to fix the SQL

# --- DATABASE SETUP ---
def setup_db():
    """
    Initializes the SQLite database 'company.db' with sample data.
    
    Creates two tables if they do not exist:
    - departments: dept_id, dept_name, location
    - employees: emp_id, name, salary, dept_id
    
    Inserts predefined sample records into both tables.
    """
    conn = sqlite3.connect("company.db")
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS departments (dept_id INTEGER PRIMARY KEY, dept_name TEXT, location TEXT)")
        cursor.executemany("INSERT OR IGNORE INTO departments VALUES (?,?,?)", [
            (101, 'Engineering', 'New York'), (102, 'Sales', 'San Francisco'), (103, 'HR', 'Remote')
        ])
        cursor.execute("CREATE TABLE IF NOT EXISTS employees (emp_id INTEGER PRIMARY KEY, name TEXT, salary REAL, dept_id INTEGER)")
        cursor.executemany("INSERT OR IGNORE INTO employees VALUES (?,?,?,?)", [
            (1, 'Alice', 120000, 101), (2, 'Bob', 85000, 102), (3, 'Charlie', 115000, 101),
            (4, 'Diana', 95000, 103), (5, 'Eve', 88000, 102)
        ])
        conn.commit()
    finally:
        conn.close()

# --- AGENT CLASS ---
class SQLAgent:
    """
    A LangGraph-based agent designed to answer user questions by querying a SQLite database.
    
    This agent follows a structured workflow:
    1. Fetches the database schema.
    2. Uses an LLM to generate a SQL query based on the schema and user question.
    3. Validates the SQL query for security risks (e.g., dropping tables).
    4. Executes the safe SQL query against the database.
    5. Summarizes the query results into a natural language response.
    """
    def __init__(self, llm):
        """
        Initializes the SQLAgent with a language model.
        
        Args:
            llm: The language model instance (e.g., ChatOpenAI, ChatOllama) used for generating SQL and summaries.
        """
        self.llm = llm
        setup_db() # Ensure DB exists on initialization

    def fetch_schema(self, state: AgentState):
        """
        Retrieves the database schema (tables and columns) to provide context for the LLM.
        
        Args:
            state (AgentState): The current state of the agent.
            
        Returns:
            dict: A dictionary containing the 'schema' string, which lists table names and column details.
        """
        conn = sqlite3.connect("company.db")
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            schema_str = ""
            for table in tables:
                table_name = table[0]
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                col_names = [f"{col[1]} ({col[2]})" for col in columns]
                schema_str += f"Table '{table_name}': {', '.join(col_names)}\n"
            return {"schema": schema_str}
        finally:
            conn.close()

    def write_sql(self, state: AgentState):
        """
        Generates a SQL query using the LLM based on the provided schema and user question.
        
        Args:
            state (AgentState): The current state, including 'schema', 'question', and optional 'error' from previous attempts.
            
        Returns:
            dict: Updates 'sql_query' with the generated SQL and increments 'retry_count'.
        """
        prompt = f"""
        You are an expert SQLite Data Analyst.
        Schema:
        {state['schema']}
        
        Question: "{state['question']}"
        
        Instructions:
        1. Return ONLY the raw SQL code. 
        2. Do not use markdown blocks (```sql).
        3. If previous error: "{state['error']}", fix it.
        """
        response = self.llm.invoke([HumanMessage(content=prompt)])
        sql = response.content.strip().replace("```sql", "").replace("```", "")
        return {"sql_query": sql, "retry_count": state.get("retry_count", 0) + 1}

    def check_security(self, state: AgentState):
        """
        Performs a security check on the generated SQL query to prevent destructive operations.
        
        Args:
            state (AgentState): The current state containing the 'sql_query'.
            
        Returns:
            dict: Updates 'sql_safe' (bool) and 'error' (str) if a forbidden keyword is found.
        """
        query = state['sql_query'].upper()
        forbidden = ["DROP", "DELETE", "TRUNCATE", "INSERT", "UPDATE", "ALTER"]
        for word in forbidden:
            if re.search(r'\b' + word + r'\b', query):
                return {"sql_safe": False, "error": f"Forbidden keyword '{word}' detected."}
        return {"sql_safe": True, "error": ""}

    def execute_sql(self, state: AgentState):
        """
        Executes the SQL query against the SQLite database.
        
        Args:
            state (AgentState): The current state containing the 'sql_query'.
            
        Returns:
            dict: Updates 'result' with the query output or 'error' if execution fails.
        """
        conn = sqlite3.connect("company.db")
        try:
            cursor = conn.cursor()
            cursor.execute(state['sql_query'])
            rows = cursor.fetchall()
            if not rows: return {"result": "No data found.", "error": ""}
            return {"result": str(rows), "error": ""}
        except sqlite3.Error as e:
            return {"result": "", "error": str(e)}
        finally:
            conn.close()

    def summarize_result(self, state: AgentState):
        """
        Summarizes the SQL query results into a natural language answer using the LLM.
        
        Args:
            state (AgentState): The current state containing 'question', 'sql_query', and 'result'.
            
        Returns:
            dict: Updates 'result' with the final natural language answer.
        """
        prompt = f"""
        User Question: {state.get('question', '')}
        SQL Used: {state.get('sql_query', '')}
        Data Found: {state.get('result', 'N/A')}
        Error: {state.get('error', '')}
        
        Provide a professional, concise answer.
        """
        response = self.llm.invoke([HumanMessage(content=prompt)])
        return {"result": response.content}

    # --- ROUTING ---
    def route_after_security(self, state: AgentState):
        """
        Determines the next step after the security check.
        
        Args:
            state (AgentState): The current state.
            
        Returns:
            str: "execute" if the query is safe, otherwise "summarize" (to report the security error).
        """
        return "execute" if state['sql_safe'] else "summarize"

    def route_after_execute(self, state: AgentState):
        """
        Determines the next step after query execution.
        
        Args:
            state (AgentState): The current state.
            
        Returns:
            str: "retry" if an error occurred and retries are available, otherwise "summarize".
        """
        if state['error'] and state['retry_count'] < 3:
            return "retry"
        return "summarize"

    def get_workflow(self):
        """
        Constructs and compiles the LangGraph state graph for the agent.
        
        Returns:
            CompiledGraph: The compiled workflow ready for execution.
        """
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("fetch_schema", self.fetch_schema)
        workflow.add_node("writer", self.write_sql)
        workflow.add_node("guardian", self.check_security)
        workflow.add_node("executor", self.execute_sql)
        workflow.add_node("summarizer", self.summarize_result)

        # Define flow
        workflow.set_entry_point("fetch_schema")
        workflow.add_edge("fetch_schema", "writer")
        workflow.add_edge("writer", "guardian")
        
        # Conditional edges based on routing functions
        workflow.add_conditional_edges("guardian", self.route_after_security, {"execute": "executor", "summarize": "summarizer"})
        workflow.add_conditional_edges("executor", self.route_after_execute, {"retry": "writer", "summarize": "summarizer"})
        
        workflow.add_edge("summarizer", END)
        
        return workflow.compile()
