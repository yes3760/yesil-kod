import subprocess


def disk_kullanimi():
    return subprocess.run("df -h", shell=True, capture_output=True).stdout
