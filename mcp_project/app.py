"""
app.py — Enterprise Data Agent (Streamlit Frontend)

A natural-language interface to the enterprise users database, powered by
Groq LLM tool-calling and a local SQLite database.

Run: streamlit run mcp_project/app.py
"""
import os
import json
import streamlit as st
from groq import Groq, APIError, AuthenticationError, RateLimitError

# Load .env from the project root (one level above this file)
_dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(_dotenv_path):
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path)

# Shared DB layer — keeps SQL logic in one place
from db import add_user, deactivate_user, get_active_users, get_user_stats, search_users

# Page config (must be first Streamlit call)
st.set_page_config(
    page_title="Enterprise Data Agent",
    page_icon="🗄️",
    layout="centered"
)

# Styles
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        /* ── Color tokens ─────────────────────────────── */
        :root {
            --bg:        #0d0f14;
            --bg2:       #13161e;
            --bg3:       #1a1d27;
            --border:    #2a2d3a;
            --border-hi: #3d4259;
            --fg:        #e8eaf0;
            --fg-muted:  #8b90a8;
            --accent:    #6ee7f7;
            --accent2:   #818cf8;
            --accent-glow: rgba(110, 231, 247, 0.15);
            --user-bg:   #1e2235;
            --bot-bg:    #161923;
            --success:   #34d399;
            --danger:    #f87171;
            --warning:   #fbbf24;
        }

        /* ── Global reset ─────────────────────────────── */
        html, body, [class*="css"], .stApp {
            background-color: var(--bg) !important;
            color: var(--fg) !important;
            font-family: 'Space Grotesk', sans-serif !important;
        }

        /* ── Main content area ────────────────────────── */
        .main .block-container {
            padding-top: 2rem !important;
            padding-bottom: 6rem !important;
            max-width: 820px !important;
        }

        /* ── Page title ───────────────────────────────── */
        h1 {
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-weight: 700 !important;
            font-size: 2rem !important;
            letter-spacing: -0.5px;
            margin-bottom: 0.2rem !important;
        }

        /* Subtitle */
        h1 + div p {
            color: var(--fg-muted) !important;
            font-size: 0.9rem;
            margin-bottom: 1.5rem;
        }

        /* ── Chat messages ────────────────────────────── */
        [data-testid="stChatMessage"] {
            background: var(--bg2) !important;
            border: 1px solid var(--border) !important;
            border-radius: 16px !important;
            padding: 16px 20px !important;
            margin-bottom: 12px !important;
            box-shadow: 0 2px 12px rgba(0,0,0,0.3) !important;
            transition: border-color 0.2s ease;
        }
        [data-testid="stChatMessage"]:hover {
            border-color: var(--border-hi) !important;
        }

        /* User message — subtly different tint */
        [data-testid="stChatMessage"][data-testid*="user"],
        .stChatMessage.user-message {
            background: var(--user-bg) !important;
            border-color: #2d3355 !important;
        }

        /* ── Chat input bar ───────────────────────────── */
        [data-testid="stChatInput"] {
            background: var(--bg2) !important;
            border: 1px solid var(--border-hi) !important;
            border-radius: 16px !important;
            box-shadow: 0 0 0 0 transparent;
            transition: box-shadow 0.25s ease, border-color 0.25s ease;
        }
        [data-testid="stChatInput"]:focus-within {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px var(--accent-glow) !important;
        }
        [data-testid="stChatInput"] textarea {
            background: transparent !important;
            color: var(--fg) !important;
            font-family: 'Space Grotesk', sans-serif !important;
            font-size: 0.95rem !important;
        }
        [data-testid="stChatInput"] textarea::placeholder {
            color: var(--fg-muted) !important;
        }

        /* Input container bottom bar */
        .stChatInputContainer {
            background: var(--bg) !important;
            border-top: 1px solid var(--border) !important;
            padding: 16px 24px 20px !important;
        }

        /* ── Markdown text ────────────────────────────── */
        .stMarkdown, .stMarkdown p, .stMarkdown li,
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li {
            color: var(--fg) !important;
            line-height: 1.7;
        }

        /* ── Inline code ──────────────────────────────── */
        .stMarkdown code,
        [data-testid="stMarkdownContainer"] code {
            font-family: 'JetBrains Mono', monospace !important;
            background: #1e2235 !important;
            color: var(--accent) !important;
            border: 1px solid var(--border) !important;
            border-radius: 6px !important;
            padding: 1px 6px !important;
            font-size: 0.85em !important;
        }

        /* ── Tables ───────────────────────────────────── */
        table { border-collapse: collapse; width: 100%; margin: 0.5rem 0; }
        th {
            background: var(--bg3) !important;
            color: var(--accent) !important;
            padding: 8px 12px;
            border: 1px solid var(--border) !important;
            font-size: 0.85rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        td {
            color: var(--fg) !important;
            padding: 8px 12px;
            border: 1px solid var(--border) !important;
            font-size: 0.9rem;
        }
        tr:nth-child(even) td { background: #13161e !important; }

        /* ── Sidebar ──────────────────────────────────── */
        [data-testid="stSidebar"] {
            background: var(--bg2) !important;
            border-right: 1px solid var(--border) !important;
        }
        [data-testid="stSidebar"] * {
            color: var(--fg) !important;
        }
        [data-testid="stSidebar"] .stMarkdown h3 {
            color: var(--accent) !important;
            font-size: 0.8rem !important;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            -webkit-text-fill-color: var(--accent) !important;
        }
        [data-testid="stSidebar"] em {
            color: var(--fg-muted) !important;
            font-style: normal !important;
            font-size: 0.88rem;
        }
        [data-testid="stSidebar"] code {
            background: var(--bg3) !important;
            color: var(--accent2) !important;
            border-color: var(--border) !important;
        }

        /* Sidebar divider */
        [data-testid="stSidebar"] hr {
            border-color: var(--border) !important;
            margin: 12px 0 !important;
        }

        /* ── Buttons ──────────────────────────────────── */
        .stButton > button {
            background: var(--bg3) !important;
            color: var(--fg) !important;
            border: 1px solid var(--border-hi) !important;
            border-radius: 10px !important;
            font-family: 'Space Grotesk', sans-serif !important;
            font-size: 0.85rem !important;
            padding: 6px 16px !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button:hover {
            background: var(--user-bg) !important;
            border-color: var(--accent) !important;
            color: var(--accent) !important;
            box-shadow: 0 0 10px var(--accent-glow) !important;
        }

        /* ── Scrollbar ────────────────────────────────── */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb {
            background: var(--border-hi);
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent2); }

        /* ── Avatar icons ─────────────────────────────── */
        [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"] {
            background: linear-gradient(135deg, #4f46e5, var(--accent2)) !important;
        }
        [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
            background: linear-gradient(135deg, #0891b2, var(--accent)) !important;
        }

        /* ── Alerts / errors ──────────────────────────── */
        [data-testid="stAlert"] {
            background: #1e1212 !important;
            border-color: var(--danger) !important;
            color: var(--fg) !important;
            border-radius: 12px !important;
        }

        /* ── Hide Streamlit chrome ────────────────────── */
        #MainMenu  { visibility: hidden; }
        footer     { visibility: hidden; }
        header     { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

# Header
st.title("Enterprise Data Agent")
st.markdown("Ask natural-language questions about the enterprise user database.")

# Sidebar — usage hints
with st.sidebar:
    st.markdown("### 💡 Example Queries")
    examples = [
        "Who are our active users?",
        "Add Jane Doe as a Manager",
        "How many users do we have?",
        "Search for users named Alice",
        "Deactivate Bob Jones",
        "Show me user statistics",
    ]
    for ex in examples:
        st.markdown(f"- *{ex}*")

    st.divider()
    st.markdown("### 🔧 Available Tools")
    st.markdown(
        "- `get_active_users`\n"
        "- `add_user`\n"
        "- `deactivate_user`\n"
        "- `get_user_stats`\n"
        "- `search_users`"
    )
    st.divider()
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.rerun()

# Groq client
_api_key = os.environ.get("GROQ_API_KEY")
if not _api_key:
    st.error("`GROQ_API_KEY` is not set. Add it to your `.env` file and restart.")
    st.stop()

client = Groq(api_key=_api_key)
# llama3-groq-70b-8192-tool-use-preview is fine-tuned for JSON tool-calling.
# llama-3.3-70b-versatile sometimes emits malformed XML-style function calls
# (e.g. <function=name={...}>) which causes Groq to return a 400 tool_use_failed error.
MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render conversation history (skip raw tool-call internals)
for msg in st.session_state.messages:
    if msg["role"] == "tool" or msg.get("tool_calls"):
        continue
    content = msg.get("content")
    if content is None:
        continue
    with st.chat_message(msg["role"]):
        st.markdown(content)

# Tool definitions (given to the LLM)
mcp_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_active_users",
            "description": "Fetches all active users and their roles from the enterprise database.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_user",
            "description": "Adds a new active user to the enterprise database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The full name of the user."},
                    "role": {
                        "type": "string",
                        "description": "Job role: Employee, Manager, Admin, Engineer, Intern, or Director. Defaults to Employee."
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deactivate_user",
            "description": "Deactivates an active user by their full name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The full name of the user to deactivate."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_stats",
            "description": "Returns total, active, and inactive user counts.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_users",
            "description": "Searches users by a name fragment. Returns name, role, and status for all matches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A name fragment to search for (case-insensitive)."}
                },
                "required": ["query"]
            }
        }
    },
]

