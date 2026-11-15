"""Source-only retrieval for IAF, with optional model-assisted passage selection."""
import json
import os
import re
import urllib.request
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

KNOWLEDGE = json.loads(Path(__file__).with_name("iaf-knowledge.json").read_text(encoding="utf-8"))
MAX_QUESTION = 400

def retrieve(question: str):
    normalized = ' '.join(re.findall(r"[a-z0-9,]+", question.casefold()))
    ranked = []
    for item in KNOWLEDGE:
        matches = [term for term in item["phrases"] if f" {term} " in f" {normalized} "]
        if matches:
            score = 2 * max(len(term.split()) for term in matches) + len(matches)
            ranked.append((score, item, matches))
    ranked.sort(key=lambda match: match[0], reverse=True)
    return ranked[:3]

def reserve(database_url: str) -> bool:
    with psycopg.connect(database_url, connect_timeout=3, row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL statement_timeout = '1800ms'")
            return bool(conn.execute(
                "SELECT sentinel_demo.reserve_iaf_call() AS allowed"
            ).fetchone()["allowed"])

def select_passage(matches, api_key: str):
    allowed = [match[1]["id"] for match in matches]
    cues = sorted({term for match in matches for term in match[2]})
    choices = [{key: match[1][key] for key in ("id", "title", "answer")} for match in matches]
    schema = {"type":"object", "properties":{"id":{"type":"string","enum":allowed}},
              "required":["id"], "additionalProperties":False}
    payload = {
        "model": "gpt-4o-mini",
        "store": False,
        "max_output_tokens": 80,
        "instructions": "Select the public passage that best matches the topic cues. Return its ID.",
        "input": json.dumps({"cues": cues, "passages": choices}, ensure_ascii=True),
        "text":{"format":{"type":"json_schema","name":"iaf_passage","strict":True,"schema":schema}},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=7) as response:
        body = json.loads(response.read(128_000))
    for item in body.get("output", []):
        for part in item.get("content", []):
            if part.get("type") == "output_text":
                pick = json.loads(part["text"])["id"]
                return pick if pick in allowed else None
    return None

def answer(question: str, database_url: str):
    matches = retrieve(question)
    if not matches:
        return {"kind":"out_of_scope"}
    result = matches[0][1]
    method = "library"
    api_key = os.environ.get("IAF_OPENAI_API_KEY")
    if api_key:
        try:
            if reserve(database_url):
                selected = select_passage(matches, api_key)
                if selected:
                    result = next(item for _, item, _ in matches if item["id"] == selected)
                    method = "model_selected"
        except (OSError, ValueError, KeyError, TypeError, AttributeError, psycopg.Error):
            # Preserve availability through credential, provider or quota failures.
            pass
    return {"kind":"answer", "method":method,
            **{key:result[key] for key in ("title","answer","url","source")}}
