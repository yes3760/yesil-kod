#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ -d /sys/class/powercap/intel-rapl ] && ! cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj >/dev/null 2>&1; then
  echo "Gerçek enerji ölçümü için RAPL okuma izni gerekiyor (bir kez, şifre sorar):"
  sudo chmod -R a+r /sys/class/powercap/intel-rapl || echo "İzin verilmedi, tahmini modda devam ediliyor."
fi
if [ "$(uname)" = "Darwin" ] && [ -x /usr/bin/powermetrics ] && [ "${YK_POWERMETRICS:-1}" != "0" ] && ! sudo -n true 2>/dev/null; then
  echo "Mac'te donanım enerji ölçümü (powermetrics) için yönetici şifresi gerekir."
  read -r -p "Donanım ölçümü açılsın mı? [E/h] " cevap
  case "$cevap" in
    [hHnN]*) echo "Tahmini modda devam ediliyor." ;;
    *) sudo -v -p "Mac şifresi: " || echo "İzin verilmedi, tahmini modda devam ediliyor." ;;
  esac
fi
exec python3 -m greencode
