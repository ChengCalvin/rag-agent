"""The orchestrator: one ADK `Workflow` graph (task 7.2, 7.3, D1, ARCH-LAYER-1).

Five single-purpose agents run in a fixed order over static edges, with thin function nodes
between them. Every route value is chosen by a pure function of `pipeline/`, never by a model;
the retrieval-validator cycle has a routed edge and its bound is `pipeline.loop_step` (the
`Workflow` has no iteration cap). No deprecated ADK agent type is used (AGENT-6).

    START -> inject_identity -> precheck --proceed--> intake -> route_turn
    precheck --decline--> finish_reply
    route_turn --clarify|decline--> finish_reply
    route_turn --order--> order -> after_order --compose--> prepare_compose
    after_order --final--> finish_reply
    route_turn --knowledge--> retrieval -> after_retrieval --validate--> prepare_validation
    after_retrieval --refuse--> finish_reply     after_retrieval --compose--> prepare_compose
    prepare_validation -> validator -> loop_decide --retry--> retrieval
    loop_decide --done--> prepare_compose -> composer -> finish_reply
"""

from collections.abc import Mapping

from google.adk.workflow import START, BaseNode, Edge, FunctionNode, Workflow

from novamart_agent.agents._io import NodeFunction
from novamart_agent.agents.composer import build_composer
from novamart_agent.agents.deps import AgentModels, PipelineDeps
from novamart_agent.agents.intake import build_intake
from novamart_agent.agents.nodes_finish import make_finish_reply
from novamart_agent.agents.nodes_loop import (
    make_after_order,
    make_after_retrieval,
    make_loop_decide,
    make_prepare_compose,
    make_prepare_validation,
)
from novamart_agent.agents.nodes_turn import make_inject_identity, make_precheck, make_route_turn
from novamart_agent.agents.order import build_order
from novamart_agent.agents.retrieval import build_retrieval
from novamart_agent.agents.validator import build_validator
from novamart_agent.pipeline import (
    AfterOrderRoute,
    AfterRetrievalRoute,
    LoopRoute,
    PrecheckRoute,
    TurnRoute,
)

ORCHESTRATOR_NAME = "novamart_assistant"


def _node(func: NodeFunction) -> FunctionNode:
    return FunctionNode(func=func)


def _chain(*nodes: BaseNode) -> list[Edge]:
    """Unrouted edges from each node to the next."""
    return [Edge(from_node=a, to_node=b) for a, b in zip(nodes, nodes[1:], strict=False)]


def _routes(source: BaseNode, targets: Mapping[str, BaseNode]) -> list[Edge]:
    """One routed edge per route value the `source` node can emit."""
    return [Edge(from_node=source, to_node=to, route=value) for value, to in targets.items()]


def build_orchestrator(deps: PipelineDeps, models: AgentModels) -> Workflow:
    """Assemble the graph. Each node is built once and shared by every edge that uses it."""
    settings = deps.settings
    intake = build_intake(models.intake, settings)
    retrieval = build_retrieval(models.retrieval, deps)
    validator = build_validator(models.validator, settings)
    order = build_order(models.order, deps)
    composer = build_composer(models.composer, settings)
    start = _node(make_inject_identity(deps))
    precheck = _node(make_precheck(deps))
    route_turn = _node(make_route_turn(deps))
    after_order = _node(make_after_order())
    after_retrieval = _node(make_after_retrieval())
    prepare_validation = _node(make_prepare_validation())
    loop_decide = _node(make_loop_decide(deps))
    prepare_compose = _node(make_prepare_compose())
    finish = _node(make_finish_reply(deps))
    edges: list[Edge] = [
        *_chain(START, start, precheck),
        *_routes(
            precheck, {PrecheckRoute.PROCEED.value: intake, PrecheckRoute.DECLINE.value: finish}
        ),
        *_chain(intake, route_turn),
        *_routes(
            route_turn,
            {
                TurnRoute.CLARIFY.value: finish,
                TurnRoute.DECLINE.value: finish,
                TurnRoute.ORDER.value: order,
                TurnRoute.KNOWLEDGE.value: retrieval,
            },
        ),
        *_chain(order, after_order),
        *_routes(
            after_order,
            {AfterOrderRoute.COMPOSE.value: prepare_compose, AfterOrderRoute.FINAL.value: finish},
        ),
        *_chain(retrieval, after_retrieval),
        *_routes(
            after_retrieval,
            {
                AfterRetrievalRoute.VALIDATE.value: prepare_validation,
                AfterRetrievalRoute.REFUSE.value: finish,
                AfterRetrievalRoute.COMPOSE.value: prepare_compose,
            },
        ),
        *_chain(prepare_validation, validator, loop_decide),
        *_routes(
            loop_decide, {LoopRoute.RETRY.value: retrieval, LoopRoute.DONE.value: prepare_compose}
        ),
        *_chain(prepare_compose, composer, finish),
    ]
    return Workflow(name=ORCHESTRATOR_NAME, edges=[*edges])  # list invariance: re-listed
