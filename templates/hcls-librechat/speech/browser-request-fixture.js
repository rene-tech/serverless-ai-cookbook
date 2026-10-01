async function call(url, options = {}) {
  const response = await fetch(url, options); const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Fixture HTTP ${response.status}`);
  return body;
}
export const request = { get: call,
  post: (url, body) => call(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }),
  postMultiPart: (url, body) => call(url, { method: 'POST', body }),
};
