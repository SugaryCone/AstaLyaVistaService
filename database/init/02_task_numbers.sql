BEGIN;

ALTER TABLE projects
    ADD COLUMN code VARCHAR(32),
    ADD COLUMN last_task_number BIGINT NOT NULL DEFAULT 0
        CHECK (last_task_number >= 0);

-- Коды существующих демопроектов. Новым проектам код задаётся при создании.
UPDATE projects
SET code = CASE id
    WHEN 1 THEN 'API'
    WHEN 2 THEN 'MOBILE'
    WHEN 3 THEN 'WEB'
    ELSE 'PROJECT' || id::TEXT
END;

ALTER TABLE projects
    ALTER COLUMN code SET NOT NULL,
    ADD CONSTRAINT projects_code_unique UNIQUE (code),
    ADD CONSTRAINT projects_code_not_blank CHECK (code = BTRIM(code) AND code <> '');

ALTER TABLE tasks ADD COLUMN number TEXT;

-- Существующие задачи нумеруются внутри проекта в порядке их ID.
WITH numbered_tasks AS (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY id) AS sequence
    FROM tasks
)
UPDATE tasks AS task
SET number = project.code || '-' || numbered.sequence::TEXT
FROM projects AS project, numbered_tasks AS numbered
WHERE task.id = numbered.id AND task.project_id = project.id;

UPDATE projects AS project
SET last_task_number = (
    SELECT COUNT(*) FROM tasks WHERE project_id = project.id
);

ALTER TABLE tasks
    ALTER COLUMN number SET NOT NULL,
    ADD CONSTRAINT tasks_number_unique UNIQUE (number);

CREATE FUNCTION assign_task_number() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.project_id IS DISTINCT FROM OLD.project_id THEN
        -- UPDATE блокирует строку проекта до завершения транзакции.
        UPDATE projects
        SET last_task_number = last_task_number + 1
        WHERE id = NEW.project_id
        RETURNING code || '-' || last_task_number::TEXT INTO NEW.number;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Project % does not exist', NEW.project_id
                USING ERRCODE = 'foreign_key_violation';
        END IF;
    ELSE
        NEW.number := OLD.number;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER tasks_assign_number
BEFORE INSERT OR UPDATE OF project_id, number ON tasks
FOR EACH ROW EXECUTE FUNCTION assign_task_number();

-- Смена кода после выдачи номеров нарушила бы их соответствие проекту.
CREATE FUNCTION protect_project_code() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.code IS DISTINCT FROM OLD.code AND OLD.last_task_number > 0 THEN
        RAISE EXCEPTION 'Project code cannot change after task numbers are assigned'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER projects_protect_code
BEFORE UPDATE OF code ON projects
FOR EACH ROW EXECUTE FUNCTION protect_project_code();

COMMIT;
