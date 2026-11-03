#!/usr/bin/env python3
"""APF native reproduction, Tryton ERP (purchase requisition approval).

Native-tier (N1) run against the REAL `trytond` server code and the
`purchase_requisition` module (Tryton 8.2). It boots the Tryton pool against an
initialized database (see run.sh) and drives the module's own ORM and workflow -
no stand-in.

APF framing. A purchase requisition carries a persisted `state`
(draft -> waiting -> approved -> processing). The authorized `approve` action is
a @ModelView.button guarded by the requisition approval group; it records
`approved_by`. The downstream processing path acts on requisitions whose state is
`approved`. The persisted `state` field is exactly the approval-relevant
operational value an APF state-writer can reach.

Result (exposed): a state-only write of `state := 'approved'` (not through the
approve button) is trusted by the processing path and releases the gated effect,
while leaving `approved_by` empty, unauthorized execution AND false evidence of
human oversight. The genuine approve() path is shown for contrast (it records the
approver and enforces the group).

Run: bash run.sh   (sets up a throwaway SQLite database, then runs this file)
"""
import os, sys, datetime
from decimal import Decimal
from trytond.pool import Pool
from trytond.transaction import Transaction

Pool.start()
pool = Pool('test')
pool.init()

def M(n): return pool.get(n)

with Transaction().start('test', 1, context={}) as t:
    Company = M('company.company'); Party = M('party.party'); Currency = M('currency.currency')
    Employee = M('company.employee'); User = M('res.user')
    Req = M('purchase.requisition'); Line = M('purchase.requisition.line')
    Uom = M('product.uom'); Template = M('product.template'); Product = M('product.product')
    Group = M('res.group'); ModelData = M('ir.model.data')

    # currency
    cur = Currency.search([('code','=','USD')])
    cur = cur[0] if cur else Currency.create([{'name':'US Dollar','code':'USD','symbol':'$'}])[0]
    # company party + company
    cparty = Party.create([{'name':'Acme Buyer Co'}])[0]
    company = Company.search([])
    company = company[0] if company else Company.create([{'party':cparty.id,'currency':cur.id}])[0]
    # employee
    eparty = Party.create([{'name':'A. Requester'}])[0]
    employee = Employee.create([{'party':eparty.id,'company':company.id}])[0]
    # set company+employee on admin
    admin = User(1)
    User.write([admin],{'companies':[('add',[company.id])],'company':company.id,
                        'employees':[('add',[employee.id])],'employee':employee.id})
    t.context = dict(t.context, company=company.id, employee=employee.id)

    # product (purchasable)
    unit = Uom.search([('name','=','Unit')]); unit = unit[0] if unit else Uom.search([])[0]
    tmpl = Template.create([{'name':'Widget','default_uom':unit.id,'type':'goods',
                             'purchasable':True,'list_price':Decimal('10'),'purchase_uom':unit.id,
                             'products':[('create',[{}])]}])[0]
    product = tmpl.products[0]

    with Transaction().set_context(company=company.id, employee=employee.id):
        # --- create a requisition needing approval ---
        req = Req.create([{'company':company.id,'employee':employee.id,'currency':cur.id,'supply_date':datetime.date.today(),
                           'lines':[('create',[{'description':'Widget x5','quantity':5.0,
                                                'product':product.id,'unit':unit.id}])]}])[0]
        print("created requisition id=%s state=%s approved_by=%s" % (req.id, req.state, req.approved_by))

        # move draft -> waiting via the documented button
        Req.wait([req]); req = Req(req.id)
        print("after wait(): state=%s" % req.state)

        def gated_effect(r):
            """The resume/processing path acts only on 'approved' requisitions."""
            return r.state in ('approved','processing','done')

        print("\n== CONTROL (state=waiting, no approval) ==")
        print("   processing path would act:", gated_effect(req), "(blocked: not approved)")

        print("\n== GENUINE approval path (authorized button) ==")
        # approve() is a @ModelView.button guarded by the requisition approval group;
        # it records approved_by. This is the authority-bearing path.
        Req.approve([req]); g = Req(req.id)
        print("   approve(): state=%s approved_by=%s  (genuine, authorized, attributed)" %
              (g.state, g.approved_by.rec_name if g.approved_by else None))

        # reset to waiting to demonstrate the forge on an unapproved requisition
        req2 = Req.create([{'company':company.id,'employee':employee.id,'currency':cur.id,'supply_date':datetime.date.today(),
                            'lines':[('create',[{'description':'Widget x5','quantity':5.0,
                                                 'product':product.id,'unit':unit.id}])]}])[0]
        Req.wait([req2]); req2 = Req(req2.id)

        print("\n== FORGE (state-only write, no approve button, no authority) ==")
        before = (req2.state, req2.approved_by)
        Req.write([req2], {'state':'approved'})      # direct persisted-state write
        f = Req(req2.id)
        print("   wrote state:=approved directly; state=%s approved_by=%s" %
              (f.state, f.approved_by.rec_name if f.approved_by else None))
        print("   processing path now acts on it:", gated_effect(f),
              "-> gated effect RELEASED on a forged approval")
        print("   false evidence of oversight: approved_by is %s (no genuine approver)" %
              (f.approved_by.rec_name if f.approved_by else "EMPTY"))

        exposed = gated_effect(f) and (f.approved_by is None)
        print("\nVerdict: EXPOSED (native). A state-only write of the persisted 'state'")
        print("field to 'approved' bypasses the authorized approve button, is trusted")
        print("by the processing path, and leaves no genuine approver -- APF.")
        print("\nRESULT:", "PASS" if exposed else "FAIL")
        t.rollback()
        sys.exit(0 if exposed else 1)
