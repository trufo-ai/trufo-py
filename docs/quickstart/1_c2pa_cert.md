# Quickstart: C2PA Signing Certificates

A C2PA Signing Certificate identifies the signing entity (software or hardware) embedded in a manifest. Two tracks are available:

| Track          | Purpose                             | Auth Required |
| -------------- | ----------------------------------- | ------------- |
| **Test**       | Development and integration testing | No            |
| **Production** | Real-world publishing               | Yes           |


> **Note:** You do not need a C2PA Signing Certificate to use the Trufo C2PA signing endpoints (`POST /c2pa/sign`) — that endpoint uses Trufo's own C2PA signer. A C2PA Signing Certificate is only required if you are operating your own conformant C2PA Generator Product. See the [C2PA Signing Certificate product page](https://app.trufo.ai/tca/certs/c2pa) for more details.

See [1_c2pa_cert.py](1_c2pa_cert.py) for a runnable example of both tracks.

---

## Test Certificate

No account authentication required. Uses a publicly known test HMAC secret; issued certificates are signed by Trufo's test CA and will not pass public validators.

```python
from trufo.api.tca.certs_test import request_c2pa_test_cert
from trufo.crypto.algorithms import SigningAlgorithm
from trufo.crypto.keygen import generate_keypair

private_pem, _ = generate_keypair(SigningAlgorithm.ES256)

cert_chain_pem = request_c2pa_test_cert(
    org_name="My Company",
    common_name="My App",
    private_key_signer=private_pem,
)
```

---

## Production Certificate

### Prerequisites

All of the following must be in place before a production certificate can be issued:

1. Trufo account with an organization
2. Organization Validation (OV) approved
3. Generator Product created with Product Validation (PV) approved
4. Active subscription
5. Instance created with a registered credential (public key)

### Key Material

Two key pairs are involved in production enrollment:


| Key              | Purpose                                                  | Lifetime                            |
| ---------------- | -------------------------------------------------------- | ----------------------------------- |
| **Instance key** | Signs the client assertion JWT sent to the RA            | Long-lived; registered per instance |
| **Leaf key**     | Signs actual C2PA manifests; embedded in the certificate | Per-certificate (up to 366 days)    |


### One-Time Setup

Run once per deployment environment to create an instance and register its credential:

```python
from trufo.api.tca.certs_c2pa import create_instance, register_credential
from trufo.crypto.algorithms import SigningAlgorithm
from trufo.crypto.keygen import generate_keypair
from trufo.util.credentials import load_session

session = load_session()

# Generate the instance key (keep the private key secure — it authorizes all CSR requests)
instance_private_pem, instance_public_pem = generate_keypair(SigningAlgorithm.ES256)

gpi_id = create_instance(session, gp_id="gp_...", name="Production server")
gpic_id = register_credential(
    session,
    gpi_id=gpi_id,
    label="prod-key-1",
    key_algorithm="ES256",
    public_key_pem=instance_public_pem.decode(),
)
# Persist gpi_id, gpic_id, and instance_private_pem securely
```

### Certificate Enrollment

Run once per certificate renewal cycle:

```python
from trufo.api.tca.certs_c2pa import request_c2pa_cert
from trufo.api.tca.tca_utils import LeafType
from trufo.crypto.algorithms import SigningAlgorithm
from trufo.crypto.keygen import generate_keypair

# this should be a NEW key
# this should be generated in a SECURE environment
leaf_private_pem, _ = generate_keypair(SigningAlgorithm.ES256)

cert_chain_pem = request_c2pa_cert(
    gpi_id=gpi_id,
    gpic_id=gpic_id,
    instance_key_pem=instance_private_pem,
    private_key_signer=leaf_private_pem,
    leaf_type=LeafType.C2PA_L1,
    validity_days=90,
)
```

**Available leaf types:**


| Value              | Max validity |
| ------------------ | ------------ |
| `LeafType.C2PA_L1` | 366 days     |
| `LeafType.C2PA_L2` | 90 days      |


---

## Reference

- RA endpoint reference: [../api/tca_ra.md](../api/tca_ra.md)
- TCA enrollment reference: [../api/tca_ca.md](../api/tca_ca.md)

