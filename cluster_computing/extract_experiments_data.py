import sys
import mlflow

def export_mlflow_to_csv(experiment_name: str, filename: str):
    runs = mlflow.search_runs(experiment_names=[experiment_name])
    runs.to_csv(filename, index=False)

if __name__ == "__main__":
    export_mlflow_to_csv(sys.argv[1], sys.argv[2])
