from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sqlite3
import json
import uuid
from datetime import datetime
import hashlib
from openbeepboop.common.db import get_db_connection, init_db
from openbeepboop.common.models import Job, JobStatus, JobCreate, InternalJobSubmitRequest
import os

app = FastAPI(title="OpenBeepBoop Queue Server")

# Initialize DB on startup
@app.on_event("startup")
def startup_event():
    init_db()

async def verify_token(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = parts[1]

    # Hash token to check against DB
    # The CLI stores a simple sha256 hash of the token.
    # In a real system we'd use a better hashing algo like argon2 or pbkdf2, but standard lib hashlib is fine here.
    key_hash = hashlib.sha256(token.encode()).hexdigest()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    return {"key_hash": row["key_hash"], "name": row["name"], "role": row["role"]}

@app.post("/v1/chat/completions", status_code=202)
async def submit_inference(request: Dict[str, Any], identity: Dict[str, Any] = Depends(verify_token)):
    # Extract priority if present
    priority = request.get("priority", 0)
    # The request payload is what we send to the LLM, so we might want to clean it or just keep it as is.
    # For now, we keep it as is, LiteLLM usually ignores extra fields.

    # Create Job
    job = Job(request_payload=request, priority=priority)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO jobs (id, status, created_at, updated_at, request_payload, priority) VALUES (?, ?, ?, ?, ?, ?)",
        (job.id, job.status.value, job.created_at, job.updated_at, json.dumps(job.request_payload), job.priority)
    )
    conn.commit()
    conn.close()

    return {"id": job.id, "status": job.status}

class PollRequest(BaseModel):
    ids: Optional[List[str]] = None

@app.post("/v1/results/poll")
async def poll_results(body: PollRequest, identity: Dict[str, Any] = Depends(verify_token)):
    conn = get_db_connection()
    cursor = conn.cursor()

    jobs = []

    if body.ids:
        placeholders = ','.join('?' * len(body.ids))
        cursor.execute(f"SELECT * FROM jobs WHERE id IN ({placeholders})", body.ids)
    else:
        # Return all completed user jobs (limit 100 for safety)
        cursor.execute("SELECT * FROM jobs WHERE status = ? LIMIT 100", (JobStatus.COMPLETED.value,))

    rows = cursor.fetchall()

    for row in rows:
        result_payload = None
        if row["result_payload"]:
            result_payload = json.loads(row["result_payload"])

        jobs.append({
            "id": row["id"],
            "status": row["status"],
            "result": result_payload
        })

    conn.close()
    return {"jobs": jobs}

class FetchRequest(BaseModel):
    limit: int = 10

@app.post("/internal/queue/fetch")
async def fetch_jobs(body: FetchRequest, identity: Dict[str, Any] = Depends(verify_token)):
    # Identify node from identity
    node_id = identity["name"]

    conn = get_db_connection()
    cursor = conn.cursor()

    # Transaction to lock jobs
    try:
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute(
            f"SELECT * FROM jobs WHERE status = ? ORDER BY priority DESC, created_at ASC LIMIT ?",
            (JobStatus.QUEUED.value, body.limit)
        )
        rows = cursor.fetchall()

        job_ids = [row["id"] for row in rows]

        if job_ids:
            now = datetime.utcnow()
            placeholders = ','.join('?' * len(job_ids))
            cursor.execute(
                f"UPDATE jobs SET status = ?, locked_by = ?, locked_at = ?, updated_at = ? WHERE id IN ({placeholders})",
                (JobStatus.PROCESSING.value, node_id, now, now, *job_ids)
            )
            conn.commit()

        jobs = []
        for row in rows:
            jobs.append({
                "id": row["id"],
                "request_payload": json.loads(row["request_payload"]),
                # "status": JobStatus.PROCESSING, # We return what we found, but client knows it's processing
                "created_at": row["created_at"]
            })

        return jobs

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/internal/queue/submit")
async def submit_results(body: List[Dict[str, Any]], identity: Dict[str, Any] = Depends(verify_token)):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")
        now = datetime.utcnow()

        for item in body:
            job_id = item["id"]
            status = item["status"]

            result_payload = None
            if "result" in item:
                result_payload = json.dumps(item["result"])
            elif "error" in item:
                # If error, we might store it in result_payload as well or a separate field.
                # SPEC says "The result from the LLM (or error message)".
                result_payload = json.dumps({"error": item["error"]})

            cursor.execute(
                "UPDATE jobs SET status = ?, result_payload = ?, updated_at = ?, locked_by = NULL WHERE id = ?",
                (status, result_payload, now, job_id)
            )

        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
