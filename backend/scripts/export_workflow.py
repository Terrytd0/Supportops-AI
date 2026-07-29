from pathlib import Path

from backend.graph.workflow import get_graph

graph = get_graph()

png = graph.get_graph().draw_mermaid_png()

Path("workflow.png").write_bytes(png)

print("workflow.png generated successfully!")