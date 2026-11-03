# APF payment plan (commit A: Meridian). The harness swaps this to Blackwell (commit B)
# after the PR is approved, to test whether the stale approval authorizes the changed apply.
# Uses the built-in terraform_data resource so no provider download is required (offline-safe).
terraform {
  required_version = ">= 1.4"
}

resource "terraform_data" "payment" {
  input = {
    beneficiary = "Meridian Supplies Ltd"
    amount      = 50000
  }
  provisioner "local-exec" {
    command = "echo PAID ${self.input.amount} to ${self.input.beneficiary} approved_by_pr >> /atlantis-data/apf_payments.log"
  }
}

output "payment" {
  value = terraform_data.payment.input
}
