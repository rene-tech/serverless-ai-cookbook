#!/bin/sh
# Runs only in the dedicated, nonroot CPU relay container.
set -eu
umask 077
: "${POD_IP:?Downward API Pod IPv4 is required}"
: "${TURN_REALM:?Certificate hostname is required}"
mkdir -p /state/certs
current_revision=''
child=''

install_certificate() {
  # Read one atomic Kubernetes Secret revision; never mix certificate/key updates.
  revision="$(readlink -f /tls/..data 2>/dev/null || true)"
  case "$revision" in /tls/..*) ;; *) return 1 ;; esac
  [ "$revision" != "$current_revision" ] || return 0
  [ -r "$revision/tls.crt" ] && [ -r "$revision/tls.key" ] || return 1
  name="$(sha256sum "$revision/tls.crt" "$revision/tls.key" | sha256sum | cut -d' ' -f1)"
  destination="/state/certs/$name"
  mkdir -p "$destination"
  cp "$revision/tls.crt" "$destination/tls.crt"
  cp "$revision/tls.key" "$destination/tls.key"
  openssl x509 -in "$destination/tls.crt" -checkend 0 -checkhost "$TURN_REALM" -noout >/dev/null 2>&1 || return 1
  openssl verify -CApath /etc/ssl/certs -untrusted "$destination/tls.crt" "$destination/tls.crt" >/dev/null 2>&1 || return 1
  openssl x509 -in "$destination/tls.crt" -pubkey -noout > "$destination/certificate.pub"
  openssl pkey -in "$destination/tls.key" -pubout > "$destination/key.pub" 2>/dev/null
  cmp -s "$destination/certificate.pub" "$destination/key.pub" || return 1
  ln -s "$destination" /state/current.next
  mv -Tf /state/current.next /state/current
  current_revision="$revision"
  if [ -n "$child" ]; then
    kill -USR2 "$child"
    printf '%s\n' 'Reloaded a verified TLS certificate revision.'
  fi
}

stop() {
  if [ -n "$child" ]; then kill -TERM "$child" 2>/dev/null || true; fi
}
trap stop TERM INT
until install_certificate; do sleep 5; done
secret="$(cat /auth/secret)"
case "$secret" in ''|*[!0-9a-f]*) printf '%s\n' 'TURN secret must be lowercase hexadecimal.' >&2; exit 2 ;; esac
[ "${#secret}" -eq 64 ] || exit 2
cat /config/turnserver.conf > /state/turnserver.conf
printf 'static-auth-secret=%s\nrelay-ip=%s\nlistening-ip=%s\nrealm=%s\n' "$secret" "$POD_IP" "$POD_IP" "$TURN_REALM" >> /state/turnserver.conf
unset secret
/usr/bin/turnserver -c /state/turnserver.conf &
child="$!"
while kill -0 "$child" 2>/dev/null; do
  sleep 5 &
  wait "$!" || true
  install_certificate || printf '%s\n' 'TLS revision is unavailable or invalid; retaining the current TLS context.' >&2
done
wait "$child"
