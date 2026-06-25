-- Ad-hoc query (edit + push to re-run). Currently: full permit_amendment silver error.
SELECT TOP 1 entity,
       LEFT(CAST(error_message AS varchar(4000)), 400) AS error_message,
       LEFT(CAST(stack_trace AS varchar(8000)), 4000)  AS stack_trace
FROM app.error_log
WHERE layer = 'silver' AND entity = 'permit_amendment'
ORDER BY created_date DESC;
GO
