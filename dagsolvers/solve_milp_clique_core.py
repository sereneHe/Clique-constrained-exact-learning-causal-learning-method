import itertools
import json
import os
import time
import gurobipy as gp
import networkx as nx
import numpy as np
from gurobipy import GRB
from gurobipy import Model
from notears import utils
from omegaconf import DictConfig, OmegaConf

from dagsolvers.dagsolver_utils import find_minimal_dag_threshold
from dagsolvers.metrics_utils import (
    apply_threshold,
    count_accuracy as count_project_accuracy,
    find_optimal_threshold_for_shd,
)
from dagsolvers.optimization_diagnostics import create_diagnostics, diagnostics_enabled
from typing import Tuple, Dict


class CliqueMethod:
    """Strategy interface used by the shared MILP model.

    Concrete PPT methods live in ``solve_delayed_separation.py`` through
    ``solve_time_limit_optimization.py``.  This core owns no A--G policy.
    """

    family_name = "clique_method"

    def __init__(self, cfg):
        self.cfg = cfg
        self.variant = str(getattr(cfg, "method_variant", "BASE")).upper()

    @property
    def method_name(self):
        return f"{self.family_name}_{self.variant.lower()}"

    def prepare_big_m(self, X, Y, global_bound):
        bounds = {(i, j): float(global_bound)
                  for i in range(X.shape[1]) for j in range(X.shape[1])
                  if i != j}
        return float(global_bound), "scalar", bounds, {
            "mode": "scalar", "fallback_count": 0,
        }

    def requires_precrush(self):
        return False

    def initialize_model(self, model):
        pass

    def integer_clique_candidates(self, model, selected_edges, edge_values):
        return None

    def on_mip(self, model):
        pass

    def on_mipnode(self, model):
        pass

    def on_mipsol(self, model, selected_edges, edge_values, weight_values,
                  lag_edge_values, lag_weight_values, objective):
        cycle_added = (_add_cycle_cuts(model, selected_edges)
                       if model._enable_cycle_constraints else False)
        run_clique = not model._delayed_second_separation or not cycle_added
        clique_added = (_add_clique_cuts(model, selected_edges, edge_values)
                        if run_clique and model._enable_clique_constraints
                        else False)
        return cycle_added, clique_added

    def on_rejected(self, model, selected_edges, edge_values, weight_values,
                    lag_edge_values, lag_weight_values, objective):
        pass

    def on_accepted(self, model, selected_edges, objective):
        pass

    def finalize(self, model):
        pass

    def summary_fields(self, model):
        return {}


def _callback_log(model, event, **fields):
    """Emit one machine-readable line for Clique callback timing analysis."""
    if not getattr(model, "_print_callback_events", False):
        return
    try:
        runtime = float(model.cbGet(GRB.Callback.RUNTIME))
    except gp.GurobiError:
        runtime = float("nan")
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    suffix = f" {details}" if details else ""
    print(f"[CALLBACK] event={event} runtime={runtime:.6f}s{suffix}", flush=True)


def _print_retained_solutions(model):
    """Print every solution retained in Gurobi's solution pool as JSON."""
    if not getattr(model, "_print_retained_solutions", False):
        return
    solution_count = int(model.SolCount)
    for solution_id in range(solution_count):
        model.Params.SolutionNumber = solution_id
        edges = []
        for i, j in model._edges_vars.keys():
            if float(model._edges_vars[i, j].Xn) > 0.5:
                edges.append({
                    "from": int(i),
                    "to": int(j),
                    "weight": float(model._edges_weights[i, j].Xn),
                })
        record = {
            "event": "retained_feasible_solution",
            "solution_id": solution_id,
            "objective": float(model.PoolObjVal),
            "directed_edge_count": len(edges),
            "edges": edges,
        }
        print(f"[SOLUTION] {json.dumps(record, separators=(',', ':'))}", flush=True)



def _maximal_cliques(edges, d, max_clique_size, time_budget=0.0):
    graph = nx.Graph()
    graph.add_nodes_from(range(d))
    graph.add_edges_from((min(i, j), max(i, j)) for i, j in edges if i != j)
    started = time.perf_counter()
    violated = []
    for clique in nx.find_cliques(graph):
        if len(clique) > max_clique_size:
            violated.append(tuple(sorted(clique)))
        if time_budget > 0 and time.perf_counter() - started >= time_budget:
            break
    return violated


def find_violated_cliques(edges, d, max_clique_size, mode):
    """Compatibility helper retained for the copied solver interface."""
    violated = _maximal_cliques(edges, d, max_clique_size)
    if not violated:
        return []
    if mode == "all_cliques":
        return violated
    if mode == "largest_clique":
        return [max(violated, key=len)]
    if mode == "first_clique":
        return [violated[0]]
    if mode == "top_k_cliques":
        return sorted(violated, key=len, reverse=True)
    assert False, f"Invalid mode{mode}"


