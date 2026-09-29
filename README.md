# Natural Language to SQL for Moodle Logs

A tool that lets a user ask a question about Moodle activity logs in plain language. It writes the SQL query, runs it on a PostgreSQL database, and returns a short answer. It runs fully on a local computer, using small open-source language models.

This is the code for my diploma thesis at the National Technical University of Athens (NTUA).

- **Thesis:** *Utilization of Generative Artificial Intelligence Tools for Data Analysis in Distributed Educational Environments*
- **Author:** Gioni Zatse
- **Supervisor:** Prof. Petros Stefaneas
- **School:** School of Applied Mathematical and Physical Sciences, NTUA
- **Date:** February 2026
- **Language:** the thesis is written in **Greek**. It has an English abstract.

## Files in this repository

| File | Content |
|---|---|
| `code.py` | The tool: question → SQL → run → answer, with error correction. |
| `data_cleaning.txt` | The code used to clean the raw Moodle logs (Dask and Pandas). |
| `Thesis_Gioni_Zatse.pdf` | The full thesis (Greek). |
| `README.md` | This file. |

## How the tool works

**Question → SQL → Run → Answer**

1. The code reads the structure of the database table (column names and types).
2. It builds a prompt. The prompt has the table structure, the allowed values of the `action` column, rules for the output (one SQL statement only, no extra text), and one example.
3. It sends the prompt to a language model running in [LM Studio](https://lmstudio.ai/), through LM Studio's OpenAI-compatible API. No data leaves the computer.
4. It takes the SQL from the model's answer and runs it in PostgreSQL.
5. If the query fails, the code sends the database error message back to the model with a short hint, for example "column X does not exist". The model then writes a corrected query. The code tries up to 4 times.
6. When the query works, the model writes a one-sentence answer from the result.

Main tools: Python, PostgreSQL, SQLAlchemy, LangChain (prompt template and table structure), LM Studio.

The thesis also describes how to expose the table as a REST API with PostgREST. This is optional. The code in this repository connects to PostgreSQL directly.

## Data

The data are Moodle logs. Each row is one event, for example a user viewing a course.

- The original file had **58,153,450** records.
- I cleaned it in a Jupyter Notebook with Dask. Dask is a Python library that processes data in parts, so it can handle files too big for memory.
- Cleaning steps:
  - Removed exact duplicate rows.
  - Removed rows with `origin = "cli"`. These are automatic or admin actions, not real user behavior. This was the biggest reduction.
  - Removed 5 columns that were mostly empty or not useful: `ip`, `realuserid`, `objectid`, `objecttable`, `other`.
  - Created `datetime`, `time`, `day` and `month` from `timecreated` (Unix time). The original `timecreated` is kept.
- Result: **2,477,467 records** and **20 columns**, stored in the PostgreSQL table `moodle_data`.

Columns: `id, eventname, component, action, target, crud, edulevel, contextid, contextlevel, contextinstanceid, userid, courseid, relateduserid, anonymous, timecreated, origin, datetime, time, day, month`

**The Moodle logs are not included in this repository**, because of privacy and data protection.

## Evaluation

I tested three models that run locally in LM Studio:

| Model | Size |
|---|---|
| Hermes Llama 3.2 | 3B |
| Phi-4 Mini Instruct | 3B |
| DeepSeek Chat | 7B |

**Setup**
- 4 test questions in English, for example "Top 20 courses by number of 'viewed' actions" and "What is the most popular 15-minute window for log-ins?"
- 2 temperature settings: 0.1 and 0.5. (Temperature controls how random the model's output is.)
- Each question was run 10 times for each model and each temperature. That is 80 runs per model.
- All models used the same code and the same prompt. Only the model, the temperature and the question changed.
- Computer: AMD Ryzen 5 2600, RTX 3060 Ti (8 GB), 16 GB RAM.

**A run counts as correct when** the SQL runs and gives the right result. I report two numbers:
- **Acceptable:** correct, even if I changed the wording of the question a little (the meaning stayed the same). Small models are sensitive to wording.
- **Without changes:** correct with the original question, with no change at all. This is the stricter number.

| Model | Acceptable | Without changes |
|---|---|---|
| Hermes Llama 3.2 (3B) | 80 / 80 (100%) | 76 / 80 (95%) |
| Phi-4 Mini Instruct (3B) | 75 / 80 (93.75%) | 29 / 80 (36.25%) |
| DeepSeek Chat (7B) | 20 / 80 (25%) | 15 / 80 (18.75%) |

**Main findings**
- Hermes Llama 3.2 was the most reliable, even though it is one of the smallest models.
- DeepSeek often added text around the SQL and invented columns or answers. It may have done better with a prompt made for its reasoning style. I used one prompt for all models to keep the comparison fair.
- Common errors: columns that do not exist, syntax errors in queries that start with `WITH`, and wrong handling of time columns. The error-feedback loop often fixed them.
- Response time was similar for all models: about 4 seconds for the simplest question and about 2 minutes for the others, on this computer.

**Limits**
- Only 4 different questions were tested (each 10 times), so the results show a trend and are not a full benchmark.
- The models are small (3B to 7B parameters). Larger models would likely do better.
- All tests ran on one computer.

## How to run

You need your own Moodle logs with the same 20 columns.

1. Install the packages:
```
   pip install langchain langchain-community openai sqlalchemy psycopg2-binary
```
2. Create a PostgreSQL database named `THESIS_DATABASE` and import your data into a table named `moodle_data`. The connection settings are at the top of `text_to_sql.py` (host `127.0.0.1`, port `5432`, user `postgres`).
3. Set the database password as an environment variable. Do not write it in the code.
   - Windows (PowerShell): `$env:PG_PASS="your_password"`
   - macOS / Linux: `export PG_PASS="your_password"`
4. Open LM Studio, load a model, and start the local server (default address `http://localhost:1234`). Set `MODEL_NAME` in `text_to_sql.py` to the same model name.
5. Run:
```
   python text_to_sql.py
```
   Then type your question.

## License

This repository is for academic and research use.
