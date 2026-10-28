# Interactive Isaac for Healthcare

This extension runs an ordinary upstream or project-authored workflow with the
actual Isaac GUI, video and keyboard/pointer teleoperation. It contains a process
supervisor, authenticated WebRTC signaling boundary, NVIDIA browser client and
native-session integration. CPU checks cover the boundary; interactive GPU,
browser media, teleoperation and shared capacity qualification remain pending.
The qualified finite batch recipes do not establish interactive readiness.

## Runtime and project contract

Use the general recipe's project archive and `project.prepare_project()` result.
Any supported workflow/mode may be selected; no acceptance fixture, filename or
customer identity enables this path. Interactive input records remain in that
session's project/output directory. Keyboard/mouse control uses the official
WebRTC input channel. USB/serial robots, physical actuators and CloudXR devices
require their own device/network mapping; this recipe does not claim remote
physical-device control or clinical operation.

Install this subtree into the same immutable runtime image as the general
`isaac-healthcare-runtime` package. The installed Python must use `-I -B`.
`i4h_interactive.prepare` takes the verified general project context and an
ordinary upstream argv list. It writes the final context with official Kit
stream settings before AppLauncher initializes Isaac. No shell interpolation
or workflow allowlist is used. The general runtime's `context.kit_arguments`
hook is required.

The operator supplies a session JSON with `session_id`, `media_host`,
`signal_port: 49100`, `media_port: 47998`, `proxy_port`, exact HTTPS
`browser_origin`, absolute new `work_dir`, existing admitted `deadline_at`
(Unix seconds), `startup_timeout_seconds`, `stop_grace_seconds`, and
`network_mode` (`authenticated-private-network` or `turn-relay`). TURN mode also
requires `turn_url`, e.g. `turns:turn.example.org:443?transport=tcp`.
Build the viewer from this same pinned recipe revision and retain its manifest:

```sh
python3 browser/build_artifact.py --output /work/isaac-viewer-artifact
```

This runs the locked npm install, TypeScript check and fresh Vite build, then
creates a new artifact with complete source/file hashes. Mount its `dist/`
read-only at `/opt/isaac-viewer` in the interactive container. Add
`"viewer_dist": "/opt/isaac-viewer"` to the session settings before preparation;
the generated configuration retains that value. The ordinary server uses these
exact files for `/` and `/assets/`. Without `viewer_dist`, it exposes the
authenticated transport endpoints but does not serve the browser. Use the
matching interactive runtime containing `i4h_interactive.server`; the separate
finite batch image does not contain this interactive extension.

The final command is generated, not supplied by the browser:

```sh
python -I -B -m i4h_interactive.prepare \
  --context /work/prepared-project/context.json \
  --session /work/session-settings.json --output /work/interactive-plan \
  --python /opt/i4h/arena/.venv/bin/python \
  -- --workflow your_workflow --mode teleop --teleop-device keyboard \
     --record /work/output/demonstrations.hdf5

python -I -B -m i4h_interactive.server \
  --config /work/interactive-plan/session.json --token-file /run/secrets/session-token
```

The portable token is a unique random 32-byte URL-safe capability mounted as a
file for this session. It is neither a cloud API key nor a repository secret.
The proxy binds loopback only. A reviewed TLS ingress validates the exact user
and session before forwarding to it; use the token in a bearer header, never a
URL. NVIDIA SDK 6.7.0 sends it as `Authorization.Bearer.<token>` alongside
`x-nv-sessionid.<session-id>` in WebSocket subprotocols. The proxy strips the
credential before forwarding to Kit. Native Scientific AI uses its own one-use
HttpOnly cookie and bound lease instead of the portable capability.

Use an isolated container/Pod and storage directory for each active session.
The supervisor starts Kit once, forwards shutdown to the entire process group,
joins cleanup, and never restarts science. A browser signaling disconnect detaches that viewer and preserves the same
process until explicit stop, workflow completion or the existing native deadline. `/health` and `/stop` require its capability. Health does not equate a
listening socket with decoded video; `media_ready` remains unknown until actual
browser evidence exists. Process cleanup is only a witness; native resource
release remains the native owner's decision.

