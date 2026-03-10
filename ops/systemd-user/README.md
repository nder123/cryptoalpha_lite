# systemd --user units

Эти файлы — эталонные unit-файлы для развёртывания CryptoAlpha как user-сервисов.

## Установка

```bash
mkdir -p ~/.config/systemd/user
cp -v ops/systemd-user/cryptoalpha-*.service ops/systemd-user/cryptoalpha-*.timer ~/.config/systemd/user/

systemctl --user daemon-reload

systemctl --user enable --now cryptoalpha-backend.service
systemctl --user enable --now cryptoalpha-snapshots.service
systemctl --user enable --now cryptoalpha-recommender.service
systemctl --user enable --now cryptoalpha-duty-check.timer
systemctl --user enable --now cryptoalpha-recommender-events.timer
systemctl --user enable --now cryptoalpha-recommender-alerts.timer

# oneshot: печатает компактную RL-операторскую сводку в journald
systemctl --user start cryptoalpha-rl-ops-summary.service
```

## Проверка

```bash
systemctl --user list-units 'cryptoalpha*' --all --no-pager
journalctl --user -u cryptoalpha-backend.service -n 100 --no-pager
journalctl --user -u cryptoalpha-recommender.service -n 100 --no-pager
journalctl --user -u cryptoalpha-recommender-events.service -n 50 --no-pager
journalctl --user -u cryptoalpha-recommender-alerts.service -n 50 --no-pager
journalctl --user -t cryptoalpha-rl-alert -p alert -n 50 --no-pager
journalctl --user -u cryptoalpha-rl-ops-summary.service -n 120 --no-pager --output=cat
journalctl --user -u cryptoalpha-duty-check.service -n 50 --no-pager
systemctl --user list-timers --all --no-pager | grep cryptoalpha-duty-check
systemctl --user list-timers --all --no-pager | grep cryptoalpha-recommender-events
systemctl --user list-timers --all --no-pager | grep cryptoalpha-recommender-alerts
```