def _score_clique_candidate(clique, edge_values):
    """Build the common candidate record for an integer clique inequality."""
    nodes = tuple(sorted(int(node) for node in clique))
    pairs = tuple(itertools.combinations(nodes, 2))
    lhs = sum(float(edge_values.get((i, j), 0.0))
              + float(edge_values.get((j, i), 0.0))
              for i, j in pairs)
    rhs = len(pairs) - 1
    return {
        "nodes": nodes,
        "pairs": pairs,
        "lhs": lhs,
        "rhs": rhs,
        "violation": lhs - rhs,
    }


def _add_clique_cuts(model, selected_edges, edge_values):
    constr_added = False
    clique_mode = getattr(model, "_clique_callback_mode", "first_clique")
    max_clique_size = getattr(model, "_max_clique_size", 3)
    print_clique_cuts = getattr(model, "_print_clique_cuts", False)
    _callback_log(model, "clique_detection_start",
                  mipsol_id=model._mipsol_count,
                  selected_edges=len(selected_edges),
                  max_clique_size=max_clique_size)
    detection_started = time.perf_counter()
    candidates = model._method.integer_clique_candidates(
        model, selected_edges, edge_values)
    if candidates is None:
        cliques = find_violated_cliques(selected_edges, model._d, max_clique_size, clique_mode)
        if clique_mode == "top_k_cliques":
            cliques = cliques[:model._clique_top_k]
        candidates = [_score_clique_candidate(clique, edge_values) for clique in cliques]
    if model._max_clique_cuts_per_callback > 0:
        candidates = candidates[:model._max_clique_cuts_per_callback]
    detection_time = time.perf_counter() - detection_started
    model._clique_detection_seconds += detection_time
    _callback_log(model, "clique_constraints_filtered",
                  mipsol_id=model._mipsol_count,
                  violated=len(candidates),
                  detection_seconds=f"{detection_time:.9f}")
    if candidates and print_clique_cuts:
        rt = model.cbGet(GRB.Callback.RUNTIME)
        print(
            f"[CLIQUE] runtime={rt:.2f}s mode={clique_mode} "
            f"max_k={max_clique_size} violated={len(candidates)}"
        )
    cut_keys = []
    submission_started = time.perf_counter()
    for candidate in candidates:
        clique = candidate["nodes"]
        key = tuple(clique)
        if model._deduplicate_clique_cuts and key in model._added_clique_cut_keys:
            continue
        cut_keys.append(key)
        clique_pairs = candidate["pairs"]
        model._lazy_count += 1
        model._clique_lazy_count += 1
        model.cbLazy(
            gp.quicksum(model._edges_vars[i, j] + model._edges_vars[j, i] for i, j in clique_pairs)
            <= candidate["rhs"]
        )
        model._added_clique_cut_keys.add(key)
        if print_clique_cuts:
            print(
                f"[CLIQUE-CUT] nodes={clique} pairs={len(clique_pairs)} "
                f"rhs={candidate['rhs']} violation={candidate['violation']:.6g}"
            )
        constr_added = True
    submission_time = time.perf_counter() - submission_started
    model._clique_submission_seconds += submission_time
    if candidates:
        _callback_log(model, "clique_constraints_added",
                      mipsol_id=model._mipsol_count,
                      added=len(cut_keys),
                      submission_seconds=f"{submission_time:.9f}",
                      clique_lazy_total=model._clique_lazy_count)
    if model._optimization_diagnostics is not None:
        model._optimization_diagnostics.record_separation(
            "clique", detection_time, submission_time, cut_keys)
    return constr_added


def find_cycles(edges, mode):
    vertices = set(e[0] for e in edges)
    vertices.update(e[1] for e in edges)

    visited = set()
    on_stack = set()
    parent = {}
    stack = []
    shortest_cycle = None
    found_cycles = []
    number_of_cycles = 0

    for root in vertices:
        if root in visited:
            continue
        stack.append(root)
        while stack:
            v = stack[-1]
            if v not in visited:
                visited.add(v)
                on_stack.add(v)
            else:
                if v in on_stack:
                    on_stack.remove(v)
                # else:
                #     print('DEBUG')
                stack.pop()

            neighbors = [e[1] for e in edges if e[0] == v]
            for neighbor in neighbors:
                if neighbor not in visited:
                    stack.append(neighbor)
                    parent[neighbor] = v
                elif neighbor in on_stack:
                    number_of_cycles += 1
                    # Found a cycle
                    cycle = [neighbor, v] # Back edge
                    p = parent[v]
                    while p != neighbor:
                        cycle.append(p)
                        p=parent[p]
                    #print(cycle)
                    if mode == 'first_cycle':
                        return [cycle] # return the first found cycle
                    found_cycles.append(cycle)
                    if shortest_cycle is None or len(shortest_cycle) > len(cycle):
                        shortest_cycle = cycle

    #print(f'number of cycles: {number_of_cycles}')
    if mode == 'shortest_cycle':
        if shortest_cycle is not None:
            return [shortest_cycle]
        else:
            return []
    elif mode in {'all_cycles', 'top_k_cycles'}:
        return found_cycles
    elif mode == 'first_cycle':
        return []
    else:
        assert False, f'Invalid mode{mode}'


