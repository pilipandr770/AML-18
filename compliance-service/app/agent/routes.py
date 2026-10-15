import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

from flask import Blueprint, current_app, jsonify, request
from pydantic import BaseModel, Field

from app.agent.factory import get_runtime
from app.agent.models import AgentCase, DepositAddress
from app.agent.runner import process_case
from app.agent.tools import fmt_amount
from app.developer_portal.auth import require_api_key
from app.extensions import db

agent_bp = Blueprint("agent", __name__, url_prefix="/agent")
logger = logging.getLogger(__name__)


class TransferIn(BaseModel):
    external_ref: Optional[str] = Field(default=None, max_length=128)
    chain: str = Field(min_length=1, max_length=32)
    asset: str = Field(min_length=1, max_length=16)
    amount: str
    tx_hash: Optional[str] = Field(default=None, max_length=128)
    deposit_address: str = Field(min_length=1, max_length=128)
    counterparty_name: Optional[str] = Field(default=None, max_length=256)
    counterparty_country: Optional[str] = Field(default=None, max_length=8)
    counterparty_address: Optional[str] = Field(default=None, max_length=128)
    memo: Optional[str] = Field(default=None, max_length=2000)


class DepositIn(BaseModel):
    chain: str = Field(min_length=1, max_length=32)
    asset: str = Field(default="ETH", max_length=16)
    address: str = Field(min_length=1, max_length=128)


def _disabled():
    if not current_app.config["AGENT_ENABLED"]:
        return jsonify({"error": "agent is not enabled on this deployment"}), 404
    return None


def case_summary(c: AgentCase) -> dict:
    return {
        "case_id": c.public_id, "status": c.status, "classification": c.classification,
        "deterministic_decision": c.deterministic_decision, "explanation": c.explanation,
        "funds_verified": bool((c.funds_check or {}).get("verified")), "amount": fmt_amount(c.amount),
        "asset": c.asset, "chain": c.chain, "tx_hash": c.tx_hash,
    }


@agent_bp.post("/transfers")
def submit_transfer():
    if (disabled := _disabled()):
        return disabled
    project, error = require_api_key()
    if error:
        return error
    try:
        body = TransferIn.model_validate(request.get_json(force=True))
        amount = Decimal(body.amount)
        if amount <= 0:
            raise InvalidOperation
    except Exception:
        return jsonify({"error": "bad request"}), 400

    if body.tx_hash:
        existing = AgentCase.query.filter_by(developer_project_id=project.id, tx_hash=body.tx_hash).first()
        if existing:
            return jsonify(case_summary(existing)), 200

    case = AgentCase(
        developer_project_id=project.id, external_ref=body.external_ref, chain=body.chain, asset=body.asset,
        amount=amount, tx_hash=body.tx_hash, deposit_address=body.deposit_address,
        counterparty_name=body.counterparty_name, counterparty_country=body.counterparty_country,
        counterparty_address=body.counterparty_address, memo=body.memo,
    )
    db.session.add(case)
    db.session.commit()
    rt = get_runtime(current_app)
    process_case(case, project, current_app.config, rt.llm, rt.ledger, rt.executor)
    return jsonify(case_summary(case)), 201


@agent_bp.get("/cases/<case_id>")
def get_case(case_id):
    if (disabled := _disabled()):
        return disabled
    project, error = require_api_key()
    if error:
        return error
    case = AgentCase.query.filter_by(public_id=case_id, developer_project_id=project.id).first()
    if case is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(case_summary(case)), 200


@agent_bp.post("/deposit-addresses")
def register_deposit():
    if (disabled := _disabled()):
        return disabled
    project, error = require_api_key()
    if error:
        return error
    try:
        body = DepositIn.model_validate(request.get_json(force=True))
    except Exception:
        return jsonify({"error": "bad request"}), 400
    row = DepositAddress.query.filter_by(developer_project_id=project.id, chain=body.chain, address=body.address).first()
    if row is None:
        row = DepositAddress(developer_project_id=project.id, chain=body.chain, asset=body.asset, address=body.address)
        db.session.add(row)
        db.session.commit()
    return jsonify({"chain": row.chain, "address": row.address, "asset": row.asset}), 201
