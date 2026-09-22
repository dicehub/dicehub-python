---
title: Run an OpenFOAM 14 case
description: Upload a small OpenFOAM case, select compute, run it, and download its results.
read_when:
  - Running an existing OpenFOAM case through the Python SDK
  - Testing the OpenFOAM Case Run template
---

# Run an OpenFOAM 14 case

The [executable example](../../examples/openfoam_case_run.py) runs a small lid-driven cavity with
the OpenFOAM Case Run template. It uploads the case, selects OpenFOAM Foundation 14, shows the
available machines and their net hourly prices, starts one run, waits for it, and downloads the
result ZIP.

Starting the run can incur charges. The example lists the available machines, then prints the
selected machine and its price before it starts the run.

## Prepare the API key

Use a project-scoped managed API key for the private project in `DICEHUB_PROJECT_URL`. The complete
example needs these permissions:

- `VIEW_PROJECT_INFO` to resolve the browser URL;
- `CREATE_APP`;
- `VIEW_CONFIG_INFO` and `EDIT_CONFIG_CONTENT`;
- `VIEW_RUN_INFO`, `START_RUN`, and `DOWNLOAD_RUN_RESULT`; and
- `DELETE_APP` to remove the example app after a successful run.

The Case Run template at `/templates/case_run` must be publicly visible. Managed API keys cannot
receive the `VIEW_APP_TEMPLATE` permission. The example checks the new app's visibility before it
uploads any case files and removes the app if the selected project is not private.

## Select a machine

List the available machine types first:

```bash
python examples/list_machine_types.py
```

Each JSON record contains the machine type ID, CPU count, GPU count, RAM, description, and net EUR
price per machine-hour. The case uses one node and one CPU process. The machine price still applies
when the selected machine provides more CPUs.

## Run the example

From the repository root, set the inputs and run the script:

```bash
export DICEHUB_PROJECT_URL="https://dicehub.com/your-namespace/your-project"
export DICEHUB_OPENFOAM_CASE_PATH="examples/openfoam_case_run_case"
export DICEHUB_MACHINE_TYPE_ID="your-machine-type-id"
export DICEHUB_RESULT_PATH="$PWD/openfoam-case-results.zip"

python examples/openfoam_case_run.py
```

The script reads the API key from `DICEHUB_API_KEY`.

The result directory must exist. The result ZIP and its `.partial` path must not exist. A failed
download leaves the `.partial` file and never replaces the requested destination.

The example defines one small documented function for each operation. Its `main()` function calls
them in this order:

1. resolve the private project from its browser URL;
2. resolve `/templates/case_run` and verify its slug;
3. create one uniquely named private app in the specified project and resolve its default config;
4. validate and upload each case file below the config's `uploads/` path;
5. select OpenFOAM Foundation 14;
6. list the machine catalog, find the exact requested ID, and set the single-process flow;
7. start one run with notifications disabled and wait with a finite timeout;
8. download results only after the run reaches `FINISHED`; and
9. delete the created app after the result download succeeds.

The script prints the app ID as soon as the app is created. If a later operation fails, the script
leaves that app in place so you can inspect it and delete it when the run is no longer active. The
SDK does not retry mutations automatically.

## Example case and license

The bundled [case](../../examples/openfoam_case_run_case) is an original input fixture released
under this repository's MIT license. It uses a 20 by 20 by 1 `blockMesh` grid, a moving lid, a
laminar Newtonian model, and the OpenFOAM 14 `incompressibleFluid` solver. Its `Allrun` script calls
only `blockMesh` and `foamRun`.

The fixture implements the standard lid-driven cavity problem. The official
[OpenFOAM 14 cavity tutorial](https://github.com/OpenFOAM/OpenFOAM-14/tree/master/tutorials/incompressibleFluid/cavity)
was used as a compatibility reference, but its files were not copied. OpenFOAM itself is available
under the [GNU General Public License](https://github.com/OpenFOAM/OpenFOAM-14/blob/master/COPYING).
