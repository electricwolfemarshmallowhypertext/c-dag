# Security Checklist

Use this checklist before any pilot or production deployment.

## Boundary controls

- [ ] API gateway authentication and authorization
- [ ] TLS enabled end-to-end
- [ ] tenant isolation defined and tested
- [ ] rate limiting configured

## Data controls

- [ ] data retention policy defined
- [ ] audit storage access controls applied
- [ ] logging boundaries reviewed
- [ ] secrets excluded from audit output

## Model and policy controls

- [ ] model and policy version locks enforced
- [ ] replay contract checks enabled
- [ ] change control approvals documented
- [ ] rollback plan documented

## Monitoring and incident response

- [ ] access logging enabled
- [ ] anomaly monitoring configured
- [ ] incident response workflow defined
- [ ] periodic control review scheduled
