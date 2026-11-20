# Offline check image. Standard library only: nothing is downloaded at run time.
#   docker build -t auditgym .
#   docker run --rm --network none --cpus 2 --memory 4g auditgym
#
# Users inside the image:
#   root     the host process (environment, grader, seeds). Safe here: the container has no network
#            (--network none), the image runs one program, and the only code that runs as root is the
#            repository itself. The policy runs as root only in the fallback below.
#   agent    uid 10002, the policy child process. It owns only its temporary working directory.
#            It cannot read /proc/<host pid>/environ, root-owned 0600 files, or anything under /app
#            (mode 0750, group auditor), and cannot write to the package.
#   auditor  uid 10001, optional: `docker run --user 10001 ...` runs everything as one user. The code
#            (also under --cap-drop ALL, where root cannot switch user) falls back to starting the policy as that same user and prints one warning line.
# /app is owned by root (not writable by others); only /app/runs belongs to uid 10001 so reports can
# be written by either root or 10001 (root is also in group auditor, so --cap-drop ALL still works).
# /app/runs is 0770: the agent user (other) cannot enter it.
# Mount volumes only for output (-v DIR:/app/runs).
#
# Strict isolation is opt-in and is NOT set in this image: a runner that drops capabilities or sets --user
# must still pass the check, with the warning above. To refuse the fallback instead, add
#   -e AUDITGYM_REQUIRE_AGENT_USER=1
# check, run, demo, viewer and budget then exit 2 with one "error:" line before the first episode and before any
# report is written, when the policy could not start as the agent user (for example with --cap-drop ALL).
FROM python:3.11.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PYTHONIOENCODING=utf-8 \
    AUDITGYM_AGENT_USER=agent

RUN useradd --create-home --uid 10001 auditor \
 && useradd --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin --uid 10002 agent
WORKDIR /app
COPY . /app
RUN mkdir -p /app/runs \
 && chmod -R go-w /app \
 && chown -R auditor:auditor /app/runs \
 && chmod 0750 /app \
 && chown root:auditor /app \
 && chmod -R g+w /app/runs \
 && chmod 0770 /app/runs \
 && usermod -aG auditor root

CMD ["python", "-m", "auditgym", "check"]
