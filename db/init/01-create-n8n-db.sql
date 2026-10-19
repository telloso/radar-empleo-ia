-- Runs only on the first start, when the data volume is empty.
-- n8n gets its own database so its internal tables stay separate from job data.
CREATE DATABASE n8n;
