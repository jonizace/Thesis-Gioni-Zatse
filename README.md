# Generative AI for Data Analysis in Distributed Educational Environments

This repository contains the implementation and supporting material for my diploma thesis at the **National Technical University of Athens (NTUA)**, titled:

> **Utilization of Generative Artificial Intelligence Tools for Data Analysis in Distributed Educational Environments**

The project explores the use of **Large Language Models (LLMs)** and **Generative AI** to enable natural-language querying of educational data stored in a relational database.

## Overview

The system allows users to ask questions about **Moodle activity logs using natural language**, without requiring direct knowledge of SQL or the underlying database schema.

The core workflow is:

**Natural Language → SQL Generation → SQL Execution → Answer**

The generated SQL query is executed against a PostgreSQL database containing cleaned Moodle Logs, and the resulting data is transformed into a concise natural-language response.

## Architecture

The application is organized into several layers:

* **Data Processing** — Cleaning and preprocessing of Moodle Logs
* **Database** — PostgreSQL relational database
* **API** — PostgREST RESTful API
* **LLM Layer** — Local LLMs served through LM Studio
* **Orchestration** — LangChain for prompt management and workflow orchestration
* **Prompt Engineering** — Schema-aware prompts and SQL generation constraints
* **Error Handling** — Feedback and correction mechanism for failed SQL queries
* **Response Generation** — Conversion of query results into concise natural-language answers

## Technologies

* Python
* PostgreSQL
* PostgREST
* LangChain
* LM Studio
* Large Language Models (LLMs)
* Jupyter Notebook
* Moodle Logs

## Dataset

The project uses Moodle Logs as its primary data source.

The original dataset contained approximately **58 million records**. After preprocessing, duplicate removal, filtering of system-generated events, removal of unsuitable fields, and transformation of temporal data, the final dataset contained:

* **2,477,467 records**
* **20 columns**

The processed data is organized in the PostgreSQL table:

```text
moodle_data
```

Due to privacy and data-protection considerations, the original Moodle Logs are **not included in this repository**.

## LLM Evaluation

The system was evaluated using three locally hosted models:

| Model               | Size |
| ------------------- | ---: |
| Hermes Llama 3.2    |   3B |
| Phi-4 Mini Instruct |   3B |
| DeepSeek Chat       |   7B |

The evaluation considered different prompt configurations and temperature settings, using:

* SQL success rate
* Query execution time
* Semantic correctness of generated SQL
* Error correction requirements

The experiments showed differences in reliability between the evaluated models for the specific Moodle database schema and prompts used in the study.

## Repository Structure

```text
.
├── data/              # Data preparation and processing
├── notebooks/         # Jupyter notebooks
├── src/               # Application source code
├── prompts/           # Prompt templates
├── sql/               # SQL queries and database-related files
├── api/               # PostgREST configuration
├── results/           # Evaluation results
├── thesis/            # Diploma thesis
└── README.md
```

*The exact structure may vary depending on the files included in the repository.*

## Running the Project

The application requires a local environment with the necessary Python dependencies, PostgreSQL database, PostgREST, and LM Studio.

### 1. Prepare the database

Create a PostgreSQL database and import the processed Moodle dataset into:

```text
moodle_data
```

### 2. Configure PostgREST

Configure PostgREST to expose the required PostgreSQL resources through a REST API.

### 3. Start LM Studio

Run LM Studio locally and load one of the evaluated LLMs.

The application communicates with LM Studio through its **OpenAI-compatible API**.

### 4. Run the application

Install the required Python dependencies and execute the relevant notebook or Python application.

The user can then submit questions in natural language, which are translated into SQL, executed against PostgreSQL, and returned as concise answers.

## Thesis

The complete diploma thesis is available in this repository:

**[Thesis PDF](./thesis/Thesis%20Gioni%20Zatse.pdf)**

The thesis was completed at the:

**National Technical University of Athens (NTUA)**
School of Applied Mathematical and Physical Sciences

**Author:** Gioni Zatse
**Supervisor:** Prof. Petros Stefaneas
**Date:** February 2026

## Key Concepts

* Generative Artificial Intelligence
* Large Language Models
* Natural Language to SQL (Text-to-SQL)
* Learning Analytics
* Moodle Logs
* Prompt Engineering
* Relational Databases
* PostgreSQL
* REST APIs
* LangChain
* Local LLM Inference

## License

This repository is intended primarily for academic and research purposes.

Please note that the original Moodle dataset is not included because of privacy and data-protection considerations.
