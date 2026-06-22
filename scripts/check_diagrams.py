#!/usr/bin/env python3
"""
Проверяет Mermaid-диаграммы студентов на соответствие задаче и эталонному решению.
Использует AI gateway (из .env) для содержательного анализа.

Структура:
  tmp/repos/{student_id}/{task}.md  — файлы студентов
  tasks/{task}.md                   — описание задачи
  reference_solutions/{task}.cs     — эталонный код
  UML_GUIDE.md                      — правила оформления связей

Результат:
  tmp/results/{student_id}/{task}.md  — замечания или пустой файл
"""

import os
import re
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
TASKS_DIR = BASE_DIR / "tasks"
REFS_DIR = BASE_DIR / "reference_solutions"
REPOS_DIR = BASE_DIR / "tmp" / "repos"
RESULTS_DIR = BASE_DIR / "results"
UML_GUIDE = BASE_DIR / "UML_GUIDE.md"

# Имя файла задачи → имя файла эталона (без расширения совпадают)
TASKS = [
    "sboi",
    "homm",
    "geometry-2",
    "robots",
    "report_generator",
    "diff",
    "taxi_order",
    "graph_viz",
    "razriad",
    "painter",
]

# ---------------------------------------------------------------------------
# Настройка AI gateway
# ---------------------------------------------------------------------------

def load_dotenv(path: Path):
    """Минимальная загрузка .env без внешних зависимостей."""
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("RAIP_API_KEY", "")
BASE_URL = os.getenv("RAIP_BASE_URL", "").rstrip("/")
# Стандартный путь OpenAI-совместимого шлюза
CHAT_URL = f"{BASE_URL}/v1/chat/completions"
MODEL = os.getenv("RAIP_MODEL", "claude-sonnet-ccr")


