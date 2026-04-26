"""Graph export helpers for causal DAG visualization."""

from __future__ import annotations

from causal_credit_risk.model import CausalDAGModel


def to_dot(model: CausalDAGModel) -> str:
    """Export the model DAG as Graphviz DOT text."""
    lines: list[str] = [
        "digraph causal_credit_risk {",
        "  rankdir=LR;",
        '  node [shape=box, style="rounded,filled", fillcolor="#f8f9fb", color="#4b5563"];',
    ]

    for node_id in model.topological_order:
        node = model.nodes[node_id]
        label = f"{node.human_label}\\n({node.node_type})"
        lines.append(f'  "{node_id}" [label="{label}"];')

    for node_id in model.topological_order:
        for parent in model.nodes[node_id].parents:
            lines.append(f'  "{parent}" -> "{node_id}";')

    lines.append("}")
    return "\n".join(lines) + "\n"
