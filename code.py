import re
import time
import json
from typing import Optional

from langchain.prompts import PromptTemplate
from langchain_community.utilities import SQLDatabase
from openai import OpenAI
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import URL

# ---------- Settings (confirmed working) ----------
PG_USER = "postgres"
PG_PASS = "1234"
PG_HOST = "127.0.0.1"
PG_PORT = 5432
PG_DB   = "THESIS_DATABASE"
MODEL_NAME = "hermes-3-llama-3.2-3b"

# ---------- 0) Minimal psycopg2 smoke test ----------
def _smoke_test():
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname=PG_DB, user=PG_USER, password=PG_PASS, host=PG_HOST, port=PG_PORT
        )
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.fetchone()
        cur.close()
        conn.close()
        print("[Smoke Test] psycopg2 connect OK")
    except Exception as e:
        raise SystemExit(f"[Smoke Test] FAILED: {e}")

_smoke_test()

# ---------- 1) Build engine ourselves and verify ----------
DB_URL = URL.create(
    "postgresql+psycopg2",
    username=PG_USER,
    password=PG_PASS,
    host=PG_HOST,
    port=PG_PORT,
    database=PG_DB,
)
print("Engine URL:", DB_URL)

engine = create_engine(DB_URL, pool_pre_ping=True)

# Direct SQLAlchemy test
with engine.connect() as conn:
    v = conn.exec_driver_sql(
        "select inet_server_addr(), inet_server_port(), current_database();"
    ).fetchone()
    print("[SQLAlchemy Test] OK ->", v)

# ---------- 2) Give LangChain the working engine ----------
db = SQLDatabase(engine=engine)

# ---------- 3) LM Studio client ----------
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# ---------- 4) Dataset-specific prompt (uses your exact action vocabulary) ----------
sql_prompt = PromptTemplate(
    input_variables=["input", "table_info"],
    template="""
You are a PostgreSQL expert who outputs exactly ONE executable SQL statement for this specific dataset.

Database schema:
{table_info}

Table & columns (do NOT invent):
- moodle_data(
  id, eventname, component, action, target, crud, edulevel,
  contextid, contextlevel, contextinstanceid, userid, courseid,
  relateduserid, anonymous, timecreated, origin, datetime, time, day, month
)

Valid action values in THIS dataset (use these exact tokens; don't invent others):
'abandoned','accepted','added','answered','assessed','assigned','awarded','becameoverdue',
'blocked','called','created','deleted','disabled','downloaded','duplicated','edited','enabled',
'ended','epas','evaluated','exported','fail','failed','graded','granted','group','imported',
'joined','launched','left','leveledup','locked','loggedin','loggedinas','loggedout','migrated',
'moved','prevented','previewed','printed','published','reassessed','received','reevaluated',
'regraded','removed','reset','restarted','restored','resumed','reviewed','saved','searched',
'sent','shown','started','stream','student','submitted','success','switched','taken','text',
'unassigned','unblocked','unlocked','unpublished','updated','uploaded','viewed'

Canonical event meanings:
- Login events: action IN ('loggedin','loggedinas')
- Logout events: action = 'loggedout'
- Views: action = 'viewed'

Time rules:
- Prefer "time" (quote it: "time") for time-of-day questions if it’s non-null.
- Otherwise derive a timestamp from the epoch: to_timestamp(timecreated).
- "datetime" may already be a timestamp. Choose the simplest correct source for the task.

CTE & scope rules:
- If you use a CTE (WITH ...), any column referenced later MUST be selected in that CTE.
- Only reference columns that exist in the current scope. Do not invent columns.

Formatting rules:
- Use only standard PostgreSQL functions (EXTRACT, COUNT, SUM, AVG, date_trunc, make_interval, floor, etc.).
- Return exactly ONE complete SQL statement ending with a semicolon, then the token <END>.
- No comments, no markdown, no prose.
- If the request cannot be answered with the available columns, return: CANNOT_ANSWER;

Examples (study patterns; do NOT echo unless asked):

-- Example A: first 100 rows
SELECT * FROM moodle_data ORDER BY id LIMIT 100;

-- Example B: most common 15-minute login window (using "time"; fallback to epoch if needed)
WITH logins AS (
  SELECT COALESCE("time"::time, (to_timestamp(timecreated))::time) AS t
  FROM moodle_data
  WHERE action IN ('loggedin','loggedinas')
),
binned AS (
  SELECT make_time(
           EXTRACT(HOUR FROM t)::int,
           (FLOOR(EXTRACT(MINUTE FROM t)/15)::int)*15,
           0
         ) AS window_start
  FROM logins
)
SELECT
  window_start,
  window_start + INTERVAL '15 minutes' AS window_end,
  COUNT(*) AS login_count
FROM binned
GROUP BY window_start
ORDER BY login_count DESC
LIMIT 1;

Task:
{input}

SQL:
"""
)

