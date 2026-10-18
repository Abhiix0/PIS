import random
from datetime import date, timedelta

from ingest.db_connection import get_connection
from ingest.validators import validate_coding_record

# Profile map: student_id → (num_problems, difficulty_weights)
# weights = [easy, medium, hard] — must sum to 1.0
STUDENT_PROFILES = {
    1: (160, [0.1, 0.45, 0.45]),  # strong
    2: (140, [0.15, 0.45, 0.4]),  # strong
    3: (100, [0.2, 0.5, 0.3]),  # coder, weak GH
    4: (90, [0.25, 0.5, 0.25]),  # coder, weak GH
    5: (30, [0.6, 0.35, 0.05]),  # GH-heavy, weak DSA
    6: (35, [0.55, 0.4, 0.05]),  # GH-heavy, weak DSA
    7: (12, [0.8, 0.2, 0.0]),  # weak overall
    8: (15, [0.75, 0.25, 0.0]),  # weak overall
}


def generate_coding_records(student_id: int) -> list[dict]:
    num_problems, weights = STUDENT_PROFILES[student_id]
    difficulties = ["easy", "medium", "hard"]
    records = []
    # Spread dates across last 180 days — critical for consistency score
    start_date = date.today() - timedelta(days=180)

    for i in range(num_problems):
        days_offset = random.randint(0, 180)
        records.append(
            {
                "student_id": student_id,
                "problem_id": f"P{student_id:02d}{i + 1:04d}",  # unique per student
                "difficulty": random.choices(difficulties, weights=weights)[0],
                "solved_at": start_date + timedelta(days=days_offset),
            }
        )
    return records


def ingest_coding_activity(student_id: int | None = None) -> dict:
    total_inserted = 0
    total_skipped = 0

    if student_id is not None:
        if student_id not in STUDENT_PROFILES:
            raise ValueError(
                f"No synthetic profile defined for student_id={student_id}. "
                "Add it to STUDENT_PROFILES."
            )
        students_to_process = [student_id]
    else:
        students_to_process = list(STUDENT_PROFILES.keys())

    with get_connection() as conn:
        cur = conn.cursor()

        for sid in students_to_process:
            records = generate_coding_records(sid)

            for record in records:
                try:
                    validate_coding_record(record)  # Python validation first
                except ValueError as e:
                    print(f"  [SKIP] student {sid}: {e}")
                    total_skipped += 1
                    continue

                # Upsert: ON CONFLICT DO NOTHING skips duplicates silently
                cur.execute(
                    """
                    INSERT INTO coding_activity
                        (student_id, problem_id, difficulty, solved_at)
                    VALUES
                        (%(student_id)s, %(problem_id)s,
                         %(difficulty)s, %(solved_at)s)
                    ON CONFLICT (student_id, problem_id)
                    DO NOTHING
                """,
                    record,
                )

                if cur.rowcount == 1:
                    total_inserted += 1
                else:
                    total_skipped += 1

    print(f"Coding ingestion complete: {total_inserted} inserted, {total_skipped} skipped")
    return {"inserted": total_inserted, "skipped": total_skipped}


if __name__ == "__main__":
    result = ingest_coding_activity()
    print(result)
