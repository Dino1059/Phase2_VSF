# AWS single-node deployment

This stack deploys DataTrust OS to one EC2 instance in `ap-southeast-1`
(Singapore). It is intended for a credit-funded demo or staging environment,
not a highly available production topology.

## Cost controls

- Default instance: `t3.medium` (4 GiB RAM).
- One 30 GiB encrypted gp3 volume.
- No NAT Gateway, load balancer, RDS, or Elastic IP.
- A 2 GiB swap file protects the initial Docker build from transient OOMs.
- Set an AWS Budget before deployment.

## Deploy

Configure valid AWS CLI credentials, then run:

```powershell
aws cloudformation deploy `
  --region ap-southeast-1 `
  --stack-name datatrust-os `
  --template-file infrastructure/aws/cloudformation.yml `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides InstanceType=t3.medium
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

## Remove all billable resources

Back up any required PostgreSQL data, then delete the CloudFormation stack.
The EC2 root volume is configured with `DeleteOnTermination: true`.
