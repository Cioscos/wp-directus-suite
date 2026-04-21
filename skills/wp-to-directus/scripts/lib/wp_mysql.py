"""WordPress MySQL access helpers (subprocess-based)."""

import json
import os
import subprocess
from typing import Dict, List, Optional, Tuple


class MySQLClient:
    def __init__(self, host: str, port: int, user: str,
                 password: str, database: str,
                 docker_service: Optional[str] = None):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.database = database
        self.docker_service = docker_service

    def _cmd(self) -> List[str]:
        """Return argv for the mysql invocation.

        The password is NEVER included here — it is passed via the
        ``MYSQL_PWD`` environment variable (see :meth:`_cmd_and_env`) to
        avoid leaking it through ``/proc/<pid>/cmdline``, ``ps`` output,
        or shell audit logs.
        """
        if self.docker_service:
            return [
                "docker", "compose", "exec", "-T",
                "-e", f"MYSQL_PWD={self.password}",
                self.docker_service,
                "mysql",
                f"-u{self.user}", self.database,
                "--skip-column-names", "--batch", "--raw",
            ]
        return [
            "mysql",
            "-h", self.host, "-P", str(self.port),
            f"-u{self.user}", self.database,
            "--skip-column-names", "--batch", "--raw",
        ]

    def _cmd_and_env(self) -> Tuple[List[str], Dict[str, str]]:
        """Return (argv, env) with MYSQL_PWD injected into env.

        For direct mode the env is passed to the local ``mysql`` client,
        which honours ``MYSQL_PWD``. For docker mode, the env passed to
        ``subprocess.run`` is irrelevant for the inner ``mysql`` (it runs
        inside the container); instead the argv includes ``-e MYSQL_PWD=...``
        so ``docker compose exec`` forwards the variable into the container.
        """
        env = {**os.environ, "MYSQL_PWD": self.password}
        return self._cmd(), env

    def _run(self, sql: str, timeout: int = 30) -> bytes:
        cmd, env = self._cmd_and_env()
        r = subprocess.run(
            cmd,
            input=sql.encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env,
            timeout=timeout,
        )
        if r.returncode != 0:
            raise RuntimeError(
                f"mysql exit {r.returncode}: {r.stderr.decode('utf-8', 'replace')[:300]}"
            )
        return r.stdout

    def query(self, sql: str) -> List[List[str]]:
        raw = self._run(sql)
        try:
            out = raw.decode("utf-8")
        except UnicodeDecodeError:
            out = raw.decode("latin-1")
        return [line.split("\t") for line in out.strip().split("\n") if line]

    def query_json(self, sql: str) -> dict:
        raw = self._run(sql)
        try:
            out = raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            out = raw.decode("latin-1").strip()
        if not out:
            return {}
        try:
            return json.loads(out)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"query_json: invalid JSON: {out[:200]}"
            ) from e

    def ping(self) -> bool:
        try:
            self.query("SELECT 1;")
            return True
        except Exception:
            return False
