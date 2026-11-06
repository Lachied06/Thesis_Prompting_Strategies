import json
from pathlib import Path
from typing import List

from src.schemas import Task


def load_jsonl_tasks(path: str) -> List[Task]:
    tasks = []

    with Path(path).open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            record = json.loads(line)

            if "task_id" not in record or "prompt" not in record:
                raise ValueError(
                    f"Line {line_number}: every task needs task_id and prompt"
                )

            tasks.append(
                Task(
                    task_id=str(record["task_id"]),
                    dataset=str(record.get("dataset", "unknown")),
                    prompt=str(record["prompt"]),
                    reference_answer=record.get("reference_answer"),
                    source_context=record.get("source_context"),
                    metadata=record.get("metadata", {}),
                )
            )

    return tasks