# Tool dispatcher — calls the shared db.py functions
def dispatch_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool call and return a JSON string result."""
    if tool_name == "get_active_users":
        result = get_active_users()
    elif tool_name == "add_user":
        result = add_user(
            name=arguments.get("name", ""),
            role=arguments.get("role", "Employee")
        )
    elif tool_name == "deactivate_user":
        result = deactivate_user(name=arguments.get("name", ""))
    elif tool_name == "get_user_stats":
        result = get_user_stats()
    elif tool_name == "search_users":
        result = search_users(query=arguments.get("query", ""))
    else:
        result = {"error": f"Unknown tool: '{tool_name}'"}
    return json.dumps(result)

# System prompt
SYSTEM_PROMPT = """You are a concise, professional enterprise AI assistant with access to tools that query and modify an employee database.

The database contains a single `users` table with columns: id, name, role, and status (Active/Inactive).

Strict rules:
1. ONLY answer questions about the user database. Politely decline all unrelated topics.
2. ALWAYS use the available tools to fetch real data — never invent user names, counts, or roles.
3. When presenting user lists, format them clearly (e.g. as a markdown table or bullet list).
4. For write operations (add, deactivate), confirm the action result to the user.

Refusal example: "I can only assist with questions about the employee database."
"""

# Chat input & inference loop
user_query = st.chat_input("E.g., Who are our active users?")

if user_query:
    # Store and show the user message
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    messages_for_groq = [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.messages

    with st.chat_message("assistant"):
        placeholder = st.empty()

        try:
            # --- Pass 1: LLM decides whether to call a tool ---
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages_for_groq,
                tools=mcp_tools,
                tool_choice="auto",
            )
            response_message = response.choices[0].message

            if response_message.tool_calls:
                placeholder.markdown("*Querying the database…*")

                # Append the assistant's tool-call request to history
                messages_for_groq.append(response_message)

                # Execute each tool call
                for tc in response_message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    db_result = dispatch_tool(tc.function.name, args)
                    messages_for_groq.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": db_result,
                    })

                # --- Pass 2: LLM synthesizes the tool results (streamed) ---
                stream = client.chat.completions.create(
                    model=MODEL,
                    messages=messages_for_groq,
                    stream=True,
                )
                final_text = ""
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    final_text += delta
                    placeholder.markdown(final_text + " ")
                placeholder.markdown(final_text)

                # Persist to session state
                serialized_tool_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in response_message.tool_calls
                ]
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": serialized_tool_calls,
                })
                # Append only the last tool result (the one the LLM responded to)
                st.session_state.messages.append(messages_for_groq[-1])
                st.session_state.messages.append({"role": "assistant", "content": final_text})

            else:
                # No tool needed — stream the direct reply
                stream = client.chat.completions.create(
                    model=MODEL,
                    messages=messages_for_groq,
                    stream=True,
                )
                ai_response = ""
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    ai_response += delta
                    placeholder.markdown(ai_response + " ")
                placeholder.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})

        except AuthenticationError:
            placeholder.error("Invalid Groq API key. Check your `.env` file.")
        except RateLimitError:
            placeholder.error("Groq rate limit reached. Please wait a moment and try again.")
        except APIError as e:
            placeholder.error(f"Groq API error: {e}")
        except Exception as e:
            placeholder.error(f"Unexpected error: {e}")
