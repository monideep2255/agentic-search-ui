"""`s3` and `s3-kgx-export` steps that start no run: the page's commands as
printed (up to the point they fail), the promised --json flag, help text, and
the KGX export without graph credentials. Writes runs/cli_no_cost.json."""
import sys
import tempfile
from pathlib import Path

import live_lib as L

venv_py = sys.executable
prefix_bin = L.PREFIX / "bin"
snips = L.page_snippets(L.SCRATCH / "int_tree/frontend/src/components/screens/InfoScreens.tsx", L.API)
(Path(__file__).parent / "page_snippets_as_copied.txt").write_text(
    "\n\n".join(f"== {k}\n{v}" for k, v in snips.items()) + "\n"
)

cred = Path(tempfile.mkdtemp(prefix="s3cred_", dir=L.SCRATCH / "int_secrets"))
env = L.s3_env(cred)
s3 = [str(prefix_bin / "s3")]
kgx = [str(prefix_bin / "s3-kgx-export")]
steps = {}
# CLI_EXAMPLE line 1, exactly as printed.
steps["page_line_1_s3_login"] = L.run_cmd(s3 + ["login"], env, stdin="")
# CLI_EXAMPLE line 2 exactly as printed, before any login: no stored credentials.
steps["page_line_2_s3_ask_without_login"] = L.run_cmd(s3 + ["ask", "diseases linked to BRCA1"], env)
# The page body says "JSON with --json".
steps["s3_ask_json_flag"] = L.run_cmd(s3 + ["ask", "--json", "diseases linked to BRCA1"], env)
steps["s3_no_args"] = L.run_cmd(s3, env)
steps["s3_help"] = L.run_cmd(s3 + ["--help"], env)
steps["s3_ask_help"] = L.run_cmd(s3 + ["ask", "--help"], env)
steps["s3_login_help"] = L.run_cmd(s3 + ["login", "--help"], env)
# KGX_EXAMPLE exactly as printed, with every GRAPH_* variable removed, which is
# what an outsider has. Output goes to a scratch directory.
out_dir = Path(tempfile.mkdtemp(prefix="kgx_", dir=L.SCRATCH / "int_secrets"))
kgx_env = dict(env)
steps["kgx_help"] = L.run_cmd(kgx + ["--help"], kgx_env)
steps["kgx_as_printed_no_graph_access"] = L.run_cmd(
    kgx + ["NCBIGene:672", "--hops", "1", "--output-dir", str(out_dir / "kgx-out")], kgx_env, timeout=90
)
L.save("cli_no_cost", steps)
for k, v in steps.items():
    print(f"== {k}: exit {v['exit']} ({v['wall_s']}s)")
    print("   stdout:", v["stdout"].strip()[:400].replace("\n", "\n           "))
    print("   stderr:", v["stderr"].strip()[:600].replace("\n", "\n           "))
