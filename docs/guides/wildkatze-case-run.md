---
title: Run a prepared Wildkatze case
description: Upload a Wildkatze case, select its version and machine, run it, and save the results.
read_when:
  - Running an existing Wildkatze case through the Python SDK
  - Testing the Wildkatze Case Run template
---

# Run a prepared Wildkatze case

The [example script](../../examples/wildkatze_case_run.py) uploads a prepared case to the
[Wildkatze Case Run template](https://dicehub.com/templates/wildkatze_case_run), selects a machine,
starts one run, and downloads the result ZIP. Each step has a small function with a docstring.
`main()` calls the steps in order.

You need a private dicehub project and a small Wildkatze case that already works. This tutorial
uses your local case; it does not include a solver mesh or a license file. For solver setup, see
the [Wildkatze documentation](https://fvus.github.io/wildkatze/).

## Prepare the case

Point the script at the directory containing `Allrun`, with this layout:

```text
my-case/
  Allrun
  mesh.bmsh
  mesh.info.bmsh
  o.txt
  run.txt
```

Use your mesh's actual name. Each `.bmsh` needs its matching `.info.bmsh` file. `o.txt` sets up the
simulation and writes its simulation tree. `run.txt` reloads that tree for result export. Include
any other files these scripts need.

`Allrun` is a shell script executed by the runner. For a prepared setup that writes `output.stree`,
a short run can use:

```bash
#!/bin/bash
set -euo pipefail
whac -lc "pf o.txt" \
     -lc "iterate 20" \
     -lc "save-restart-bin Restb" \
     -lc "export-ensight results"
```

Twenty iterations are useful for a small execution test; they do not establish convergence.
The corresponding `run.txt` loads the mesh and simulation tree:

```text
setdir ./
setmesh mesh
setsim output
readsimtree
```

The template uses `run.txt` and `Restb` to export results after the run. Keep these names when you
prepare the case. The upload preserves paths inside your case directory, so `Allrun` lands at
`uploads/Allrun`, not inside another case folder.

The example accepts up to 256 files, 64 MiB per file, and 128 MiB in total. Use an unpacked case
directory containing only the required inputs. Leave old result exports, restart files, and logs out
of a fresh-run upload. Symbolic links, special files, and hidden files are rejected before the
script contacts dicehub.

If a local launcher uses `whac4.sh`, change it to `whac` in the copy you upload; the dicehub runner
provides `whac`. Use the result name `results` in `export-ensight` to match the template's final
export. Keep iteration commands in either `o.txt` or `Allrun`, so they execute only once.

## Prepare the API key

Use a managed API key scoped to your private project. It needs:

- `VIEW_PROJECT_INFO` and `CREATE_APP`;
- `VIEW_CONFIG_INFO`, `VIEW_CONFIG_CONTENT`, and `EDIT_CONFIG_CONTENT`;
- `VIEW_RUN_INFO`, `START_RUN`, and `DOWNLOAD_RUN_RESULT`; and
- `DELETE_APP` for cleanup.

Set the key in `DICEHUB_API_KEY`. The script uses your project URL from the browser and resolves its
ID for you. The template must be publicly visible.

## Select compute and run

Install the SDK and the example's YAML reader, then list the current machine prices:

```bash
python -m pip install dicehub-python
python -m pip install -r requirements/examples.txt
dicehub run machine-types
```

Choose a Wildkatze CPU machine from the catalog. These machines have IDs beginning with `wk1_`;
GPU machines and remote desktop machines are excluded from this tutorial. `local` is also accepted
when a local Wildkatze runner is already configured.

The example requests one node and one CPU process. Starting a hosted run can incur charges, and the
price of the whole selected machine applies even if it has more CPUs. The script prints the
compatible machines and the selected machine's net EUR price per machine-hour before creating the
app or starting compute.

From the repository root:

```bash
export DICEHUB_PROJECT_URL="https://dicehub.com/your-namespace/your-project"
export DICEHUB_WILDKATZE_CASE_PATH="/path/to/my-case"
export DICEHUB_MACHINE_TYPE_ID="your-wildkatze-cpu-machine-id"
export DICEHUB_RESULT_PATH="$PWD/wildkatze-results.zip"

python examples/wildkatze_case_run.py
```

The script reads the Wildkatze version from the new app's template configuration, checks it against
the template metadata, applies it through `client.configs.set_values()`, and reads it back. No image
tag is fixed in the example. If you set `DICEHUB_WILDKATZE_VERSION`, it must match that supplied
version. The SDK does not currently expose a catalog of other supported Wildkatze versions.

## Results and cleanup

The script waits for up to 30 minutes and downloads results only after the run reaches `FINISHED`.
The ZIP contains the runner's `case/` output, including the files produced by your `Allrun` script.
The separate browser visualization directory, `VTK/`, is excluded from this download.

The output directory must exist. The result ZIP and its `.partial` path must be unused. Downloads
are limited to 512 MiB. A failed download leaves its `.partial` file and preserves any existing
result file.

After a successful download, the script deletes only the app it created. Set `DICEHUB_KEEP_APP=1`
before running to keep that app and inspect its results in dicehub.

If a step fails, the app remains available for inspection. Its ID is printed when it is created;
the run ID is printed after a successful start response. A wait timeout does not stop the remote
run. Check the app in dicehub, stop any active run, and delete the app when you no longer need it.
Stopping through the SDK requires `STOP_RUN` in addition to the permissions above.

If a mutation reports `MUTATION_OUTCOME_UNKNOWN`, check the app before trying again. The script
sends each mutation once. It does not fetch runner logs or handle license credentials.