def extract_adj_matrix(edges_vals, weights_vals, d):
    W = np.zeros((d,d))
    for v1 in range(d):
        for v2 in range(d):
            if v1 != v2:
                if edges_vals[v1, v2] > 0.5:
                    W[v1, v2] = weights_vals[(v1, v2)]
    return W

def extract_adj_matrix_no_vars(weights_vals, d):
    A = np.zeros((d,d))
    for v1 in range(d):
        for v2 in range(d):
            A[v1, v2] = weights_vals[(v1, v2)]
    return A

def _cycle_edges_and_key(cycle):
    edges_of_cycle = [(cycle[i + 1], cycle[i])
                      for i in range(len(cycle) - 1)]
    edges_of_cycle.append((cycle[0], cycle[-1]))
    # Sorting directed edges canonicalizes cyclic rotations while preserving
    # direction, so a reversed directed cycle remains a different key.
    return edges_of_cycle, tuple(sorted(edges_of_cycle))


def _add_cycle_cuts(model, selected_edges, cycles_override=None):
    constr_added = False
    _callback_log(model, "cycle_detection_start",
                  mipsol_id=model._mipsol_count,
                  selected_edges=len(selected_edges))
    detection_started = time.perf_counter()
    cycles = (find_cycles(selected_edges, model._callback_mode)
              if cycles_override is None else list(cycles_override))
    if cycles_override is None and model._callback_mode == "top_k_cycles":
        cycles = sorted(cycles, key=len)[:model._cycle_top_k]
    if model._max_cycle_cuts_per_callback > 0:
        cycles = cycles[:model._max_cycle_cuts_per_callback]
    detection_time = time.perf_counter() - detection_started
    model._cycle_detection_seconds += detection_time
    _callback_log(model, "cycle_constraints_filtered",
                  mipsol_id=model._mipsol_count,
                  violated=len(cycles),
                  detection_seconds=f"{detection_time:.9f}")
    cut_keys = []
    submission_started = time.perf_counter()
    for cycle in cycles:
        edges_of_cycle, key = _cycle_edges_and_key(cycle)
        if model._deduplicate_cycle_cuts and key in model._added_cycle_cut_keys:
            continue
        cut_keys.append(key)
        model._lazy_count += 1
        model._cycle_lazy_count += 1
        model.cbLazy(gp.quicksum(model._edges_vars[i, j] for i, j in edges_of_cycle)
                     <= len(edges_of_cycle)-1)
        model._added_cycle_cut_keys.add(key)
        constr_added = True
    submission_time = time.perf_counter() - submission_started
    model._cycle_submission_seconds += submission_time
    if cycles:
        _callback_log(model, "cycle_constraints_added",
                      mipsol_id=model._mipsol_count,
                      added=len(cycles),
                      submission_seconds=f"{submission_time:.9f}",
                      cycle_lazy_total=model._cycle_lazy_count)
    if model._optimization_diagnostics is not None:
        model._optimization_diagnostics.record_separation(
            "cycle", detection_time, submission_time, cut_keys)
    return constr_added


