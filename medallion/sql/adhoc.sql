-- Did permit_amendment fail recently? Compare now to its last silver error.
SELECT SYSUTCDATETIME() AS now_utc,
       (SELECT MAX(created_date) FROM app.error_log
        WHERE layer='silver' AND entity='permit_amendment') AS last_pa_silver_error,
       (SELECT COUNT(*) FROM app.error_log
        WHERE layer='silver' AND entity='permit_amendment'
          AND created_date >= DATEADD(minute, -10, SYSUTCDATETIME())) AS pa_errors_last_10min;
GO
