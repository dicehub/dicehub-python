# Car mesh example

This example uses public dicehub SDK calls to run a snappyHexMesh car case. It resolves the
template, creates a private project and app, uploads and converts the bundled STL, applies mesh
settings, starts a run, and downloads its result. It leaves the project available for inspection.

## Requirements

Use a deployment with the `/templates/openfoam_snappyhexmesh` template and an available `local`
machine with four CPUs. The example starts conversion, setup, and mesh runs. Check the deployment's
machine access, quota, and cost before running it. Each wait is limited to 30 minutes. A timeout
ends the script; it does not stop the remote run.

The key needs permission to create a personal project and app, view templates and configuration
metadata, view and edit configuration content, start runs, view run status, and download results.
For cleanup, use `DELETE_PROJECT` on the created project. See the
[controlled cube guide](../../docs/guides/controlled-cube-workflow.md) for the full permission model.

## Run

Install the SDK first, then install the example's extra dependencies from the repository root:

```bash
python -m pip install .
python -m pip install -r examples/car_mesh/requirements.txt
read -rsp "dicehub API key: " DICEHUB_API_KEY && export DICEHUB_API_KEY
printf '\n'
python -m examples.car_mesh.workflow
```

The example and its bundled STL are in the source repository and are not included in the wheel.
The SDK connects to `https://dicehub.com` by default.

The script prints the created project ID immediately. Keep that ID even if a later step fails.
It uploads `assets/car_01_fixed_ground.stl.tar.gz` as a stream without extracting files to disk.
The camera step edits `sceneSettings.yaml` with `ruamel.yaml` round-trip mode.

Change the geometry, mesh settings, and run settings in the example for a different case.
The example is specific to this template; it is not a general OpenFOAM case runner.

## Results

Results are written below a new `results/car-mesh-*` directory whose name is generated locally.
Set `DICEHUB_RESULTS_DIR` to use another local root. A complete ZIP is named `run-results.zip`.
An interrupted download retains `run-results.zip.partial` and is not reported as complete. Review
or discard that partial file before retrying. Existing result files are not overwritten.

After the run finishes, open the printed app URL. Open the Run step and select **Show result**.
For mesh inspection, select `internalMesh`, add a Clip filter, select **Y Normal**, and apply it.
Set the representation to **Surface with edges**, show `PRO2STL_version_1.0`, and fit the view.
Interactive VTK data stays in the dicehub result viewer; it is not part of the ZIP snapshot.

To also download mesh points with the Results-panel S3 credentials:

```bash
export DICEHUB_DOWNLOAD_RESULTS_WITH_S3=1
```

This optional step requires broad `VIEW_APP` access. It downloads
`case/constant/polyMesh/points` into `from-s3/points` below the same new result directory.
Credentials are passed directly to boto3 and are not printed. The dicehub S3 endpoint is read-only.

## Cleanup

After inspection, delete only the project ID printed by this invocation. This removes the project,
app, configuration, runs, and stored data. In an interactive Bash session:

```bash
read -r -p "Created project ID: " DICEHUB_PROJECT_ID
dicehub project delete "$DICEHUB_PROJECT_ID" --output json
```

Review the exact ID at the confirmation prompt. Automation can use `--yes` only after its operator
has approved that exact target. After a timeout, check the run state and stop any active run before
cleanup. If project creation returned an uncertain outcome without an ID, inspect dicehub before
creating another project; the SDK does not retry mutations automatically.

Local result files are retained after remote cleanup. Temporary credentials must be revoked after use.
