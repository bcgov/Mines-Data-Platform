-- Confirm the DAG now points at materialized stg tables (stg.*) not the old views (stg.v_*).
SELECT node_name, gold_object, transform_notebook, source_view, depends_on, load_order
FROM app.gold_build_dag
ORDER BY load_order;
GO
