import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
const result = spawnSync(python, ["-B", "-m", "unittest", "discover", "-s", "tests", "-p", "*_test.py", "-v"], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1",
    ...(process.argv.includes("--require-r") ? { OMP_REQUIRE_R: "1" } : {}),
  },
});
if (result.error) {
  process.stderr.write(`无法运行综述测试：${result.error.message}。请安装 Python，或用 PYTHON 指定解释器。\n`);
}
process.exitCode = result.status ?? 1;
