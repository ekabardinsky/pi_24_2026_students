#!/usr/bin/env python3
import os
import re
import shutil
import subprocess

# Пути относительно корня репозитория
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDENTS_FILE = os.path.join(BASE_DIR, 'students.md')
TMP_DIR = os.path.join(BASE_DIR, 'tmp')
REPOS_DIR = os.path.join(TMP_DIR, 'repos') # Новая изолированная папка под репозитории

def clean_and_create_dir():
    """Удаляет старую папку tmp со всем содержимым и создает чистую структуру заново."""
    if os.path.exists(TMP_DIR):
        print(f"🧹 Очистка временной папки: {TMP_DIR}")
        shutil.rmtree(TMP_DIR)
    # os.makedirs сhoreографично создаст и tmp/, и tmp/repos/ за один вызов
    os.makedirs(REPOS_DIR)

def parse_students():
    """Парсит md-таблицу и возвращает список кортежей (имя, student_id, ссылка_на_репо)."""
    students = []
    if not os.path.exists(STUDENTS_FILE):
        print(f"❌ Файл {STUDENTS_FILE} не найден!")
        return students

    # Регулярка под любое количество колонок: берём первые три
    row_pattern = re.compile(r'^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|')

    with open(STUDENTS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            match = row_pattern.match(line.strip())
            if match:
                name, student_id, repo = match.group(1), match.group(2), match.group(3)
                # Пропускаем заголовок таблицы и разделители
                if name.startswith('Студент') or name.startswith(':---'):
                    continue
                if repo.lower() != 'n/a':
                    students.append((name.strip(), student_id.strip(), repo.strip()))
    return students

def clone_repository(student_name, student_id, repo_url):
    """Клонирует репозиторий студента в папку tmp/repos/{student_id}."""
    # Теперь путь ведет внутрь папки repos/
    target_path = os.path.join(REPOS_DIR, student_id)

    print(f"🚀 Клонирование репо для: {student_name} ({student_id})")
    print(f"   Ссылка: {repo_url}")

    try:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, target_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print(f"   ✅ Успешно клонировано в tmp/repos/{student_id}\n")
        else:
            print(f"   ❌ Ошибка клонирования: {result.stderr.strip()}\n")

    except subprocess.TimeoutExpired:
        print(f"   ❌ Превышено время ожидания (таймаут 30с) для {repo_url}\n")
    except Exception as e:
        print(f"   ❌ Непредвиденная ошибка: {e}\n")

def main():
    print("=== Старт синхронизации репозиториев студентов ===")

    clean_and_create_dir()

    students = parse_students()
    print(f"📋 Найдено студентов с репозиториями: {len(students)}")

    if not students:
        print("ℹ️ Нет доступных репозиториев для скачивания (у всех стоит n/a).")
        return

    # Клонируем репозитории в изолированную подпапку tmp/repos/
    for name, student_id, repo in students:
        clone_repository(name, student_id, repo)

    print("=== Синхронизация успешно завершена! ===")

if __name__ == '__main__':
    main()