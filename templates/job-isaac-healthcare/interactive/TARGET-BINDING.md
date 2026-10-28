# Native target transport binding

The bridge configuration follows `bridge.schema.json`: each operator-approved
row binds the authoritative Native session region and exact target
`{cluster, variant, id, image, gpu_class}` to one configured WSS URL and runtime
revision. Null variant/class values remain null where Native returns them.
The bridge accepts no supplied URL and never derives a hostname from an ID.
Unknown targets, changed images, duplicate object mappings, or inconsistent
signed start envelopes fail before opening a Native socket.

The App can omit its operator profile's region to let the existing Native owner
choose among declared compatible targets. It saves the returned target and
approved transport mapping once; idempotent replay, viewer reconnect, input/output
authorization and later Native GETs retain that binding. They never submit a
second session to seek another worker. The start signature covers the selected
region/target together with image, runtime revision and deadline; the unchanged
worker checks that signature and its installed image/runtime identity.
Native's targeted-placement feature and trusted selected-route enforcement must
be deployed and qualified first. This source does not enable that feature.

Configure `turn_secrets` by exact Native region when regional relays use different
keys. Alternatively, `turn_secret` deliberately shares one operator key across
the configured relays; select exactly one form, and never persist a key in session
receipts. A region always uses its saved approved TURN URL. Every approved bridge
uses the separately configured private bridge service credential. Changing an
admitted object's image or transport mapping fails closed; drain through the
Native owner before replacing such mappings.

If the mapped Native endpoints use a private CA, render the CPU bridge with
`--trust-bundle-config YOUR_APPROVED_CA_CONFIGMAP` and, when needed,
`--trust-bundle-key YOUR_CONFIGMAP_KEY`. This mounts the operator's reviewed CA
bundle read-only and sets `SSL_CERT_FILE`; Python still verifies the configured
endpoint hostname and certificate chain. The bundle must cover every mapped
endpoint served by that bridge. This does not change browser trust or authorize
arbitrary destinations. Private bridge TLS likewise needs a certificate whose
SAN matches the configured bridge origin and a CA trusted by the App.
