from datetime import date

VALID_DIFFICULTIES = {'easy', 'medium', 'hard'}

def validate_coding_record(record: dict) -> None:
    """Raises ValueError if the record is invalid."""
    if not record.get('student_id'):
        raise ValueError("student_id is required")
    if not record.get('problem_id'):
        raise ValueError("problem_id is required")
    if record.get('difficulty') not in VALID_DIFFICULTIES:
        raise ValueError(
            f"difficulty must be one of {VALID_DIFFICULTIES}, "
            f"got: {record.get('difficulty')}"
        )
    solved = record.get('solved_at')
    if solved and solved > date.today():
        raise ValueError(f"solved_at cannot be a future date: {solved}")

def validate_github_record(record: dict) -> None:
    """Raises ValueError if the record is invalid."""
    if not record.get('student_id'):
        raise ValueError("student_id is required")
    if not record.get('repo_name'):
        raise ValueError("repo_name is required")
    if not isinstance(record.get('commits'), int) or record['commits'] <= 0:
        raise ValueError(f"commits must be a positive integer")
    cd = record.get('commit_date')
    if cd and cd > date.today():
        raise ValueError(f"commit_date cannot be a future date: {cd}")