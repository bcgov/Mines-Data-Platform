# Hand-off (3): route pipeline errors to the centralized `app.error_log`

> **For:** whoever maintains the ingestion Data Factory pipeline `pl_ingest_mds`.
> **Goal:** on a pipeline failure, also write a row to `app.error_log` (the centralized error store), so pipeline AND notebook errors live in one queryable table.
> **Effort:** add ONE NonQuery script statement to the existing `Log_Failure` Script activity. No new activity, no schema changes (the `app.error_log` table already exists with the right shape).

## Where
The pipeline already has a **`Log_Failure`** Script activity that runs when `Copy_to_Raw` fails (inside the `ForEach_ControlRows`). It currently runs two `NonQuery` scripts: (1) `UPDATE app.pipeline_log … status='FAILED'`, (2) `UPDATE app.pipeline_control … last_run_status='FAILED'`. **Add a third `NonQuery` script** (same `externalReferences.connection` as the others — the warehouse connection):

## The script (Pipeline expression — `NonQuery`)

```
@concat(
 'INSERT INTO [app].[error_log] ',
 '([error_id],[layer],[pipeline_name],[run_id],[entity],[target_table],[error_message],[error_code],[created_date]) ',
 'VALUES (CAST(NEWID() AS varchar(36)),''ingest'',''',
 pipeline().parameters.pipeline_name, ''',''',
 pipeline().RunId, ''',''',
 item().source_entity, ''',''',
 item().target_schema, '.', item().target_table, ''',''',
 replace(activity('Copy_to_Raw').output.errors[0].Message, '''', ''''''), ''',''',
 activity('Copy_to_Raw').output.errors[0].Code, ''',''',
 utcNow(), ''')'
)
```

This mirrors the existing `Log_Failure` expression style (the `replace(...,'''','''''')` doubles single quotes so error text doesn't break the SQL).

## Column notes
- `error_id` = `CAST(NEWID() AS varchar(36))` — Fabric Warehouse has no IDENTITY; the writer mints a GUID.
- `layer` = `'ingest'` (the discriminator for pipeline-sourced errors).
- `run_id` = `pipeline().RunId` — **this is the correlation key**: it equals `pipeline_log.run_id`, so you can join `error_log` ↔ `pipeline_log` on `run_id` (+ `entity`/`source_entity`) for full run context.
- `log_id` = left NULL here. If you want the literal `pipeline_log.log_id` on the error row, add a `Lookup` after `Log_Start` to fetch that row's `log_id` and substitute it in; otherwise `run_id` is sufficient to trace.
- `error_code` = the Copy activity's error code; `error_context`/`stack_trace` left NULL (not produced by ADF).
- `error_number`/`error_severity`/`error_state`/`error_procedure`/`error_line` = the SQL Server `TRY/CATCH` error fields (`ERROR_NUMBER()`, etc.). Not produced by ADF — leave NULL here. They exist for **other (stored-proc / SQL-based) processes** that write into this shared table and want to capture `CATCH`-block error metadata.

## Optional: pass lineage into notebooks
When a pipeline invokes a medallion notebook (bronze/silver/gold), pass `pipeline().RunId` (and the `pipeline_log.log_id` if you fetch it) as notebook parameters; the notebook's `log_error(...)` already accepts `run_id` / `log_id` / `pipeline_name` and will stamp them on its `app.error_log` rows. Direct notebook runs leave them null.

## Query / trace examples (for the client)
```sql
-- everything that failed, any source, newest first
SELECT layer, pipeline_name, entity, target_table, error_message, created_date
FROM app.error_log ORDER BY created_date DESC;

-- only pipeline (ingest) errors
SELECT * FROM app.error_log WHERE layer = 'ingest';

-- an error with its pipeline run context
SELECT e.*, p.status, p.start_time, p.end_time, p.rows_read, p.rows_written
FROM app.error_log e
JOIN app.pipeline_log p ON p.run_id = e.run_id AND p.source_entity = e.entity
WHERE e.layer = 'ingest';
```
