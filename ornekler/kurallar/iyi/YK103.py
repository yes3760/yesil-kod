import subprocess


def disk_kullanimi():
    return subprocess.run(["df", "-h"], capture_output=True).stdout
