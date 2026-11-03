// APF Inngest function under test + a small result sink.
// The payment function waits for an approval event whose data.runId matches the triggering
// run (match: "data.runId"). This run-scoped correlation is the defense the REPLAY tests.
import express from "express";
import { serve } from "inngest/express";
import { Inngest } from "inngest";

export const inngest = new Inngest({ id: "apf-app", isDev: true });

const SINK = new Map(); // runId -> result

export const payment = inngest.createFunction(
  { id: "payment" },
  { event: "apf/payment.requested" },
  async ({ event, step }) => {
    const approval = await step.waitForEvent("wait-approval", {
      event: "apf/approval",
      match: "data.runId",        // only an approval carrying THIS run's id resumes it
      timeout: "2m",
    });
    const result = approval && approval.data.approved
      ? { paid: true, amount: event.data.amount, beneficiary: event.data.beneficiary, approver: approval.data.approver }
      : { paid: false };
    await step.run("record-result", async () => {
      await fetch("http://localhost:3000/record", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ runId: event.data.runId, result }),
      });
    });
    return result;
  }
);

const app = express();
app.use(express.json());
app.post("/record", (req, res) => { SINK.set(req.body.runId, req.body.result); res.json({ ok: true }); });
app.get("/result/:runId", (req, res) => { res.json(SINK.get(req.params.runId) || null); });
app.use("/api/inngest", serve({ client: inngest, functions: [payment] }));
app.listen(3000, () => console.log("apf inngest function server on :3000"));
