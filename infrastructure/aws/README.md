# AWS single-node deployment

This stack deploys DataTrust OS to one EC2 instance in `ap-southeast-1`
(Singapore). It is intended for a credit-funded demo or staging environment,
not a highly available production topology.

## Cost controls

- Default instance: `c7i-flex.large` (4 GiB RAM, Free Tier eligible on
  qualifying accounts).
- One 30 GiB encrypted gp3 volume.
- One Elastic IP keeps the application URL stable across EC2 stop/start cycles.
- No NAT Gateway, load balancer, or RDS.
- A 2 GiB swap file protects the initial Docker build from transient OOMs.
- Set an AWS Budget before deployment.
- AWS charges for public IPv4 addresses; credits may cover that charge when
  the credit terms include EC2 networking.

## Deploy

Configure valid AWS CLI credentials, then run:

```powershell
aws cloudformation deploy `
  --region ap-southeast-1 `
  --stack-name datatrust-os `
  --template-file infrastructure/aws/cloudformation.yml `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides InstanceType=c7i-flex.large
```

Optionally pass `OpenAIApiKeyBase64` as a NoEcho parameter. The stack waits up
to 30 minutes for `/health` to become available before reporting success.

## Operate

Use the `SessionManagerCommand` stack output to open a shell without exposing
SSH. The checkout lives at `/opt/datatrust` and bootstrap logs are written to
`/var/log/datatrust-bootstrap.log`.

```bash
cd /opt/datatrust
sudo docker compose --env-file .env.aws -f docker-compose.aws.yml ps
sudo docker compose --env-file .env.aws -f docker-compose.aws.yml logs --tail=200
```

## CI/CD

Pushes to `mvp` run backend tests and frontend tests/build before deploying the
exact commit through AWS Systems Manager. Authentication uses GitHub OIDC; no
long-lived AWS access key is stored in GitHub.

The stack creates the tightly scoped `datatrust-github-deploy` role trusted only
by this repository's `mvp` branch. The workflow is defined in
`.github/workflows/deploy-aws.yml`.

The EC2 deployment script rebuilds the Compose services, waits for `/health`,
and checks out/rebuilds the previous commit automatically if deployment fails.

## Remove all billable resources

Back up any required PostgreSQL data, then delete the CloudFormation stack.
The EC2 root volume is configured with `DeleteOnTermination: true`.