## Docker and on-premises networking

[Isaac Sim 6.0.1 requires NVENC, a compatible driver and host networking for its
documented Docker streaming path](https://docs.isaacsim.omniverse.nvidia.com/6.0.1/installation/manual_livestream_clients.html).
Expose NVIDIA driver capabilities `compute,utility,graphics,video,display` and
the encode library. A batch-compatible CUDA GPU does not establish NVENC support.
Use the NVIDIA encode capability/runtime probe on the actual assigned GPU and
perform an actual encode/decoded-frame test; do not select hardware by a fixture.
Hopper batch results cannot be reused as interactive streaming evidence.

Use `docker run --gpus <assigned-device> --network=host` on the Ubuntu GPU host,
mount the project read-only and isolated outputs/cache/home writable, and use the
same immutable image. Retain the image digest and actual driver/encoder results.
Do not publish raw TCP 49100, UDP 47998 or the unauthenticated upstream viewer
8210 to the Internet. An authenticated VPN/private network may carry the direct
stream. Each concurrent host-network instance needs distinct signal/media ports;
the existing workload owner allocates them. Docker `-p` bridge mappings are not
the documented replacement for host networking.

## Browser and authenticated TURN

`browser/` pins NVIDIA `@nvidia/ov-web-rtc` 6.7.0. The artifact command above runs
`npm ci`, `npm run check`, and `npm run build`; serve its verified `dist` only on the authenticated session's HTTPS
origin. A standalone viewer opened at `<session>/viewer/` reads its descriptor
with the HttpOnly session cookie. An embedded viewer accepts a descriptor only
from its same-origin opener/parent. Nothing stores API keys in browser storage.
The client sets `newSession:false`, `maxReconnects:0`, WSS and relay-only ICE.
It reports media readiness only after a decoded video frame, preserving native
session status as resource authority. Mouse/keyboard input targets the streamed
virtual scene; built-in browser shortcuts may still require user focus.

The proposed cloud topology is:

```text
Browser -- authenticated HTTPS/WSS --> existing App/native session --> private Kit signaling
Browser -- authenticated TURN over TLS --> CPU relay -- UDP 47998 --> same isolated Kit
                       DTLS/SRTP media and input remain end-to-end
```

`render_relay.py` emits a review-only Kubernetes List: a CPU Deployment,
ConfigMap, separate LoadBalancer Service and narrow NetworkPolicies. It
creates no resources, Secret or namespace. Supply an immutable coturn image,
TLS hostname/certificate Secret, auth Secret, authoritative worker allocation CIDRs
(`--pod-cidr` may be repeated), and an operator-selected relay port range. Derive
these ranges from the cluster's provider subnet/IPAM allocation authority and
exclude Service CIDRs. Do not derive a permanent allowlist from the current
GPU nodes: autoscaled nodes may receive different Pod CIDRs. A shared provider
pool can include node addresses too; its CIDRs bound addressing, while the
namespace/model NetworkPolicy restricts relay traffic to the intended Pods and
UDP port. Re-read this binding when the subnet, pool or Service CIDRs change;
ordinary node scaling inside the bound allocation domain requires no edits. The initial
1 CPU/1 GiB request and 2 CPU/2 GiB limit are an unmeasured pilot envelope, not a
capacity claim. Listener readiness is not stream health. Confirm the image
contains `/bin/sh` and `turnserver` and supports its non-root configuration.

The default `--relay-address-mode private-pod` exposes only public TURN TLS
(use `--service-port 5349` for its standard port). The relay advertises its actual
Pod IPv4 through the ordinary Deployment downward API. Browser datagrams travel
inside TURN-over-TLS, while the relay and same-region Kit communicate over private
UDP. Only the selected worker Pods can reach the relay allocation ports; no UDP
LoadBalancer support, public media ports, or cross-region routing is assumed.

```bash
python render_relay.py --namespace "$RELAY_NAMESPACE" --worker-namespace "$WORKER_NAMESPACE" \
  --model "$NATIVE_INFERENCESERVICE" --image "$PINNED_TURN_IMAGE" \
  --relay-address-mode private-pod --hostname "$TURN_HOSTNAME" \
  --tls-secret turn-tls --auth-secret turn-auth --pod-cidr "$WORKER_ALLOCATION_CIDR" \
  --relay-min 52000 --relay-max 52031 --service-port 5349 --output relay.json
```

For an on-premises network with qualified public UDP/NAT routing, select
`--relay-address-mode public-nat --public-ip "$ACTUAL_RELAY_PUBLIC_IPV4"`.
That mode also exposes the selected UDP range and advertises the public address;
the NAT must preserve relay port numbers and the peer address used by TURN
permissions. Supplying `--public-ip` without a mode preserves this original
behavior. Do not broaden peer permissions to hide a source-NAT mismatch.
[Nebius's load-balancer contract](https://docs.nebius.com/kubernetes/clusters/load-balancer)
does not support `externalTrafficPolicy: Local` or PROXY protocol and does not
establish public mixed-protocol behavior. Use the private-Pod transport there
until a different path has actual evidence.

TURN credentials are HMAC-derived for the native session ID and expire at its
existing deadline. They do not confer access to signaling or bypass WebRTC's
DTLS fingerprint. Relay egress is limited to the exact model's worker Pods on
UDP 47998; no unrestricted private-network proxy is opened. The native endpoint
retains its existing ingress policy; the additive media policy admits only the
relay. Run coturn in its dedicated, non-host-network Pod; selected workers must
also use ordinary Pod networking. Check all Kubernetes and Cilium policies that
select the relay, because their allows combine. The relay requires no DNS or
other outbound exception. Do not colocate it with a Gateway sidecar that needs
DNS, controller or ACME egress: those permissions would also apply to TURN.
Configure one relay in each region with an actual route to its workers;
cross-region connectivity is not assumed. The allocator must provide a stable
public TCP address and the peer must reach the advertised private or public UDP
relay address, according to the selected mode. HTTPRoutes alone do not provide
TURN transport. TURN-over-TCP performance under packet loss remains a separate
measurement; this source makes no latency or sustained-capacity claim.

Provide an ordinary trusted, hostname-matching certificate before starting the
standalone relay. A dedicated HTTP-01 Gateway/Service can obtain a certificate for
an operator-owned address using its DNS name or an IP-derived sslip.io hostname;
keep ACME validation reachable independently of TURN readiness. Do not alter a
shared Gateway's hostname-less listener or use browser certificate exceptions.
An existing task Gateway may forward raw TCP/TLS to a separate ClusterIP relay
Service with a TCPRoute. Keep its HTTP-01 listener and public Service identity,
and restrict relay TCP ingress to that Gateway's Pods. The Gateway may retain
its own DNS/controller/ACME policy; those permissions must not select the relay.
Complete certificate issuance before requiring relay readiness, and gate public
interactive admission separately.

The auth Secret's `secret` key contains a private random 32-byte value encoded as
64 lowercase hex characters. The App uses those identical ASCII bytes for HMAC;
the key is never returned to a browser or authored project. `turn-supervisor.sh`
reads one atomic TLS Secret revision, verifies its chain/hostname/key pair, and
uses coturn SIGUSR2 to reload valid renewals without restarting allocations.
Invalid revisions leave the prior TLS context active and report an operator error.
Monitor certificate expiry and prove renewal in the actual deployment.

TURN authenticates allocation; native cancellation terminates the associated
Kit process and its DTLS state. TURN allocations may persist until their normal
refresh/timeout. Before replacing a shared relay, stop new admissions through
the existing owner, wait for native sessions and relay allocations to drain,
and retain fresh counters. Missing measurements are unknown. There is no second
session scheduler or autoscaler in this recipe.

## Native and provider integration boundaries

`i4h_interactive.native.application` wraps the engine with existing Native201
attach/watch/release APIs. It trusts the API-verified Pod/connection/owner tuple,
starts the prepared project only after attach, polls cancellation/deadline, and
releases only after joined process cleanup. Unknown cleanup/release disables
local readiness and remains charged/unknown natively. It has no admission API. `bridge.py` keeps that one native WebSocket alive while
browser peers detach and reattach with new one-use cookies. Its registry owns
transport connections only. It never allocates a replacement session. The
bridge is a separate CPU Deployment with one explicit connection owner; its
restart ends the native connection and is surfaced as failure, not automatic
science replay. Native status remains authoritative throughout.

MCP cannot transfer a browser login. A create result contains a noncredential
handoff ID and same-origin attachment path. The user logs into that origin with
the same Scientific AI identity (or supplies their own API key to the HTTPS
attachment form, kept in memory only). An authenticated POST exchanges that
handoff for a Secure, HttpOnly, SameSite=Strict cookie; no API key, native claim
or attach credential appears in a link. Reconnect performs a new owner-authenticated
attachment exchange for the existing session. Keepalive reads that session and
does not extend Native201's fixed deadline. Stop requests native cancellation.

The App returns a scoped project descriptor only after normal artifact grants.
The signed start envelope binds native ID, image, revision and deadline. The
worker receives only a model-specific derived verification key, not the App's
signing key or a customer API key. The project's full byte count/SHA is checked
before extraction. Each project's Python imports run in a fresh child process;
its policy services remain in the same general runtime context and are joined
before native release. On close, scientific files are archived with per-file
hashes and uploaded to the same owner's two scoped destinations. Delivery alone
does not assert successful teleoperation or a valid demonstration.

The provider Endpoint schema exposes HTTP/TCP/UDP ports; its managed HTTP token
does not authenticate arbitrary raw ports. A provider interactive deployment
still needs a qualified host-network/routed-UDP design, scoped TLS signaling and
TURN/private access. No provider Endpoint deployment is claimed by this source.
The already-qualified finite Job path remains separate.

Before enabling customers, qualify the exact image on NVENC hardware: actual
browser video and input; owner isolation and unauthorized controls; cancellation
and disconnected-client cleanup; relay-only ICE on a UDP-blocked client; two
concurrent users; shared batch contention; drain/recovery; sustainable load and
native placement/fallback. Preserve existing customers and use the existing
admission owner throughout.

References: [NVIDIA stream authorization](https://docs.omniverse.nvidia.com/ovas/latest/configuration/streaming-authorization.html),
[NVIDIA Web SDK](https://docs.omniverse.nvidia.com/ov-web-sdk/latest/web-streaming-library/overview.html).


## Immutable builds and deployment review

Build contexts exclude dependency trees, virtual environments and generated
browser bundles. Commit `requirements.lock`, `uv.lock` and the browser npm lock.
Build the UI with `npm ci --ignore-scripts && npm run check && npm run build` and
copy its generated `dist` into the App image at build time. Do not commit it.

```sh
docker build -f Dockerfile.bridge --build-arg CPU_BASE="$PINNED_PYTHON_BASE" \
  -t "$YOUR_REGISTRY/isaac-interactive-bridge:$UNIQUE_BUILD_TAG" .
docker build -f Dockerfile.worker --build-arg ISAAC_RUNTIME_BASE="$PINNED_GENERAL_ISAAC_RUNTIME" \
  --build-arg WORKER_CONFIG=worker.json \
  -t "$YOUR_REGISTRY/isaac-interactive-worker:$UNIQUE_BUILD_TAG" .
```

Both base references must include full immutable digests. Publish to your own
registry, read back each manifest/config/layer, and use the resulting full
digests in the reviewed native endpoint and CPU deployment. Before the worker
build, copy `examples/native-worker.json` to `worker.json` and set its nonsecret
model/revision/origin/runtime values. This file is baked at
`/opt/interactive/worker.json`; the default entrypoint loads it there. Its
`image_env` reads `I4H_EXPECTED_IMAGE`, supplied through the ordinary native
`env` field after publication: an image cannot bake its own manifest digest.
The bridge starts
`i4h_interactive.bridge` with explicit config, token file and TLS key/certificate
files. No Secret is baked into either image. Build the supplied coturn overlay:

```bash
docker build -f Dockerfile.turn -t "$YOUR_REGISTRY/isaac-turn:$UNIQUE_BUILD_TAG" .
```

`Dockerfile.turn` pins official coturn 4.6.3 and removes its executable's unused
CAP_NET_BIND_SERVICE file attribute, while verifying unchanged binary bytes.
The original executable fails under `cap-drop=ALL`; the overlay runs nonroot
without that capability on port 5349. Publish and verify its immutable digest
before rendering. The image includes the shell, OpenSSL and core utilities used
by the supervisor; no package is installed at startup.

An isolated CPU proof passed verified TLS, authenticated private-UDP payload
exchange, invalid-credential denial, and certificate reload preserving an existing
allocation. This does not qualify a provider load balancer, Chromium ICE, NVIDIA
encoding, interactive latency, or shared capacity; those remain live release gates.

`examples/native-worker.json`, `examples/native-security.json` and
`examples/bridge.json` are templates, not enabled deployment specifications.
Replace image/revision/origin values with reviewed bindings, provide the normal
NVIDIA graphics/video driver capabilities, and supply the projected Native token
at its documented path. Native201 supports `env_secrets`; use a model-specific
Secret containing only `I4H_MODEL_START_KEY_HEX`. The controller consumes and
removes that environment value before starting a listener or project. Never
include the App signing key. The worker derives its own Pod IPv4 from its exact
hostname entry in `/etc/hosts`, failing if missing or ambiguous; its value must
match the operator's actual Pod readback. It does not use an unsupported
`env_field_refs: status.podIP` projection.

`examples/native-security.json` is an optional lower-level renderer hardening
fragment, **not** a directly applicable Kubernetes manifest or Native201 model API field. Native201 does not project those
container security fields or arbitrary config/Secret mounts from a model spec.
The ordinary native path instead uses the baked config, supported secret env,
bounded `empty_dirs`, native projected token and the self-enforcing entrypoint.
The examples use a 600-second startup and 30-second stop grace for review; they
are not measured readiness/latency claims.

`render_bridge.py` emits one CPU Deployment and private ClusterIP Service. Its
250m CPU/256 MiB request, 1 CPU/1 GiB limit and one replica are an unmeasured pilot
envelope. The bridge requires an exact trusted TLS origin reachable by the App;
it is not publicly exposed. Bind ingress to App pods and egress to the exact
native HTTPS route using the operator's existing network-policy mechanism.
Do not broaden a shared Gateway or disable native authorization. The TURN
Service is separate and requires the operator's supported mixed TCP/UDP L4
implementation, static address binding and matching TLS certificate. A rendered
manifest is not evidence that the provider supports that network path.

No rollout is authorized by rendering these templates. The existing platform
owner admits all GPU sessions, and its queues/limits remain authoritative. A
shared bridge/relay rollout must first stop new native admissions through that
owner and drain its exact active connections; a replica count is not measured
customer capacity.


## Authored project isolation and failed output retention

The native worker requires an isolated container PID and IPC namespace,
[Linux Landlock](https://docs.kernel.org/userspace-api/landlock.html) ABI 3 or newer, and its normal assigned
GPU devices. A kernel version alone does not prove Landlock is enabled: startup
runs the real syscall probe and fails closed. No fallback removes isolation.
Only the trusted controller runs as UID 0. Before starting threads, listeners
or project code, it makes itself nondumpable, sets `no_new_privs`, drops its
effective/permitted/bounding capabilities to `CHOWN`, `SETUID`, `SETGID` and
`KILL`, and applies a Landlock filesystem boundary. Required rights must actually
be available at startup; the process fails closed if it cannot enforce this.
This path also works with a writable root filesystem: runtime writes are denied
by Landlock. A read-only root filesystem is additional hardening when the
operator's supported deployment interface exposes it.
It needs neither privileged mode nor host PID/IPC nor `SYS_ADMIN`. Platform
network policies still own egress and must exclude cloud metadata and unrelated
workloads; filesystem isolation is not a network authorization mechanism.

Each project receives a new reserved UID/GID, a private HOME/cache/temp directory,
a scrubbed environment and an inherited Landlock policy. Only immutable runtime
paths, container-assigned GPU devices, that session's workspace and its private
short Unix-bus directory are accessible. The native Pod token, derived signing
key, controller process environment and prior session directories are excluded,
even if a projected token is world-readable. Project execution inherits no
customer API keys or native credentials. The shared-runtime hook honors
`I4H_BUS_ROOT`; it keeps policy backend sockets in the private short directory.
CUDA also needs to name current and future threads through procfs. The inherited
policy grants only file-write and truncate rights on `/proc`, subject to the
kernel's process-ownership checks. It permits kernel-authorized own-process
controls, including memory and OOM adjustment; it does not grant another
session's UID or the nondumpable controller's rights. Startup and child launch
require `/proc/bus`, `/proc/fs`, `/proc/irq`, `/proc/sys` and
`/proc/sysrq-trigger` to remain read-only. No process may create device nodes or
remove this inherited boundary.
The controller joins every owned process, checks the dedicated PID namespace,
clears its POSIX/System-V shared memory, and seals retained files to controller
ownership before reuse. Any unknown descendant or cleanup disables readiness.
Already-exited adopted children are joined only after their UID, parent and
process-start identity match; the managed leader and pre-existing processes
remain excluded. Malformed identity metadata also quarantines the worker.

Simulator construction errors retain a nonzero exit even when upstream teardown
would otherwise exit successfully. A process that exits before signaling is
ready is an initialization failure. The worker sends its terminal execution
observation through the authenticated bridge, bound to the exact signed start,
session, image and runtime revision. Scientific AI persists that observation
when read and reports a sanitized cause through status and result. This is
separate from Native lifecycle settlement and physical resource release. If the
bridge disappears before observation, the cause may remain unknown; retrieval
of the same session must not imply replaying its scientific work.

Output publication sends exact Content-Length and X-FS2-Artifact-SHA256 headers
for two write-once targets: the archive and its delivery receipt. An unknown PUT
outcome is never retried automatically. A failed delivery quarantines the worker
and preserves its session directory for operator export; `/livez` remains alive,
while `/healthz` becomes unavailable. This retention is **Pod-local**, and Pod
loss or scale-down can lose it. It is not a durable recovery guarantee. Native201
exposes an explicitly configured shared-filesystem claim through the endpoint
`weights` contract. Its lower-level renderer also supports RWO persistent
volumes, but those fields are not projected by the Native201 model API. An
operator must review storage, ownership and replica semantics before using any
shared claim for durable output. No volume is provisioned by this recipe.

`tests/isolation_cpu.py` exercises real hostile child processes in a CPU-only
container with a writable root and ordinary initial Docker capabilities:
attempts to read authority/another owner's state, regain
UID 0 and mutate runtime files must fail. It also checks IPC cleanup and a
purposefully detached descendant's quarantine. These checks do not establish
NVENC availability, functioning WebRTC, teleoperation latency, GPU concurrency,
or the target cluster's enabled Landlock support. Qualify those on the exact
image and actual relay/worker topology before enabling the public capability.

The relay renderer’s `model` argument is the actual KServe InferenceService
name used in Pod labels. For distinct native variants, retain exact policies
for each rendered worker identity; never broaden the selector to every GPU Pod.

Before enabling authored projects, inspect cluster-wide as well as namespaced
network policies. Native201's tenant egress policies select tenant-labelled
namespaces; they need not select endpoint workers in `models`. Its declared-port
policy constrains ingress only. Require an exact-model egress boundary against
instance metadata and unintended control-plane access while preserving DNS,
authenticated native/App artifact delivery, external customer assets and the
regional TURN peer range. Batch Jobs already covered by their tenant execution
profile must retain that profile; do not broaden shared policies automatically.
No instance metadata token request is needed to review policy selectors.
