#!/usr/bin/env node
// Full MongoDB state transfer for a drained operator-owned workbench. Run from
// /app inside the pinned image. Stream private output over SSH, never to logs.
// Not a point-in-time backup while the application is accepting writes.
'use strict';
const { MongoClient, BSON } = require('/app/node_modules/mongodb');
const { createHash } = require('node:crypto');
const { createInterface } = require('node:readline');

const encode = (value) => BSON.EJSON.stringify(value, { relaxed: false });
const digest = (value) => createHash('sha256').update(encode(value)).digest('hex');
function indexOptions(index) {
  const { key, v, ns, ...options } = index;
  return [key, options];
}

async function records(db, write) {
  for (const { name, type } of (await db.listCollections().toArray()).sort((a, b) => a.name.localeCompare(b.name))) {
    if (type !== 'collection') throw new Error('Views need an explicit migration; not silently omitted');
    const collection = db.collection(name);
    await write({ kind: 'collection', name, indexes: await collection.indexes() });
    for await (const document of collection.find({}).sort({ _id: 1 })) {
      await write({ kind: 'document', collection: name, document });
    }
  }
}

async function main() {
  const mode = process.argv[2];
  if (!['export', 'restore', 'verify'].includes(mode)) throw new Error('Use export, restore or verify');
  if (!process.env.MONGO_URI) throw new Error('MONGO_URI must explicitly select the database');
  const client = new MongoClient(process.env.MONGO_URI);
  await client.connect();
  try {
    const db = client.db();
    if (mode === 'export') {
      await records(db, async (record) => {
        if (!process.stdout.write(encode(record) + '\n')) {
          await new Promise((resolve) => process.stdout.once('drain', resolve));
        }
      });
      return;
    }
    if (mode === 'restore' && (await db.listCollections().toArray()).length) {
      throw new Error('Restore target must be empty; no database is dropped or overwritten');
    }
    const expected = new Map();
    const indexes = new Map();
    for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
      if (!line) continue;
      const item = BSON.EJSON.parse(line, { relaxed: false });
      if (item.kind === 'collection') {
        if (expected.has(item.name)) throw new Error('Duplicate collection header');
        expected.set(item.name, []);
        indexes.set(item.name, item.indexes);
        if (mode === 'restore') await db.createCollection(item.name);
      } else if (item.kind === 'document' && expected.has(item.collection)) {
        expected.get(item.collection).push(digest(item.document));
        if (mode === 'restore') await db.collection(item.collection).insertOne(item.document);
      } else throw new Error('Invalid or out-of-order archive record');
    }
    if (!expected.size) throw new Error('Empty archive');
    if (mode === 'restore') {
      for (const [name, list] of indexes) {
        for (const index of list) if (index.name !== '_id_') {
          await db.collection(name).createIndex(...indexOptions(index));
        }
      }
    }
    const actual = new Map();
    const actualIndexes = new Map();
    await records(db, async (item) => {
      if (item.kind === 'collection') {
        actual.set(item.name, []);
        actualIndexes.set(item.name, item.indexes);
      } else actual.get(item.collection).push(digest(item.document));
    });
    if ([...actual.keys()].sort().join('\0') !== [...expected.keys()].sort().join('\0')) {
      throw new Error('Collection inventory differs');
    }
    const counts = {};
    for (const [name, hashes] of expected) {
      if (hashes.sort().join('\0') !== actual.get(name).sort().join('\0')) {
        throw new Error('Document hashes differ: ' + name);
      }
      const normalized = (list) => list.map(indexOptions).sort((a, b) => a[1].name.localeCompare(b[1].name));
      if (encode(normalized(indexes.get(name))) !== encode(normalized(actualIndexes.get(name)))) {
        throw new Error('Indexes differ: ' + name);
      }
      counts[name] = hashes.length;
    }
    console.log(JSON.stringify({ mode, verified: true, collections: counts, documents_and_indexes_verified: true }));
  } finally {
    await client.close();
  }
}
main().catch((error) => { console.error(error.message); process.exitCode = 1; });
