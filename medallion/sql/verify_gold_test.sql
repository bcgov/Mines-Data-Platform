-- Results of nb_gold_test (update + soft-delete tests for dimension and fact).
SELECT test_name, entity, status,
       LEFT(CAST(detail AS varchar(4000)), 220) AS detail, run_ts
FROM app.gold_test_log
ORDER BY entity, test_name;
GO
