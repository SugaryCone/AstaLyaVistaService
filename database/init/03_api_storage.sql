BEGIN;

ALTER TABLE tasks
    ALTER COLUMN employee_id DROP NOT NULL,
    ALTER COLUMN deadline_at DROP NOT NULL,
    -- API принимает календарную дату; сохраняем день срока в часовом поясе проекта.
    ALTER COLUMN deadline_at TYPE DATE USING (deadline_at AT TIME ZONE 'Europe/Moscow')::DATE,
    ADD COLUMN spent_minutes INTEGER NOT NULL DEFAULT 0 CHECK (spent_minutes >= 0);

CREATE TABLE task_links (
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    linked_task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, linked_task_id),
    CHECK (task_id <> linked_task_id)
);

CREATE INDEX task_links_linked_task_id_idx ON task_links (linked_task_id);

COMMIT;