def method_callback(model, where):
    """Common callback lifecycle; A--G decisions are delegated to a method."""
    if where == GRB.Callback.MESSAGE:
        return
    if where == GRB.Callback.MIP:
        if model._optimization_diagnostics is not None:
            model._optimization_diagnostics.record_progress(model)
        model._method.on_mip(model)
        return
    if where == GRB.Callback.MIPNODE:
        model._mipnode_count += 1
        if (model._optimization_diagnostics is not None
                and model.cbGet(GRB.Callback.MIPNODE_STATUS) == GRB.OPTIMAL
                and model.cbGet(GRB.Callback.MIPNODE_NODCNT) < 0.5):
            edge_vals = model.cbGetNodeRel(model._edges_vars)
            weight_vals = model.cbGetNodeRel(model._edges_weights)
            model._optimization_diagnostics.record_root(
                model, edge_vals, weight_vals)
        model._method.on_mipnode(model)
        return
    if where != GRB.Callback.MIPSOL:
        return

    model._mipsol_count += 1
    edge_values = model.cbGetSolution(model._edges_vars)
    weight_values = model.cbGetSolution(model._edges_weights)
    lag_edge_values = [model.cbGetSolution(values)
                       for values in model._lag_edges_vars]
    lag_weight_values = [model.cbGetSolution(values)
                         for values in model._lag_edges_weights]
    objective = float(model.cbGet(GRB.Callback.MIPSOL_OBJ))
    _callback_log(model, "mipsol_candidate", mipsol_id=model._mipsol_count,
                  objective=f"{objective:.12g}")
    if model._optimization_diagnostics is not None:
        model._optimization_diagnostics.record_mipsol(model, edge_values)
    selected_edges = gp.tuplelist(
        (i, j) for i, j in model._edges_vars.keys()
        if edge_values[i, j] > 0.5)

    cycle_added, clique_added = model._method.on_mipsol(
        model, selected_edges, edge_values, weight_values,
        lag_edge_values, lag_weight_values, objective)
    rejected = bool(cycle_added or clique_added)
    if model._optimization_diagnostics is not None:
        model._optimization_diagnostics.record_mipsol_outcome(rejected)

    if rejected:
        model._method.on_rejected(
            model, selected_edges, edge_values, weight_values,
            lag_edge_values, lag_weight_values, objective)
        model._mipsol_rejected_count += 1
        runtime = float(model.cbGet(GRB.Callback.RUNTIME))
        if model._first_constraint_runtime is None:
            model._first_constraint_runtime = runtime
        model._last_constraint_runtime = runtime
        _callback_log(
            model, "mipsol_rejected", mipsol_id=model._mipsol_count,
            objective=f"{objective:.12g}", cycle_added=int(cycle_added),
            clique_added=int(clique_added),
            rejected_total=model._mipsol_rejected_count)
        _callback_log(model, "solver_resume_after_constraints",
                      mipsol_id=model._mipsol_count,
                      lazy_total=model._lazy_count)
        return

    model._mipsol_accepted_count += 1
    accepted_runtime = float(model.cbGet(GRB.Callback.RUNTIME))
    if model._first_valid_incumbent_time is None:
        model._first_valid_incumbent_time = accepted_runtime
    model._method.on_accepted(model, selected_edges, objective)
    if objective < model._best_accepted_objective - 1e-9:
        model._best_accepted_objective = objective
        W_candidate = extract_adj_matrix(edge_values, weight_values, model._d)
        W_eval = W_candidate.copy()
        W_eval[np.abs(W_eval) < model._w_threshold] = 0
        accuracy = (count_project_accuracy(
            np.asarray(model._B_ref).astype(int),
            (W_eval != 0).astype(int), [], [], test_dag=True)
            if model._B_ref is not None else {})
        model._best_accepted_snapshot = {
            "objective": objective,
            "edges": list(selected_edges),
            "weights": {str(key): float(weight_values[key])
                        for key in model._edges_weights.keys()},
            "nnz": int(np.count_nonzero(W_eval)),
            "shd": accuracy.get("shd"),
            "f1": accuracy.get("f1score"),
        }
        model._accepted_incumbent_trajectory.append({
            "runtime": accepted_runtime, "objective": objective,
            "nnz": int(np.count_nonzero(W_eval)),
            "shd": accuracy.get("shd"), "f1": accuracy.get("f1score"),
        })
    _callback_log(model, "mipsol_accepted", mipsol_id=model._mipsol_count,
                  objective=f"{objective:.12g}",
                  accepted_total=model._mipsol_accepted_count)

    rt = model.cbGet(GRB.Callback.RUNTIME)
    if model._B_ref is not None and rt - model._last_time_stats > 60:
        model._last_time_stats = rt
        W_sol = extract_adj_matrix(edge_values, weight_values, model._d)
        dag_t, W_sol = find_minimal_dag_threshold(W_sol)
        default_threshold = 0.3
        W_t = apply_threshold(W_sol, default_threshold)
        shd = utils.count_accuracy(model._B_ref, W_t != 0)['shd']
        best_t, best_shd = find_optimal_threshold_for_shd(
            model._B_ref, W_sol, [], [], np.zeros_like(model._B_ref),
            np.zeros_like(model._B_ref))
        print(f't{default_threshold}_SHD: {shd} BEST_SHD: {best_shd} '
              f'BEST_t: {best_t} OBJ: {objective} DAG_t: {dag_t}')
        model._stats.append(
            (round(rt), shd, best_shd, best_t, objective, dag_t))


def _write_method_summary(model, cfg):
    if getattr(model, "_summary_written", False):
        return
    model._summary_written = True
    output_dir = str(getattr(cfg, "diagnostics_output_dir", "."))
    os.makedirs(output_dir, exist_ok=True)
    runtime = float(model.Runtime)
    nodes = float(model.NodeCount)
    has_solution = int(model.SolCount) > 0
    callback_time = (model._cycle_detection_seconds
                     + model._cycle_submission_seconds
                     + model._clique_detection_seconds
                     + model._clique_submission_seconds
                     + float(getattr(model, "_fractional_separation_seconds", 0.0))
                     + float(getattr(model, "_delayed_classification_seconds", 0.0))
                     + float(getattr(model, "_repair_metrics", {}).get("time", 0.0)))
    summary = {
        "method": model._method_name,
        "method_variant": model._method_variant,
        "effective_variant_config": OmegaConf.to_container(cfg, resolve=True),
        "status": int(model.Status), "runtime": runtime,
        "objective": float(model.ObjVal) if has_solution else None,
        "best_bound": float(model.ObjBound),
        "gap": float(model.MIPGap) if has_solution else None,
        "node_count": nodes,
        "mipsol_total": model._mipsol_count,
        "mipsol_rejected": model._mipsol_rejected_count,
        "mipsol_accepted": model._mipsol_accepted_count,
        "mipnode_total": model._mipnode_count,
        "cycle_cuts": model._cycle_lazy_count,
        "clique_cuts": model._clique_lazy_count,
        "clique_user_cuts": model._clique_user_count,
        "unique_cycle_cuts": len(model._added_cycle_cut_keys),
        "unique_clique_lazy_cuts": len(model._added_clique_cut_keys),
        "callback_time": callback_time,
        "callback_time_over_total_runtime": callback_time / max(runtime, 1e-12),
        "nodes_per_second": nodes / max(runtime, 1e-12),
        "lp_iterations": float(model.IterCount),
        "lp_iterations_per_node": float(model.IterCount) / max(nodes, 1.0),
        "first_valid_incumbent_time": model._first_valid_incumbent_time,
        "accepted_incumbent_trajectory": model._accepted_incumbent_trajectory,
        "best_accepted_snapshot": model._best_accepted_snapshot,
        "big_m_mode": model._big_m_mode,
        "effective_weights_bound": model._global_big_m,
        "edge_bound_summary": model._edge_bound_summary,
        "method_details": model._method.summary_fields(model),
    }
    path = os.path.join(output_dir, f"{model._method_name}_summary.json")
    with open(path, "w") as handle:
        json.dump(summary, handle, indent=2)
    print("[METHOD-SUMMARY] " + json.dumps({
        "path": path, "method": model._method_name,
        "runtime": runtime, "gap": summary["gap"],
    }, separators=(",", ":")), flush=True)


