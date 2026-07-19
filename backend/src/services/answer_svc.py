import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from src.llm.claude_client import ClaudeClient, EvidenceItem
from src.models.artifact import Artifact
from src.models.relationship import RelationshipOrigin
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.relationship_repository import RelationshipRepository
from src.services.retrieval_svc import RetrievalService

CITE_MARKER_RE = re.compile(r"\[cite:([^\]]+)\]")
INSUFFICIENT_EVIDENCE_MARKER = "[INSUFFICIENT_EVIDENCE]"


@dataclass
class Citation:
    artifact_id: str
    source_url: str
    artifact_type: str
    origin: str


@dataclass
class AnswerResult:
    answer: str
    abstained: bool
    citations: list[Citation] = field(default_factory=list)


class AnswerService:
    """Constitution Principle I (NON-NEGOTIABLE): every citation is validated
    against evidence this service itself retrieved — never trusted from the
    model's own claim — and the service abstains rather than returns an
    unsupported answer. Built in here at first construction (not deferred to
    a later "add validation" pass), for the same reason token encryption and
    prompt isolation were fixed to build in from the start: an MVP checkpoint
    that violates a NON-NEGOTIABLE principle isn't a real checkpoint.
    """

    def __init__(
        self,
        session: AsyncSession,
        claude_client: ClaudeClient | None = None,
        retrieval_service: RetrievalService | None = None,
    ):
        self._session = session
        self._artifacts = ArtifactRepository(session)
        self._relationships = RelationshipRepository(session)
        self._retrieval = retrieval_service or RetrievalService(session)
        self._claude = claude_client or ClaudeClient()

    async def answer_question(
        self, workspace_id: uuid.UUID, question: str, notion_doc_url: str | None = None
    ) -> AnswerResult:
        evidence_by_id = await self._gather_evidence(workspace_id, question, notion_doc_url)

        if not evidence_by_id:
            return AnswerResult(
                answer="No relevant evidence was found in the connected sources for this question.",
                abstained=True,
            )

        raw_answer = self._claude.generate_grounded_answer(question, list(evidence_by_id.values()))

        if INSUFFICIENT_EVIDENCE_MARKER in raw_answer:
            cleaned = raw_answer.replace(INSUFFICIENT_EVIDENCE_MARKER, "").strip()
            return AnswerResult(answer=cleaned, abstained=True)

        cited_ids = CITE_MARKER_RE.findall(raw_answer)
        # FR-013 (Constitution Principle I): only ever cite from the evidence
        # set we actually retrieved — an id the model mentions that isn't in
        # evidence_by_id is silently dropped, never surfaced as a citation.
        valid_citations = [
            Citation(
                artifact_id=eid,
                source_url=evidence_by_id[eid].source_url,
                artifact_type=evidence_by_id[eid].artifact_type,
                origin=evidence_by_id[eid].origin,
            )
            for eid in dict.fromkeys(cited_ids)  # de-dupe, preserve order
            if eid in evidence_by_id
        ]
        display_answer = CITE_MARKER_RE.sub("", raw_answer).strip()

        if not valid_citations:
            # A confident-sounding answer with zero grounded citations is
            # exactly what Principle I forbids — treat it as insufficient
            # evidence rather than let ungrounded prose through.
            return AnswerResult(
                answer="The available evidence did not support a confidently-cited answer to "
                "this question.",
                abstained=True,
            )

        return AnswerResult(answer=display_answer, abstained=False, citations=valid_citations)

    async def _gather_evidence(
        self, workspace_id: uuid.UUID, question: str, notion_doc_url: str | None
    ) -> dict[str, EvidenceItem]:
        evidence: dict[str, EvidenceItem] = {}

        if notion_doc_url:
            anchor = await self._artifacts.get_by_source_url(workspace_id, notion_doc_url)
            if anchor is not None:
                evidence[str(anchor.id)] = _to_evidence_item(anchor, origin="explicit")
                for rel in await self._relationships.get_for_artifact(workspace_id, anchor.id):
                    target_id = (
                        rel.target_artifact_id
                        if rel.source_artifact_id == anchor.id
                        else rel.source_artifact_id
                    )
                    target = await self._artifacts.get_by_id(workspace_id, target_id)
                    if target is not None:
                        evidence[str(target.id)] = _to_evidence_item(
                            target, origin=rel.relationship_origin
                        )

        retrieved = await self._retrieval.retrieve(workspace_id, question)
        for artifact in retrieved:
            key = str(artifact.id)
            if key not in evidence:
                evidence[key] = _to_evidence_item(artifact, origin="inferred")

        return evidence


def _to_evidence_item(artifact: Artifact, origin: str | RelationshipOrigin) -> EvidenceItem:
    return EvidenceItem(
        artifact_id=str(artifact.id),
        artifact_type=artifact.artifact_type,
        source_url=artifact.source_url,
        origin=str(origin),
        content=artifact.content,
    )
