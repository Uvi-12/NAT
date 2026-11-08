#!/usr/bin/env python3
# Restate service under test: a payment Virtual Object whose approval is a durable awakeable.
# The awakeable id is stored in object state so an approver (the harness) can resolve it.
import restate

payment = restate.VirtualObject("payment")

@payment.handler()
async def request(ctx: restate.ObjectContext, order: dict) -> dict:
    name, future = ctx.awakeable()          # distinct per-invocation approval promise
    ctx.set("awk", name)                    # surface the id for the approver
    approval = await future                 # durable wait for resolution of THIS id
    result = {"paid": bool(approval.get("approved")),
              "amount": order["amount"], "beneficiary": order["beneficiary"],
              "approver": approval.get("approver")}
    ctx.set("result", result)
    return result

@payment.handler(kind="shared")
async def get_awk(ctx: restate.ObjectSharedContext) -> str:
    return (await ctx.get("awk")) or ""

@payment.handler(kind="shared")
async def get_result(ctx: restate.ObjectSharedContext) -> dict:
    return (await ctx.get("result")) or {}

app = restate.app([payment])
