#!/bin/bash
# clean_up.sh - Удаляет все созданные мной файлы

echo "🧹 Очистка мусора..."

# Останавливаем все процессы
pkill -f auto_prompt.py
pkill -f auto_poke
pkill -f trigger
pkill -f cleanup
pkill -f direct

# Удаляем созданные файлы
cd /home/ander/CascadeProjects/cryptoalpha_lite

rm -f auto_prompt.py
rm -f auto_poke.py
rm -f auto_poke_fixed.py
rm -f trigger_cascade.py
rm -f cleanup_old_tasks.py
rm -f direct_command.py
rm -f start_everything.sh
rm -f start.sh
rm -f windsurf_codex_bridge.sh
rm -f force_read.py
rm -f .current_task
rm -f .WAKE_UP
rm -f .WAKE_UP_NOW
rm -f .cascade_trigger
rm -f .cascade_command

# Удаляем из docs (оставляем только оригинальные файлы)
cd docs
rm -f WAKE_UP.txt
rm -f last_report.md

echo "✅ Мусор удалён"
echo ""
echo "Оставлены только ваши оригинальные файлы:"
ls -la /home/ander/CascadeProjects/cryptoalpha_lite/docs/
