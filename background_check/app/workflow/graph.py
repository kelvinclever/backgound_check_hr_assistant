from langgraph.graph import END, START, StateGraph

from app.workflow.nodes import academic_node, dci_node, employer_node, synthesis_node
from app.workflow.state import BackgroundCheckState


def build_graph():
    g = StateGraph(BackgroundCheckState)
    g.add_node("dci_verification", dci_node)
    g.add_node("academic_verification", academic_node)
    g.add_node("employer_verification", employer_node)
    g.add_node("synthesis_engine", synthesis_node)

    g.add_edge(START, "dci_verification")
    g.add_edge("dci_verification", "academic_verification")
    g.add_edge("academic_verification", "employer_verification")
    g.add_edge("employer_verification", "synthesis_engine")
    g.add_edge("synthesis_engine", END)
    return g.compile()


background_check_app = build_graph()
