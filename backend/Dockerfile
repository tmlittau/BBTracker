FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# uv for fast, reproducible installs into the system environment.
# --link-mode=copy copies wheels out of uv's cache instead of reflinking/cloning
# them: the default clone uses the FICLONE/copy_file_range ioctl, which on
# ZFS-backed Docker storage (TrueNAS SCALE) intermittently fails with EAGAIN
# ("Resource temporarily unavailable", os error 11) at a random package.
RUN pip install --no-cache-dir uv

COPY requirements.txt ./
RUN uv pip install --system --link-mode=copy -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