def construct_matrix_vars(m: Model, d: int, matrix_name: str, constraints_mode, weights_bound, tabu_edges, diagonal=False) -> Tuple[Dict, Dict]:
    edges_vars = {}
    edges_weights = {}
    for v1 in range(d):
        for v2 in range(d):
            if diagonal or v1 != v2:
                if constraints_mode != 'no-vars':
                    edges_vars[v1,v2] = m.addVar(vtype=GRB.BINARY, name=f'{matrix_name}_{v1}->{v2}')
                edges_weights[v1,v2] = m.addVar(lb = float('-inf'),vtype=GRB.CONTINUOUS, name=f'{matrix_name}_weight{v1}->{v2}')

                if constraints_mode == 'no-weights':
                    m.addConstr(edges_weights[v1,v2] == edges_vars[v1,v2])
                elif constraints_mode == 'no-vars':
                    bound = (weights_bound.get((v1, v2), max(weights_bound.values()))
                             if isinstance(weights_bound, dict) else weights_bound)
                    m.addConstr(edges_weights[v1,v2] <= bound)
                    m.addConstr(-edges_weights[v1,v2] <= bound)
                else:
                    bound = (weights_bound.get((v1, v2), max(weights_bound.values()))
                             if isinstance(weights_bound, dict) else weights_bound)
                    m.addConstr(edges_weights[v1,v2] <= bound * edges_vars[v1,v2])
                    m.addConstr(-edges_weights[v1,v2] <= bound * edges_vars[v1,v2])
    if tabu_edges is not None:
        for (v1,v2) in tabu_edges:
            m.addConstr(edges_vars[v1,v2] == 0)
            m.addConstr(edges_weights[v1,v2] == 0)
    return edges_vars, edges_weights