# ---------- 5) Helpers ----------
def _cleanup(sql: str) -> str:
    return (
        sql.replace(", FROM", " FROM")
           .replace("HAVG", "AVG")
           .replace("TIMESTAMPTOSTRING", "to_char")
           .strip()
    )

def extract_sql(text: str) -> str:
    """Extract a single SQL query (supports CTEs with WITH ...)."""
    if "CANNOT_ANSWER" in text:
        raise ValueError("Model refused: CANNOT_ANSWER (missing columns)")
    text = text.split("<END>", 1)[0]
    lower = text.lower()
    if "with" in lower:
        start = lower.find("with")
        end = text.rfind(";")
        if start != -1 and end != -1 and end > start:
            return _cleanup(text[start:end + 1])
    m = re.search(r"(?is)\bselect\b[\s\S]*?;", text)
    if m:
        return _cleanup(m.group(0))
    m2 = re.search(r"(?is)\bselect\b[\s\S]*$", text)
    if m2:
        sql = m2.group(0).strip()
        if not sql.endswith(";"):
            sql += ";"
        return _cleanup(sql)
    raise ValueError("No SQL query found in LLM output")

def summarize_db_error(err: Exception) -> Optional[str]:
    msg = str(err)
    m = re.search(r'column "([^"]+)" does not exist', msg, flags=re.IGNORECASE)
    if m:
        col = m.group(1)
        return (
            f'You referenced column "{col}" that is not in scope. '
            f'If you used a CTE, include "{col}" in that CTE\'s SELECT list or reference the correct column name. '
            f'Only reference columns that are selected in the current scope.'
        )
    if "relation" in msg.lower() and "does not exist" in msg.lower():
        return "You referenced a table or alias that does not exist. Use only the table moodle_data."
    if "syntax error" in msg.lower():
        return (
            "Your SQL has a syntax error. Ensure each CTE and SELECT is properly closed, "
            "lists do not end with dangling commas, and the final statement ends with a semicolon."
        )
    if "timestamp" in msg.lower() or "time zone" in msg.lower():
        return (
            "You likely applied a timestamp function to a non-timestamp column. "
            "Use to_timestamp(timecreated) for epoch; use datetime directly if it is a timestamp; "
            "avoid string concatenation with timestamps."
        )
    return None

def _serialize_rows(rows, columns, max_rows=5, str_max_len=200):
    out = []
    for r in rows[:max_rows]:
        obj = {}
        for c, v in zip(columns, r):
            if hasattr(v, "isoformat"):
                try:
                    obj[c] = v.isoformat()
                    continue
                except Exception:
                    pass
            if isinstance(v, str):
                obj[c] = (v if len(v) <= str_max_len else v[:str_max_len] + "…")
            else:
                obj[c] = str(v) if v is not None else None
        out.append(obj)
    return out

