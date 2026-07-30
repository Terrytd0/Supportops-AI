from pathlib import Path

from backend.core.logging import configure_logging, get_logger
from backend.graph.workflow import get_graph

configure_logging()
logger = get_logger(__name__)

graph = get_graph()

png = graph.get_graph().draw_mermaid_png()

Path("workflow.png").write_bytes(png)

logger.info("workflow.png generated successfully!")