def solve(X, cfg: DictConfig, w_threshold, Y=None, B_ref=None, tabu_edges=None,
          method=None):

    time_limit = cfg.time_limit
    lambda1 = cfg.lambda1
    lambda2 = cfg.lambda2
    loss_type = cfg.loss_type
    constraints_mode = cfg.constraints_mode
    mode = cfg.callback_mode
    robust = cfg.robust
    if method is None:
        raise ValueError("A concrete A--G CliqueMethod is required")
    method_variant = method.variant
    reg_type = cfg.reg_type
    a_reg_type = cfg.a_reg_type
    target_mip_gap = cfg.target_mip_gap

    n, d = X.shape
    if Y is None:
        Y = []
    p = len(Y) # The number of historical data slices
    weights_bound, big_m_mode, edge_specific_bounds, edge_bound_summary = \
        method.prepare_big_m(X, Y, float(cfg.weights_bound))
    W_link_bounds = (edge_specific_bounds
                     if big_m_mode == "edge_specific"
                     else weights_bound)
     # 'no-weights'
    # if loss_type == 'l2':
    #     X = X - np.mean(X, axis=0, keepdims=True)


    m = gp.Model()
    W_edges_vars, W_edges_weights = construct_matrix_vars(
        m, d, 'W', constraints_mode, W_link_bounds, tabu_edges)
    for v1 in range(d):
        for v2 in range(v1):
            m.addConstr(W_edges_vars[v2,v1] + W_edges_vars[v1,v2] <= 1)

    A_edges_vars = []
    A_edges_weights = []

    a_constraints_mode = '' if a_reg_type == 'l1' else 'no-vars'

    for t in range(p):
        A_t_edges_vars, A_t_edges_weights = construct_matrix_vars(m, d, f'A_{t}', a_constraints_mode, weights_bound, diagonal=True, tabu_edges=None)
        A_edges_vars.append(A_t_edges_vars)
        A_edges_weights.append(A_t_edges_weights)

    robust_vars = {}
    quad_diff = {}
    if robust:
        for i in range(n):
            robust_vars[i] = m.addVar(vtype=GRB.BINARY, name=f's{i}')
            for j in range(d):
                quad_diff[i, j] = m.addVar(lb = float('-inf'),vtype=GRB.CONTINUOUS, name=f'q{i}-{j}')
        r = round(0.9 * n)
        m.addConstr(gp.quicksum(robust_vars[i] for i in range(n)) >= r)
        for i in range(n):
            for j in range(d):
                m.addConstr((X[i,j] - gp.quicksum(X[i, k] * W_edges_weights[k, j] for k in range(d) if k != j) - gp.quicksum(Y[t][i, k] * A_edges_weights[t][k, j] for k in range(d) for t in range(p)))**2 == quad_diff[i,j])
        robust_objective = gp.quicksum(quad_diff[i,j] * robust_vars[i] for i in range(n) for j in range(d))
    #callback_constraints = {}
    #callback_constraints[1] = 0


    # regulazition
    if reg_type == 'l2':
        reg = gp.quicksum(w**2 for w in W_edges_weights.values())
        # reg2 = 0
        # for A_t_edges_weights in A_edges_weights:
        #     reg2 = reg2 + gp.quicksum(a**2 for a in A_t_edges_weights.values())
    elif reg_type == 'l1':
        reg = gp.quicksum(w for w in W_edges_vars.values())
        # reg2 = 0
        # l2 reg for As becouse we dont have decision variables for them.
        # for A_t_edges_weights in A_edges_weights:
        #     reg2 = reg2 + gp.quicksum(a**2 for a in A_t_edges_weights.values())
        # for A_t_edges_vars in A_edges_vars:
        #     reg = reg + gp.quicksum(a for a in A_t_edges_vars.values())
    else:
        assert False

    if a_reg_type == 'l2':
        reg2 = 0
        for A_t_edges_weights in A_edges_weights:
            reg2 = reg2 + gp.quicksum(a**2 for a in A_t_edges_weights.values())
    elif a_reg_type == 'l1':
        reg2 = 0
        for A_t_edges_vars in A_edges_vars:
            reg = reg + gp.quicksum(a for a in A_t_edges_vars.values())
    else:
        assert False


    # Cost function
    if loss_type == 'l2':
        if robust:
            m.setObjective(robust_objective + lambda1 * reg / d + lambda2 * reg2 / d, GRB.MINIMIZE)
        else:
            m.setObjective(gp.quicksum((X[i,j] - gp.quicksum(X[i, k] * W_edges_weights[k, j] for k in range(d) if k != j)
                                        - gp.quicksum(Y[t][i, k] * A_edges_weights[t][k, j] for k in range(d) for t in range(p))
                                        )**2 for i in range(n) for j in range(d))/n + lambda1 * reg / d + lambda2 * reg2 / d, GRB.MINIMIZE)
            print(m.getObjective().getValue())
    elif loss_type == 'l1':

        abs_vars = {}
        for i in range(n):
            for j in range(d):
                abs_vars[i,j] = m.addVar(vtype=GRB.CONTINUOUS, name=f'abs{i}-{j})')
                m.addConstr((X[i,j] - gp.quicksum(X[i, k] * W_edges_weights[k, j] for k in range(d) if k != j) - gp.quicksum(Y[t][i, k] * A_edges_weights[t][k, j] for k in range(d) for t in range(p))) <= abs_vars[i,j])
                m.addConstr(-(X[i,j] - gp.quicksum(X[i, k] * W_edges_weights[k, j] for k in range(d) if k != j) - gp.quicksum(Y[t][i, k] * A_edges_weights[t][k, j] for k in range(d) for t in range(p))) <= abs_vars[i,j])

        # abs_edges_weights={}
        # for v1 in range(d):
        #     for v2 in range(d):
        #         if v1 != v2:
        #             abs_edges_weights[v1,v2] = m.addVar(vtype=GRB.CONTINUOUS, name=f'abs_weight{v1}->{v2}')
        #             m.addConstr(W_edges_weights[v1,v2] <= abs_edges_weights[v1,v2])
        #             m.addConstr(-W_edges_weights[v1,v2] <= abs_edges_weights[v1,v2])


        m.setObjective(gp.quicksum(abs_vars[i,j] for i in range(n) for j in range(d))/n + lambda1 * reg / d + lambda2 * reg2 / d, GRB.MINIMIZE)

    m.Params.lazyConstraints = 1
    if method.requires_precrush():
        m.Params.PreCrush = 1
    m.Params.MIPGap = target_mip_gap
    m.params.TimeLimit = time_limit
    if hasattr(cfg, "gurobi_seed"):
        m.Params.Seed = int(cfg.gurobi_seed)
    if hasattr(cfg, "gurobi_threads"):
        m.Params.Threads = int(cfg.gurobi_threads)
    m._edges_vars = W_edges_vars
    m._edges_weights = W_edges_weights
    m._lag_edges_vars = A_edges_vars
    m._lag_edges_weights = A_edges_weights
    m._lazy_count = 0
    m._cycle_lazy_count = 0
    m._clique_lazy_count = 0
    m._clique_user_count = 0
    m._added_cycle_cut_keys = set()
    m._added_clique_cut_keys = set()
    m._mipsol_count = 0
    m._mipsol_rejected_count = 0
    m._mipsol_accepted_count = 0
    m._first_constraint_runtime = None
    m._last_constraint_runtime = None
    m._cycle_detection_seconds = 0.0
    m._cycle_submission_seconds = 0.0
    m._clique_detection_seconds = 0.0
    m._clique_submission_seconds = 0.0
    m._last_time_stats = 0
    m._B_ref = B_ref
    m._stats = []
    m._d = d
    m._X = np.asarray(X)
    m._Y = Y
    m._w_threshold = float(w_threshold)
    m._method = method
    m._method_variant = method_variant
    m._method_name = method.method_name
    m._global_big_m = float(weights_bound)
    m._big_m_mode = big_m_mode
    m._edge_specific_bounds = edge_specific_bounds
    m._edge_bound_summary = edge_bound_summary
    m._callback_mode = mode
    m._clique_callback_mode = getattr(cfg, "clique_callback_mode", "first_clique")
    m._max_clique_size = getattr(cfg, "max_clique_size", 3)
    m._enable_cycle_constraints = bool(getattr(cfg, "enable_cycle_constraints", True))
    m._enable_clique_constraints = bool(getattr(cfg, "enable_clique_constraints", True))
    m._separation_order = str(getattr(cfg, "separation_order", "cycle_first"))
    m._delayed_second_separation = bool(
        getattr(cfg, "delayed_second_separation", False))
    m._cycle_top_k = int(getattr(cfg, "cycle_top_k", 5))
    m._clique_top_k = int(getattr(cfg, "clique_top_k", 5))
    m._max_cycle_cuts_per_callback = int(
        getattr(cfg, "max_cycle_cuts_per_callback", 0))
    m._max_clique_cuts_per_callback = int(
        getattr(cfg, "max_clique_cuts_per_callback", 0))
    m._deduplicate_cycle_cuts = bool(getattr(cfg, "deduplicate_cycle_cuts", False))
    m._deduplicate_clique_cuts = bool(getattr(cfg, "deduplicate_clique_cuts", False))
    m._best_accepted_objective = float("inf")
    m._mipnode_count = 0
    m._best_accepted_snapshot = None
    m._first_valid_incumbent_time = None
    m._accepted_incumbent_trajectory = []
    method.initialize_model(m)
    diagnostics_on = diagnostics_enabled(cfg)
    # Preserve the original solver output when diagnostics are disabled:
    # print_clique_cuts predates the diagnostics collector and therefore
    # remains independently controlled by its original YAML field.
    m._print_clique_cuts = bool(getattr(cfg, "print_clique_cuts", False))
    # These two outputs were introduced by the diagnostics instrumentation,
    # so the master switch must be on before their optional sub-flags apply.
    m._print_callback_events = diagnostics_on and bool(
        getattr(cfg, "print_callback_events", True))
    m._print_retained_solutions = diagnostics_on and bool(
        getattr(cfg, "print_retained_solutions", True))
    m._optimization_diagnostics = create_diagnostics(
        cfg, m._method_name, d,
        int(m._max_clique_size), weights_bound)
    try:
        solve_wall_started = time.perf_counter()
        if m._print_callback_events:
            print("[SOLVER] event=gurobi_solve_start runtime=0.000000s", flush=True)
        m.optimize(method_callback)
        method.finalize(m)
        solve_wall_seconds = time.perf_counter() - solve_wall_started
        post_constraint_seconds = (
            float(m.Runtime) - m._last_constraint_runtime
            if m._last_constraint_runtime is not None else None
        )
        if m._print_callback_events:
            print(
                f"[SOLVER] event=gurobi_solve_end runtime={float(m.Runtime):.6f}s "
                f"wall_seconds={solve_wall_seconds:.6f} status={int(m.Status)}",
                flush=True,
            )
            print(
                "[CALLBACK-SUMMARY] "
                f"mipsol_total={m._mipsol_count} "
                f"mipsol_rejected={m._mipsol_rejected_count} "
                f"mipsol_accepted={m._mipsol_accepted_count} "
                f"cycle_constraints_added={m._cycle_lazy_count} "
                f"clique_constraints_added={m._clique_lazy_count} "
                f"cycle_filter_seconds={m._cycle_detection_seconds:.9f} "
                f"cycle_add_seconds={m._cycle_submission_seconds:.9f} "
                f"clique_filter_seconds={m._clique_detection_seconds:.9f} "
                f"clique_add_seconds={m._clique_submission_seconds:.9f} "
                f"first_constraint_runtime_seconds="
                f"{m._first_constraint_runtime if m._first_constraint_runtime is not None else 'NA'} "
                f"last_constraint_runtime_seconds="
                f"{m._last_constraint_runtime if m._last_constraint_runtime is not None else 'NA'} "
                f"solve_after_last_constraint_seconds="
                f"{post_constraint_seconds if post_constraint_seconds is not None else 'NA'}",
                flush=True,
            )
        _print_retained_solutions(m)

        sol_count = m.getAttr(GRB.attr.SolCount)
        if sol_count == 0:
            if m._optimization_diagnostics is not None:
                m._optimization_diagnostics.write({"solution_count": 0})
            return None, None, None, None, None, {
                "cycle_lazy_count": m._cycle_lazy_count,
                "clique_lazy_count": m._clique_lazy_count,
                "clique_user_count": m._clique_user_count,
            }
        gap = m.MIPGap
        lazy_count = m._lazy_count
        lazy_breakdown = {
            "cycle_lazy_count": m._cycle_lazy_count,
            "clique_lazy_count": m._clique_lazy_count,
            "clique_user_count": m._clique_user_count,
        }
        stats = m._stats

        #print(f'add constraints: {callback_constraints[1]}')

        W_edges_vals = m.getAttr('x', W_edges_vars)
        W_weights_vals = m.getAttr('x', W_edges_weights)

        W = extract_adj_matrix(W_edges_vals, W_weights_vals, d)

        A = []
        for t in range(p):
            #A_t_edges_vals = m.getAttr('x', A_edges_vars[t])
            A_t_weights_vals = m.getAttr('x', A_edges_weights[t])
            A_t = extract_adj_matrix_no_vars(A_t_weights_vals, d)
            A.append(A_t)

        if m._enable_cycle_constraints:
            assert utils.is_dag(W)

        if m._optimization_diagnostics is not None:
            W_eval = W.copy()
            W_eval[np.abs(W_eval) < w_threshold] = 0
            final_accuracy = count_project_accuracy(
                np.asarray(B_ref).astype(int), (W_eval != 0).astype(int), [], [],
                test_dag=m._enable_cycle_constraints) \
                if B_ref is not None else {}
            m._optimization_diagnostics.write({
                "solution_count": int(sol_count),
                "objective": float(m.ObjVal),
                "best_bound": float(m.ObjBound),
                "gap": float(gap),
                "runtime": float(m.Runtime),
                "node_count": float(m.NodeCount),
                "mipnode_total": int(m._mipnode_count),
                "simplex_iteration_count": float(m.IterCount),
                "work": float(m.Work),
                "nodes_per_second": float(m.NodeCount / max(m.Runtime, 1e-12)),
                "final_shd_at_solver_threshold": final_accuracy.get("shd"),
                "final_f1_at_solver_threshold": final_accuracy.get("f1score"),
                "lazy_count": int(lazy_count),
                "best_accepted_snapshot": m._best_accepted_snapshot,
                "method_details": m._method.summary_fields(m),
                **lazy_breakdown,
            })

        # threshold_func = np.vectorize(lambda x: (x if abs(x) > threshold else 0.0))
        # W_t = threshold_func(W)

        W[np.abs(W) < w_threshold] = 0

        return W, A, gap, lazy_count, stats, lazy_breakdown
    finally:
        if m._optimization_diagnostics is not None:
            m._optimization_diagnostics.write()
        _write_method_summary(m, cfg)
        m.dispose()
        gp.disposeDefaultEnv()