def summarize_result(question: str, sql: str, columns, rows):
    total_rows = len(rows)
    sample_rows_cap = 2 if total_rows > 20 else 5
    sample = _serialize_rows(rows, columns, max_rows=sample_rows_cap, str_max_len=160)

    # Trim columns list if it’s huge (keep first N)
    cols_list = list(columns)
    if len(cols_list) > 12:
        cols_list = cols_list[:12]

    payload = {
        "question": question,
        "sql": sql[:4000],  # guard against giant SQL strings
        "columns": cols_list,
        "total_rows": total_rows,
        "sample_rows": sample,
    }
    payload_str = json.dumps(payload, ensure_ascii=False)

    # Hard cap payload size (shrink further if needed)
    if len(payload_str) > 8000:
        payload["sample_rows"] = _serialize_rows(rows, columns, max_rows=1, str_max_len=120)
        payload["columns"] = cols_list[:8]
        payload_str = json.dumps(payload, ensure_ascii=False)
    if len(payload_str) > 8000:
        payload["sample_rows"] = []
        payload["columns"] = cols_list[:5]
        payload_str = json.dumps(payload, ensure_ascii=False)

    instructions = (
        "You are a precise analyst. Based ONLY on the provided SQL result JSON, "
        "answer the user's question in ONE concise sentence. "
        "Do not invent values not present in the result. "
        "If there are zero rows, say that no rows matched the criteria. "
        "If the result is a single aggregated row, state the key value(s). "
        "If multiple rows, summarize the key takeaway."
    )
    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": payload_str},
    ]
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.1,
        top_p=0.9,
        max_tokens=100,
        seed=42,
    )
    return resp.choices[0].message.content.strip()

def ask_question(question: str, retries: int = 4):
    start = time.time()
    schema = db.get_table_info()

    messages = [
        {"role": "system", "content": "You are a precise PostgreSQL SQL generator. Output only SQL."},
        {"role": "user", "content": sql_prompt.format(input=question, table_info=schema)},
    ]

    for attempt in range(1, retries + 1):
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.0,
            top_p=0.9,
            max_tokens=350,
            seed=42,
            stop=["<END>"],
        )

        llm_output = response.choices[0].message.content.strip()
        print(f"\n[LLM Raw Output]\n{llm_output}")

        try:
            sql = extract_sql(llm_output)
            print(f"\n[Final SQL to execute]\n{sql}")

            with engine.connect() as conn:
                result = conn.exec_driver_sql(sql)
                rows = result.fetchall()
                columns = result.keys()

            print("\n[Query Results]\n", rows)

            # Skip summarization for large dumps to avoid context overflow
            if len(rows) > 20:
                print("\n[Answer]\nReturned", len(rows), "rows. (Summary skipped for large result.)")
            else:
                human = summarize_result(question, sql, columns, rows)
                print("\n[Answer]\n", human)

            elapsed = time.time() - start
            print(f"\nSuccess in {elapsed:.2f} seconds (attempt {attempt})")
            return
        except (SQLAlchemyError, Exception) as e:
            print(f"Attempt {attempt} failed: {e}\n")

            if attempt >= retries:
                print("Query completely failed after retries.")
                return

            guidance = summarize_db_error(e)
            correction = (
                "Correct the SQL.\n"
                "- Only one complete SQL statement ending with a semicolon.\n"
                "- If you used a CTE, only reference columns selected by that CTE; add any needed columns to the CTE output.\n"
                "- Use only columns that exist in moodle_data. Do not invent column names.\n"
                "- Prefer \"time\" when non-null; otherwise use to_timestamp(timecreated).\n"
                "- For logins, use action IN ('loggedin','loggedinas'); for logout action='loggedout'.\n"
            )
            if guidance:
                correction += f"\nSpecific error to fix: {guidance}\n"

            messages.extend([
                {"role": "assistant", "content": llm_output},
                {
                    "role": "user",
                    "content": (
                        f"The SQL above failed with error:\n{e}\n\n"
                        f"{correction}\n"
                        f"Database schema for reference:\n{schema}\n\n"
                        "Return only the corrected SQL statement ending with a semicolon, then <END>."
                    ),
                },
            ])

# ---------- Entry ----------
if __name__ == "__main__":
    q = input("Enter your question: ")
    ask_question(q)
