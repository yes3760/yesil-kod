#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ -d /sys/class/powercap/intel-rapl ] && ! cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj >/dev/null 2>&1; then
  echo "Gerçek enerji ölçümü için RAPL okuma izni gerekiyor (bir kez, şifre sorar):"
  sudo chmod -R a+r /sys/class/powercap/intel-rapl || echo "İzin verilmedi, tahmini modda devam ediliyor."
fi
exec python3 -m greencode
