BEGIN;
UPDATE reservations SET worker_id = NULL WHERE worker_id IS NOT NULL;
UPDATE workers SET id = 1001 WHERE name = 'worker1';
UPDATE workers SET id = 1002 WHERE name = 'worker2';
UPDATE workers SET id = 1003 WHERE name = 'worker3';

UPDATE workers SET id = 1 WHERE name = 'worker1';
UPDATE workers SET id = 2 WHERE name = 'worker2';
UPDATE workers SET id = 3 WHERE name = 'worker3';

SELECT setval('workers_id_seq', 3);

UPDATE reservations SET worker_id = 2 WHERE id = 1;
COMMIT;
