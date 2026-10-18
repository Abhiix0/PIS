## Query Optimization Results

### Query 2: Single-student feature lookup
**Before indexing:**
  Seq Scan on features (cost=0.00..1.08 rows=8) actual time=0.012ms

**After covering index:**
  Index Only Scan on idx_features_covering  actual time=0.004ms

**Improvement:** ~3× faster. Index-only scan avoids heap access entirely.

### Interview talking point:
"I used a covering index on the features table — it includes all the
columns the API reads, so PostgreSQL satisfies the query from the
index alone without touching the heap. This is especially valuable
because GET /features/{id} is called before every prediction."
