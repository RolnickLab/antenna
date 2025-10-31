

This folder adds one IAM statement needed by App Runner VPC Connector creation:
- Grants iam:PassRole scoped by iam:AWSServiceName = apprunner.amazonaws.com
- Uses Resource: "*" so AWS internals can pass the correct service linked role variant.

File:
- infra/iam_app_runner_policy_addition.json additive; merge this statement into the existing deploy policy. Nothing is replaced.
