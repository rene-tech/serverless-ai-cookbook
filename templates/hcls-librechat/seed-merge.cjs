'use strict';

const { isDeepStrictEqual } = require('node:util');

/** Three-way merge platform seed updates without clobbering customer changes.
 * Missing baselines identify a legacy install: preserve its existing fields.
 * Once recorded, untouched fields follow the default; customized fields stay.
 */
function mergeSeed(existing, previous, next) {
  if (!existing) return { ...next };
  const updates = {};
  for (const [key, value] of Object.entries(next)) {
    if (!(key in existing) || (previous && isDeepStrictEqual(existing[key], previous[key]))) {
      updates[key] = value;
    }
  }
  return updates;
}

module.exports = { mergeSeed };
