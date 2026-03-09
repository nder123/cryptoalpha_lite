---
description: CI гейты качества и безопасности
---

# Цель
Не пускать в main/master код без базовых проверок качества и безопасности.

# Что проверяет CI (GitHub Actions)
- Ruff (линт)
- Black (формат)
- Isort (импорты)
- Mypy (типизация, мягкий режим)
- Bandit (базовые security checks)
- Pytest (unit) + coverage в консоль

# Правило
- PR нельзя мержить, если CI красный.

# Быстрая локальная репликация
- `cd backend`
- `poetry run ruff check .`
- `poetry run black --check .`
- `poetry run isort --check-only .`
- `poetry run mypy app scripts`
- `poetry run bandit -q -r app scripts`
- `poetry run pytest -q --maxfail=1 --cov=app --cov-report=term-missing`