def call_llm(system_prompt: str, user_message: str, retries: int = 3) -> str:
    """Отправляет запрос в AI gateway, возвращает текст ответа."""
    payload = json.dumps({
        "model": MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(CHAT_URL, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            if attempt == retries:
                raise RuntimeError(f"HTTP {e.code}: {err_body}") from e
            print(f"    ⚠️  HTTP {e.code}, попытка {attempt}/{retries}...")
            time.sleep(2 ** attempt)
        except Exception as e:
            if attempt == retries:
                raise
            print(f"    ⚠️  Ошибка: {e}, попытка {attempt}/{retries}...")
            time.sleep(2 ** attempt)


# ---------------------------------------------------------------------------
# Чтение файлов
# ---------------------------------------------------------------------------

def read_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def extract_mermaid(md_content: str) -> str | None:
    """Извлекает первый блок ```mermaid ... ``` из markdown."""
    match = re.search(r"```mermaid\s*\n(.*?)```", md_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Системный промпт
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Ты — проверяющий UML-диаграмм классов студентов.
Тебе дают: описание задачи и диаграмму студента в Mermaid.

Проверяй диаграмму исключительно относительно ТРЕБОВАНИЙ ЗАДАНИЯ.
Не ищи классы или методы, которых нет в описании — студент мог сделать всё правильно,
просто иначе структурировав код.

Твоя задача — найти ГРУБЫЕ ошибки и Мелкие неточности (неполный список методов, незначительные
расхождения в именах) — упомяни кратко одной строкой в конце, но не раздувай список.

Грубые ошибки (проверяй ОБЯЗАТЕЛЬНО каждый пункт):
1. Диаграмма не является classDiagram.
1. Диаграмма нарисована для другого задания (совершенно не совпадают описание задания и сущности в диаграмме)
3. Отсутствие ключевых сущностей, которые явно требуются заданием (например, если задание
   требует паттерн Visitor — должны быть интерфейс Visitor и его реализации).
4. Неправильный тип связи (например, --> вместо <|-- для наследования, --> вместо <|.. для
   реализации интерфейса). Используй UML_GUIDE для определения верного типа.
5. Если в задании есть запрет на использование каких либо типов и классов - они должны отсутствовать

Все остальные ошибки/недочеты и проблемы - считай их мелкими замечаниями.
Проверяй лояльно - нет цели завалить студентов. 

Формат ответа — строго следуй ему, никаких дополнительных пояснений и рассуждений:
- Если грубых ошибок НЕТ — первая строка: OK
- Если ошибки ЕСТЬ — нумерованный список, каждый пункт одной строкой.
  Пример: "1. Отсутствует интерфейс IVisitor, который требуется заданием."
- Мелкие замечания (если есть) — одной строкой в конце: "Мелкие замечания: ..."

Отвечай по-русски."""


def build_user_message(
    task_name: str,
    task_desc: str,
    uml_guide: str,
    student_diagram: str,
) -> str:
    parts = [
        f"## Задача: {task_name}",
        "",
        "### Описание задачи",
        task_desc,
        "",
        "### Правила оформления UML-связей (UML_GUIDE)",
        uml_guide,
        "",
        "### Диаграмма студента (Mermaid)",
        "```mermaid",
        student_diagram,
        "```",
        "",
        "Проверь диаграмму студента согласно инструкции выше.",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Постобработка ответа модели
# ---------------------------------------------------------------------------

def extract_verdict(raw: str) -> str:
    """
    Вырезает из ответа модели только итоговый вердикт.
    Ищет первую строку, начинающуюся с OK или с цифры (начало нумерованного списка).
    Всё до неё (рассуждения, заголовки) — отбрасывается.
    Возвращает "" если замечаний нет, иначе текст замечаний.
    """
    lines = raw.splitlines()
    verdict_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.upper().startswith("OK") or re.match(r"^\d+\.", stripped):
            verdict_start = i
            break

    if verdict_start is None:
        # Модель ответила в свободной форме — вернём как есть
        return raw.strip()

    verdict_lines = lines[verdict_start:]
    verdict = "\n".join(verdict_lines).strip()

    # Если вердикт начинается с OK — замечаний нет
    if verdict.upper().startswith("OK"):
        # Может быть "OK\nМелкие замечания: ..."
        rest = verdict[2:].strip()
        return rest if rest else ""

    return verdict


# ---------------------------------------------------------------------------
# Проверка на плагиат
# ---------------------------------------------------------------------------

PLAGIARISM_PROMPT = """Ты — детектор плагиата UML-диаграмм классов.
Тебе дают диаграмму проверяемого студента и список диаграмм других студентов, которые уже были сданы ранее.

Твоя задача — определить, не списал ли проверяемый студент свою диаграмму у кого-то из списка.

Критерии:
- Полное идентичность - разница только в пробелах и переводах строк
- Подозрительное сходство (50–90%): структура и большинство классов совпадают, но есть небольшие отличия.
- Самостоятельная работа (<50%): заметные структурные отличия, своя нотация.

Формат ответа — строго одна из трёх строк:
CLEAN
SUSPICIOUS: <student_id> (<краткое пояснение, одна строка>)
PLAGIAT: <student_id> (<краткое пояснение, одна строка>)

Если подозрений несколько — укажи наиболее похожего. Никаких дополнительных пояснений."""


def collect_submitted_diagrams(task_name: str, exclude_id: str) -> list[tuple[str, str]]:
    """Собирает диаграммы уже проверенных студентов для данной практики.
    Возвращает список (student_id, diagram_text).
    """
    result = []
    if not REPOS_DIR.exists():
        return result
    for repo_dir in sorted(REPOS_DIR.iterdir()):
        sid = repo_dir.name
        if sid == exclude_id or repo_dir.name.startswith("."):
            continue
        # Считаем студента "уже проверенным" если у него есть файл результата
        result_file = RESULTS_DIR / sid / f"{task_name}.md"
        if not result_file.exists():
            continue
        md = read_file(repo_dir / f"{task_name}.md")
        if not md:
            continue
        diagram = extract_mermaid(md)
        if diagram:
            result.append((sid, diagram))
    return result


def check_plagiarism(student_id: str, task_name: str, student_diagram: str) -> str | None:
    """
    Сравнивает диаграмму студента с уже сданными.
    Возвращает:
      None                       — всё чисто или не с чем сравнивать
      "SUSPICIOUS: ..."          — подозрение на списывание
      "PLAGIAT: ..."             — высокое сходство (>90%)
    """
    others = collect_submitted_diagrams(task_name, exclude_id=student_id)
    if not others:
        return None

    others_block = "\n\n".join(
        f"### {sid}\n```mermaid\n{diag}\n```" for sid, diag in others
    )
    user_msg = (
        f"## Диаграмма проверяемого студента ({student_id})\n"
        f"```mermaid\n{student_diagram}\n```\n\n"
        f"## Диаграммы других студентов\n{others_block}"
    )

    raw = call_llm(PLAGIARISM_PROMPT, user_msg).strip()

    if raw.startswith("PLAGIAT:"):
        return raw
    if raw.startswith("SUSPICIOUS:"):
        return raw
    return None


# ---------------------------------------------------------------------------
# Основная логика
# ---------------------------------------------------------------------------

def check_student_task(student_id: str, task_name: str, uml_guide: str) -> str | None:
    """
    Возвращает:
      None   — файл диаграммы у студента отсутствует (практика не сдана)
      ""     — ошибок нет
      str    — текст с замечаниями (может включать блок плагиата)
    """
    student_file = REPOS_DIR / student_id / f"{task_name}.md"
    md_content = read_file(student_file)
    if md_content is None:
        return None  # файл не сдан

    student_diagram = extract_mermaid(md_content)
    if student_diagram is None:
        return "Файл есть, но блок ```mermaid``` не найден или синтаксис неверен."

    task_desc = read_file(TASKS_DIR / f"{task_name}.md") or "(описание задачи недоступно)"

    user_msg = build_user_message(task_name, task_desc, uml_guide, student_diagram)
    verdict = extract_verdict(call_llm(SYSTEM_PROMPT, user_msg))

    plagiarism = check_plagiarism(student_id, task_name, student_diagram)
    if plagiarism:
        sep = "\n\n" if verdict else ""
        verdict = verdict + sep + f"⚠️ {plagiarism}"

    return verdict


def write_result(student_id: str, task_name: str, result: str):
    out_dir = RESULTS_DIR / student_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{task_name}.md"
    out_file.write_text(result, encoding="utf-8")


# ---------------------------------------------------------------------------
# Обновление results.md
# ---------------------------------------------------------------------------

STUDENTS_FILE = BASE_DIR / "students.md"
RESULTS_MD = BASE_DIR / "results.md"

# Человекочитаемые названия столбцов
TASK_LABELS = {
    "sboi":             "Сбои",
    "homm":             "HoMM",
    "geometry-2":       "Геометрия-2",
    "robots":           "Роботы",
    "report_generator": "Генератор отчётов",
    "diff":             "Дифф.",
    "taxi_order":       "TaxiOrder",
    "graph_viz":        "GraphViz",
    "razriad":          "Разряд",
    "painter":          "Painter",
}


def classify_result(text: str | None) -> str:
    """
    None            → практика не сдана
    "ok"            → замечаний нет
    "minor"         → только мелкие замечания
    "major"         → грубые ошибки
    "plagiat"       → полное списывание (>90%)
    "suspicious"    → подозрение на списывание
    """
    if text is None:
        return "not_submitted"
    if text.strip() == "Замечаний нет.":
        return "ok"
    # Проверяем плагиат — он может быть в любом месте текста
    if "⚠️ PLAGIAT:" in text:
        return "suspicious"
    if "⚠️ SUSPICIOUS:" in text:
        # Грубые ошибки важнее подозрения на списывание
        first_line = text.strip().splitlines()[0].strip()
        if not first_line.lower().startswith("мелкие ") and not first_line.upper().startswith("OK") and not first_line.upper().startswith("⚠️ SUSPICIOUS:"):
            return "major"
        return "suspicious"
    first_line = text.strip().splitlines()[0].strip()
    if first_line.lower().startswith("мелкие "):
        return "minor"
    return "major"


def cell_text(student_id: str, task_name: str) -> str:
    result_file = RESULTS_DIR / student_id / f"{task_name}.md"
    text = read_file(result_file)
    verdict = classify_result(text)
    rel_path = f"results/{student_id}/{task_name}.md"

    if verdict == "not_submitted":
        return "—"
    if verdict == "ok":
        return "зачтено"
    if verdict == "minor":
        return f"[зачтено, есть замечания]({rel_path})"
    if verdict == "suspicious":
        return f"[зачтено, подозрение на списывание]({rel_path})"
    if verdict == "plagiat":
        return f"[списывание]({rel_path})"
    # major
    return f"[не зачтено]({rel_path})"


def parse_students() -> list[tuple[str, str, str]]:
    """Возвращает список (ФИО, student_id, grade) из students.md.
    grade — значение колонки «Автомат» (пустая строка если не выставлена).
    """
    students = []
    # 3 или 4 колонки
    row_re = re.compile(r"^\|(.+?)\|(.+?)\|(.+?)\|(?:(.+?)\|)?$")
    text = read_file(STUDENTS_FILE)
    if not text:
        return students
    for line in text.splitlines():
        m = row_re.match(line.strip())
        if not m:
            continue
        name = m.group(1).strip()
        student_id = m.group(2).strip()
        grade = (m.group(4) or "").strip()
        if name.startswith("Студент") or name.startswith(":---"):
            continue
        students.append((name, student_id, grade))
    return students


import subprocess
from datetime import datetime, timezone


def _git_log(student_id: str, fmt: str) -> str:
    repo_path = REPOS_DIR / student_id
    if not repo_path.exists():
        return ""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", f"--format={fmt}"],
            capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip()
    except Exception:
        return ""


def get_repo_commit_hash(student_id: str) -> str:
    """Возвращает SHA последнего коммита в репо студента."""
    return _git_log(student_id, "%H")


def get_repo_commit_time(student_id: str) -> str:
    """Возвращает время последнего коммита репо в формате дд.мм.гггг чч:мм."""
    ts = _git_log(student_id, "%ci")  # "2026-06-09 10:46:32 +0500"
    if not ts:
        return "—"
    try:
        dt = ts[:16]  # "2026-06-09 10:46"
        date, time_part = dt.split(" ")
        y, mo, d = date.split("-")
        return f"{d}.{mo}.{y} {time_part}"
    except Exception:
        return "—"


LAST_CHECKED_FILE = ".last_checked_commit"


def get_last_checked_commit(student_id: str) -> str:
    """Читает хэш последнего проверенного коммита из results/{student_id}/.last_checked_commit"""
    f = RESULTS_DIR / student_id / LAST_CHECKED_FILE
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def save_last_checked_commit(student_id: str, commit_hash: str):
    out_dir = RESULTS_DIR / student_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / LAST_CHECKED_FILE).write_text(commit_hash, encoding="utf-8")


def get_last_checked_time(student_id: str) -> str:
    """Возвращает время последней проверки (mtime файла .last_checked_commit)."""
    f = RESULTS_DIR / student_id / LAST_CHECKED_FILE
    if not f.exists():
        return "—"
    try:
        mtime = f.stat().st_mtime
        dt = datetime.fromtimestamp(mtime)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return "—"


REQUIRED_FOR_3 = {"sboi", "homm", "geometry-2", "robots", "report_generator", "diff"}
EXTRA_TASKS = [t for t in TASKS if t not in REQUIRED_FOR_3]


def calc_grade(student_id: str, task_cells: list[str] | None = None) -> str:
    """Вычисляет автооценку на основании результатов проверки. Возвращает '3', '4', '5' или ''.

    task_cells — если передан, используется для определения зачёта вместо чтения файлов.
    Это важно, чтобы учесть защиту от понижения оценки, применяемую при построении таблицы.
    """
    if task_cells is not None:
        passed = {
            task for task, cell in zip(TASKS, task_cells)
            if _is_passed(cell)
        }
    else:
        passed = {
            task for task in TASKS
            if classify_result(read_file(RESULTS_DIR / student_id / f"{task}.md")) in ("ok", "minor", "suspicious")
        }
    if not REQUIRED_FOR_3.issubset(passed):
        return ""
    extra_passed = len(passed - REQUIRED_FOR_3)
    if extra_passed >= len(EXTRA_TASKS):
        return "5"
    if extra_passed >= 2:
        return "4"
    return "3"


def _is_passed(cell: str) -> bool:
    """Возвращает True если ячейка содержит зачёт (зачтено/suspicious)."""
    stripped = cell.strip()
    return stripped.startswith("зачтено") or stripped.startswith("[зачтено")


def _is_failed(cell: str) -> bool:
    """Возвращает True если ячейка содержит «не зачтено» или «списывание»."""
    return "не зачтено" in cell or "списывание" in cell


def read_current_cells(name: str) -> dict[str, str]:
    """Читает текущие значения ячеек заданий из results.md для данного студента.
    Возвращает словарь {task_name: cell_value}.
    """
    text = read_file(RESULTS_MD)
    if not text:
        return {}
    task_col_names = [TASK_LABELS[t] for t in TASKS]
    header_line = None
    data_line = None
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if "Студент" in cols:
            header_line = cols
        elif header_line and cols[0] == name:
            data_line = cols
            break
    if not header_line or not data_line:
        return {}
    result = {}
    for task, label in zip(TASKS, task_col_names):
        try:
            idx = header_line.index(label)
            result[task] = data_line[idx] if idx < len(data_line) else "—"
        except ValueError:
            result[task] = "—"
    return result


def update_results_md():
    students = parse_students()
    if not students:
        print("⚠️  Не удалось прочитать список студентов из students.md")
        return

    header_cols = ["Студент", "Оценка", "Последний коммит", "Последняя проверка"] + [TASK_LABELS[t] for t in TASKS]
    sep_cols = [":---", "---", "---", "---"] + ["---"] * len(TASKS)

    rows = [
        "| " + " | ".join(header_cols) + " |",
        "| " + " | ".join(sep_cols) + " |",
    ]

    for name, student_id, grade in students:
        commit_time = get_repo_commit_time(student_id)
        checked_time = get_last_checked_time(student_id)
        if grade:
            # ручная оценка — не пересчитываем, практики не показываем
            grade_cell = grade
            task_cells = ["—"] * len(TASKS)
        else:
            current_cells = read_current_cells(name)
            task_cells = []
            for task in TASKS:
                new_cell = cell_text(student_id, task)
                old_cell = current_cells.get(task, "—")
                # Защита: если было зачтено — не понижаем до «не зачтено»
                if _is_passed(old_cell) and _is_failed(new_cell):
                    task_cells.append(old_cell)
                else:
                    task_cells.append(new_cell)
            # Передаём уже защищённые ячейки, чтобы оценка соответствовала таблице
            grade_cell = calc_grade(student_id, task_cells)
        cells = [name, grade_cell, commit_time, checked_time] + task_cells
        rows.append("| " + " | ".join(cells) + " |")

    content = "\n".join(rows) + "\n"
    RESULTS_MD.write_text(content, encoding="utf-8")
    print(f"📊 results.md обновлён ({len(students)} студентов)")


def main():
    if not API_KEY:
        print("❌ RAIP_API_KEY не задан в .env")
        return
    if not BASE_URL:
        print("❌ RAIP_BASE_URL не задан в .env")
        return

    uml_guide = read_file(UML_GUIDE) or ""

    # Собираем student_id по папкам в tmp/repos/
    if not REPOS_DIR.exists():
        print(f"❌ Папка {REPOS_DIR} не найдена. Сначала запусти sync_students.py")
        return

    students = sorted(
        d.name for d in REPOS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    if not students:
        print("❌ В tmp/repos/ нет папок студентов.")
        return

    print(f"👥 Студентов: {len(students)}, практик: {len(TASKS)}")
    print(f"📤 Результаты → {RESULTS_DIR}\n")

    all_students = parse_students()
    students_to_check = [
        (name, sid) for name, sid, grade in all_students
        if not grade and sid in students
    ]

    for name, student_id in students_to_check:
        current_hash = get_repo_commit_hash(student_id)
        last_hash = get_last_checked_commit(student_id)

        if current_hash and current_hash == last_hash:
            print(f"── {student_id} — без изменений, пропускаем")
            continue

        print(f"── {student_id} ──")
        for task_name in TASKS:
            print(f"   {task_name}...", end=" ", flush=True)
            try:
                result = check_student_task(student_id, task_name, uml_guide)
            except Exception as e:
                result = f"⚠️ Ошибка при проверке: {e}"
                print(f"ERROR: {e}")
            else:
                if result is None:
                    print("—")  # не сдано, файл не пишем
                    continue
                elif result == "":
                    print("OK")
                else:
                    lines = result.count("\n") + 1
                    print(f"{lines} замечание(й)")

            write_result(student_id, task_name, result if result else "Замечаний нет.")

        if current_hash:
            save_last_checked_commit(student_id, current_hash)

    update_results_md()
    print("\n✅ Готово.")


if __name__ == "__main__":
    main()
