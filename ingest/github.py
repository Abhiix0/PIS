import random
from datetime import date, timedelta
from ingest.db_connection import get_connection
from ingest.validators import validate_github_record

# Profile map: student_id → list of (repo_name, max_commits, date_spread_days)
GITHUB_PROFILES = {
    1: [('dsa-solutions', 80, 180), ('ml-project', 60, 150),
         ('portfolio', 40, 120), ('api-server', 55, 90)],
    2: [('competitive-cp', 70, 160), ('web-app', 50, 130),
         ('blog-site', 35, 100)],
    3: [('leetcode-grind', 10, 60)],             # coder, weak GH
    4: [('practice-repo', 8, 45)],
    5: [('open-source-contrib', 120, 180),        # GH-heavy
         ('devtools', 90, 150), ('cli-utils', 75, 120),
         ('react-components', 60, 100)],
    6: [('fullstack-app', 100, 170), ('data-viz', 80, 140),
         ('automation-scripts', 55, 110)],
    7: [('hello-world', 4, 30)],                # weak overall
    8: [],                                        # zero GitHub activity
}

def generate_github_records(student_id: int) -> list[dict]:
    repos = GITHUB_PROFILES[student_id]
    records = []
    start_date = date.today() - timedelta(days=180)

    for repo_name, max_commits, spread in repos:
        # Each repo gets 3–8 commit "snapshots" spread over time
        num_snapshots = random.randint(3, 8)
        for _ in range(num_snapshots):
            days_offset = random.randint(0, spread)
            commits = random.randint(1, max(1, max_commits // num_snapshots))
            records.append({
                'student_id':  student_id,
                'repo_name':   repo_name,
                'commits':     commits,
                'commit_date': start_date + timedelta(days=days_offset),
            })
    return records

def ingest_github_activity(student_id: int = None) -> dict:
    total_inserted = 0
    total_skipped  = 0

    if student_id is not None:
        if student_id not in GITHUB_PROFILES:
            raise ValueError(
                f"No synthetic profile defined for student_id={student_id}. "
                "Add it to GITHUB_PROFILES."
            )
        students_to_process = [student_id]
    else:
        students_to_process = list(GITHUB_PROFILES.keys())

    with get_connection() as conn:
        cur = conn.cursor()

        for sid in students_to_process:
            records = generate_github_records(sid)

            for record in records:
                try:
                    validate_github_record(record)
                except ValueError as e:
                    print(f"  [SKIP] student {sid}: {e}")
                    total_skipped += 1
                    continue

                cur.execute("""
                    INSERT INTO github_activity
                        (student_id, repo_name, commits, commit_date)
                    VALUES
                        (%(student_id)s, %(repo_name)s,
                         %(commits)s, %(commit_date)s)
                    ON CONFLICT (student_id, repo_name, commit_date) DO NOTHING
                """, record)

                if cur.rowcount == 1:
                    total_inserted += 1
                else:
                    total_skipped += 1

    print(f"GitHub ingestion complete: {total_inserted} inserted, {total_skipped} skipped")
    return {'inserted': total_inserted, 'skipped': total_skipped}


if __name__ == "__main__":
    result = ingest_github_activity()
    print(result)