import os
from pathlib import Path
from typing import Optional, Union, Dict, Any


_tracking_type = None
_experiment_name = None


def _mlflow_fallback_uri() -> str:
    configured = os.getenv("EXDBN_MLFLOW_FALLBACK_URI")
    if configured:
        return configured
    fallback_dir = Path(__file__).resolve().parent / "mlruns"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return fallback_dir.resolve().as_uri()

class ExperimentRunNeptune:
    def __init__(self, description):
        import neptune
        self.tracking_object = neptune.init_run(tags=[description], monitoring_namespace="monitoring")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.tracking_object.__exit__(exc_type, exc_val, exc_tb)

    def log_metric(self, key, value):
        self.tracking_object[f'metrics/{key}'] = value


    def log_param(self, key, value):
        self.tracking_object[f'params/{key}'] = value

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None):
        self.tracking_object[f'artifacts/{artifact_path}'].upload(local_path)

    def log_text(self, text: str, artifact_file: str):
        from neptune.types import File
        self.tracking_object[f'texts/{artifact_file}'].upload(File.from_content(text))

    def log_table(self, data: Union[Dict[str, Any], "pandas.DataFrame"], artifact_file: str,):
        if isinstance(data, dict):
            import pandas as pd
            data = pd.DataFrame.from_dict(data)
        from neptune.types import File
        self.tracking_object[f'tables/{artifact_file}'].upload(File.as_html(data))


class ExperimentRunMLFlow:
    import mlflow
    def __init__(self):
        self.tracking_object = self.mlflow.start_run()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.tracking_object.__exit__(exc_type, exc_val, exc_tb)

    def log_metric(self, key, value):
        return self.mlflow.log_metric(key, value)

    def log_param(self, key, value):
        return self.mlflow.log_param(key, value)

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None):
        return self.mlflow.log_artifact(local_path, artifact_path)

    def log_text(self, text: str, artifact_file: str):
        return self.mlflow.log_text(text, artifact_file)

    def log_table(self, data: Union[Dict[str, Any], "pandas.DataFrame"], artifact_file: str,):
        return self.mlflow.log_table(data, artifact_file)


def set_tracking(tracking_type: str, experiment_name: str | None = None):
    if tracking_type == 'mlflow':
        import mlflow
        requested_uri = os.getenv("MLFLOW_TRACKING_URI")
        if requested_uri:
            mlflow.set_tracking_uri(requested_uri)
        else:
            mlflow.set_tracking_uri(_mlflow_fallback_uri())
        try:
            mlflow.set_experiment(experiment_name)
        except Exception as exc:
            fallback_uri = _mlflow_fallback_uri()
            print(
                f"[WARN] mlflow backend initialization failed ({exc!r}); "
                f"falling back to file store at {fallback_uri}"
            )
            mlflow.set_tracking_uri(fallback_uri)
            mlflow.set_experiment(experiment_name)
    elif tracking_type == 'neptune':
        import neptune
    else:
        assert False, 'Invalid tracking type'
    global _tracking_type
    global _experiment_name
    _tracking_type = tracking_type
    _experiment_name = experiment_name


def start_run():
    global _tracking_type
    if _tracking_type == 'mlflow':
        return ExperimentRunMLFlow()
    elif _tracking_type == 'neptune':
        global _experiment_name
        return ExperimentRunNeptune(_experiment_name)
    else:
        assert False


# def end_run():
#     pass