if __name__ == '__main__':
    from notears import utils
    utils.set_random_seed(1)


    n, d, s0, graph_type, sem_type = 2000, 10, 30, 'ER', 'gauss'
    #n, d, s0, graph_type, sem_type = 100, 3, 20, 'PATHPERM', 'gauss'  # 7 funguje, 25 GOBNILP COUNTER EXAMPL
    #n, d, s0, graph_type, sem_type = 10, 2, 20, 'PATH', 'gauss' # 7 funguje, 25
    B_true = utils.simulate_dag(d, s0, graph_type)
    W_true = utils.simulate_parameter(B_true)
    np.savetxt('W_true.csv', W_true, delimiter=',')
    #W_true = np.loadtxt('W_true.csv', delimiter=',')

    X = utils.simulate_linear_sem(W_true, n, sem_type, noise_scale=1)
    Y = [] # TODO: add historical data
    xcol = X[:,1] / X[:,0]
    x1avg = X[:,0].sum()/n
    x2avg = X[:,1].sum()/n
    print('debug')
    print(x2avg/x1avg)

    xrat = (X[:,1]/X[:,0]).sum()/n
    print(xrat)

    np.savetxt('X.csv', X, delimiter=',')
    #X = np.loadtxt('X.csv', delimiter=',')
    cfg = OmegaConf.create()
    cfg.time_limit = 18000
    cfg.constraints_mode = 'weights'
    cfg.callback_mode = 'all_cycles'
    cfg.lambda1=1
    cfg.lambda2=1
    cfg.loss_type='l2'
    cfg.reg_type='l1'
    cfg.a_reg_type='l1'
    cfg.robust = False
    cfg.weights_bound = 100
    cfg.target_mip_gap = 0.001
    cfg.tabu_edges = False

    W_est, A_est, gap, lazy_count, stats = solve(X, cfg, 0, Y=Y, B_ref=B_true) # lambda1=0.0009
    assert utils.is_dag(W_est)
    np.savetxt('W_est_milp.csv', W_est, delimiter=',')
    acc = utils.count_accuracy(B_true, W_est != 0)
    print(f'gap: {gap}')
    print(f'lazy_count: {lazy_count}')
    print(stats)
    print(acc)
